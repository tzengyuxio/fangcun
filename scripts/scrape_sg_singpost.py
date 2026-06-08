# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Scrape Singapore (SingPost) Zodiac Series stamp products into data/raw/sg-singpost/.

Source: SingPost online shop (Magento 2), tier=official, id=sg-singpost.
    https://shop.singpost.com/stamps/postage-stamps.html

The storefront product grid is JS-rendered, so the public Magento GraphQL endpoint
(https://shop.singpost.com/graphql) is used instead — it returns the full Zodiac
Series catalogue (stamp sets, self-adhesive booklets, collector's sheets, minipanes,
presentation/special packs, mystamp folders, postcards) with live-resolved image
CDN URLs. Image cache hashes are read from the response, never hardcoded.

The current Lim An-Ling cycle runs 2020 (Rat) – 2031. Each product's lunar year is
derived from the zodiac animal in its title; older one-off / previous-cycle items are
kept as-is. code = "{year}-{sku}" (year-led, unique).

Each product -> data/raw/sg-singpost/{code}/{raw.json, detail.json, img/*.png}
Plus a top-level _index.json.

Usage:
    uv run scripts/scrape_sg_singpost.py --list-only      # collect & print the list
    uv run scripts/scrape_sg_singpost.py                  # full scrape (detail + images)
    uv run scripts/scrape_sg_singpost.py --reparse-local  # re-parse saved detail.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

BASE = "https://shop.singpost.com"
GRAPHQL = f"{BASE}/graphql"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "sg-singpost"
DELAY = 1.0  # polite delay between requests (seconds)
MAX_RETRIES = 3
SOURCE = {"id": "sg-singpost", "tier": "official"}

# Lim An-Ling cycle: lunar year the animal falls on (current 12-year run).
ANIMAL_YEAR = {
    "rat": 2020,
    "ox": 2021,
    "tiger": 2022,
    "rabbit": 2023,
    "dragon": 2024,
    "snake": 2025,
    "horse": 2026,
    "goat": 2027,
    "sheep": 2027,
    "monkey": 2028,
    "rooster": 2029,
    "dog": 2030,
    "pig": 2031,
    "boar": 2031,
}
ANIMALS = list(ANIMAL_YEAR.keys())

# Coarse product role, inferred from the title (for downstream filtering).
ROLE_RULES = [
    ("self-adhesive booklet", "booklet"),
    ("booklet", "booklet"),
    ("collector", "collectors_sheet"),
    ("minipane", "minipane"),
    ("mini pane", "minipane"),
    ("presentation pack", "presentation_pack"),
    ("special pack", "special_pack"),
    ("special sheet", "special_sheet"),
    ("postcard", "postcards"),
    ("mystamp", "mystamp_folder"),
    ("precancelled", "precancelled_fdc"),
    ("fdc", "fdc"),
    ("complete set", "stamp_set"),
    ("stamp set", "stamp_set"),
    ("mega pack", "mega_pack"),
    ("lacquer tray", "gift"),
    ("gem encrusted", "gift"),
    ("gem-encrusted", "gift"),
    ("cycle collectible", "gift"),
]

PRODUCTS_QUERY = """
{ products(search: "zodiac", pageSize: 200) {
    total_count
    items { sku name url_key type_id created_at categories { name } }
} }
"""

DETAIL_QUERY = """
query($sku: String!) {
  products(filter: { sku: { eq: $sku } }) {
    items {
      sku
      name
      url_key
      type_id
      created_at
      description { html }
      short_description { html }
      image { url label }
      media_gallery { url label position }
      categories { name url_path }
      price_range { minimum_price { regular_price { value currency } } }
      ... on PhysicalProductInterface { weight }
    }
  }
}
"""


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.headers["Content-Type"] = "application/json"
    s.headers["Accept"] = "application/json"
    return s


def gql(session: requests.Session, query: str, variables: dict | None = None) -> dict:
    """POST a GraphQL query with retries; raise on persistent failure / GraphQL errors."""
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.post(GRAPHQL, data=json.dumps(payload), timeout=60)
            r.raise_for_status()
            data = r.json()
            if data.get("errors"):
                raise requests.RequestException(f"GraphQL errors: {data['errors']}")
            return data["data"]
        except (requests.RequestException, ValueError, KeyError) as e:
            last_exc = e
            wait = DELAY * attempt
            print(f"    ! GraphQL attempt {attempt} failed: {e} (retry in {wait:.1f}s)",
                  file=sys.stderr)
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    text = re.sub(r"<\s*br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</\s*p\s*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&nbsp;", " ").replace("&#39;", "'").replace("&rsquo;", "’"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def derive_animal(name: str) -> str:
    low = name.lower()
    for a in ANIMALS:
        if re.search(rf"\b{a}\b", low):
            return "goat" if a == "sheep" else ("pig" if a == "boar" else a)
    return ""


def derive_year(animal: str, name: str, created_at: str) -> int | None:
    if animal in ANIMAL_YEAR:
        return ANIMAL_YEAR[animal]
    m = re.search(r"\b(20\d{2})\b", name)
    if m:
        return int(m.group(1))
    return None


def derive_role(name: str) -> str:
    low = name.lower()
    for needle, role in ROLE_RULES:
        if needle in low:
            return role
    return "other"


def derive_code(year: int | None, sku: str) -> str:
    """Year-led unique code, e.g. 2026-csa26ast. Undated items keep the sku only."""
    s = sku.lower()
    return f"{year}-{s}" if year else s


def collect_products(session: requests.Session) -> list[dict]:
    data = gql(session, PRODUCTS_QUERY)
    items = data["products"]["items"]
    out: list[dict] = []
    for it in items:
        name = clean(it["name"])
        animal = derive_animal(name)
        year = derive_year(animal, name, it.get("created_at", ""))
        out.append(
            {
                "sku": it["sku"],
                "name": name,
                "url_key": it["url_key"],
                "type_id": it["type_id"],
                "animal": animal,
                "year": year,
                "role": derive_role(name),
                "code": derive_code(year, it["sku"]),
                "detail_url": f"{BASE}/{it['url_key']}.html",
            }
        )
    # Sort by (year, role, sku) for stable, readable output.
    out.sort(key=lambda x: (x["year"] or 0, x["role"], x["sku"]))
    return out


def parse_detail(item: dict) -> dict:
    """Normalise one GraphQL product item into the raw record's detail fields."""
    gallery = item.get("media_gallery") or []
    image_urls: list[str] = []
    main = (item.get("image") or {}).get("url")
    if main:
        image_urls.append(main)
    for g in sorted(gallery, key=lambda x: x.get("position") or 0):
        url = g.get("url")
        if url and url not in image_urls:
            image_urls.append(url)
    price = (
        item.get("price_range", {})
        .get("minimum_price", {})
        .get("regular_price", {})
    )
    return {
        "page_name": clean(item.get("name")),
        "description": html_to_text((item.get("description") or {}).get("html")),
        "short_description": html_to_text((item.get("short_description") or {}).get("html")),
        "categories": [c["name"] for c in (item.get("categories") or [])],
        "price": price.get("value"),
        "currency": price.get("currency"),
        "weight": item.get("weight"),
        "created_at": item.get("created_at"),
        "image_urls": image_urls,
    }


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=120)
        r.raise_for_status()
        if not r.content:
            raise requests.RequestException("empty body")
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def scrape_set(session: requests.Session, meta: dict) -> dict:
    set_dir = OUT_DIR / meta["code"]
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    data = gql(session, DETAIL_QUERY, {"sku": meta["sku"]})
    items = data["products"]["items"]
    if not items:
        raise requests.RequestException(f"no product for sku {meta['sku']}")
    item = items[0]
    (set_dir / "detail.json").write_text(
        json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    detail = parse_detail(item)

    images: list[dict] = []
    for url in detail["image_urls"]:
        fname = Path(urlparse(url).path).name
        img = {"image_url": url}
        if download(session, url, img_dir / fname):
            img["image_file"] = f"img/{fname}"
        images.append(img)
        time.sleep(DELAY)

    record = {
        "code": meta["code"],
        "sku": meta["sku"],
        "name": meta["name"],
        "animal": meta["animal"],
        "year": meta["year"],
        "role": meta["role"],
        "type_id": meta["type_id"],
        "url_key": meta["url_key"],
        "detail_url": meta["detail_url"],
        "page_name": detail["page_name"],
        "categories": detail["categories"],
        "price": detail["price"],
        "currency": detail["currency"],
        "weight": detail["weight"],
        "created_at": detail["created_at"],
        "description": detail["description"],
        "short_description": detail["short_description"],
        "images": images,
        "n_images": len([i for i in images if i.get("image_file")]),
        "source": SOURCE,
    }
    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def reparse_local() -> None:
    """Re-parse saved detail.json into raw.json without hitting the server."""
    for d in sorted(p for p in OUT_DIR.iterdir() if p.is_dir()):
        rawf, detailf = d / "raw.json", d / "detail.json"
        if not rawf.exists() or not detailf.exists():
            continue
        old = json.loads(rawf.read_text(encoding="utf-8"))
        item = json.loads(detailf.read_text(encoding="utf-8"))
        detail = parse_detail(item)
        img_map = {
            Path(urlparse(i["image_url"]).path).name: i.get("image_file")
            for i in old.get("images", [])
        }
        images = []
        for url in detail["image_urls"]:
            fname = Path(urlparse(url).path).name
            img = {"image_url": url}
            if img_map.get(fname):
                img["image_file"] = img_map[fname]
            images.append(img)
        old.update(
            {
                "page_name": detail["page_name"],
                "categories": detail["categories"],
                "price": detail["price"],
                "currency": detail["currency"],
                "weight": detail["weight"],
                "created_at": detail["created_at"],
                "description": detail["description"],
                "short_description": detail["short_description"],
                "images": images,
                "n_images": len([i for i in images if i.get("image_file")]),
            }
        )
        rawf.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  reparsed {d.name}: desc={len(detail['description'])} chars, "
              f"{len(images)} images", file=sys.stderr)


def write_index(sets: list[dict]) -> None:
    idx = [
        {
            "code": s["code"],
            "sku": s["sku"],
            "name": s["name"],
            "animal": s["animal"],
            "year": s["year"],
            "role": s["role"],
            "detail_url": s["detail_url"],
            "source": SOURCE,
        }
        for s in sets
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "_index.json").write_text(
        json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="only collect & print the list")
    ap.add_argument("--reparse-local", action="store_true",
                    help="re-parse saved detail.json into raw.json (no network)")
    args = ap.parse_args()

    if args.reparse_local:
        print("Re-parsing local detail.json files...", file=sys.stderr)
        reparse_local()
        print("Done.", file=sys.stderr)
        return

    session = make_session()
    print("Collecting Zodiac Series products via GraphQL...", file=sys.stderr)
    sets = collect_products(session)
    print(f"Total products: {len(sets)}", file=sys.stderr)

    write_index(sets)

    if args.list_only:
        for s in sets:
            yr = s["year"] or "----"
            print(f"  {yr} {s['animal'] or '-':8} {s['role']:18} {s['code']}")
        return

    for i, meta in enumerate(sets, 1):
        print(f"[{i}/{len(sets)}] {meta['code']} {meta['name'][:50]}", file=sys.stderr)
        try:
            rec = scrape_set(session, meta)
            print(f"    images={rec['n_images']} desc={len(rec['description'])} chars",
                  file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - keep going on a single product failure
            print(f"    ! product failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
