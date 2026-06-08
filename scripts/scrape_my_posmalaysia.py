# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Scrape Pos Malaysia (shop.pos.com.my) Chinese-zodiac stamp sets.

Source: the Magento storefront category "Stamps & Philately" (cat=3838) lists all
225 philatelic SKUs on a single page (no server-side paging for this category).
The zodiac issues are mixed in among festival folders, postboxes, totes, etc., so
we keyword-filter them out, then group the surviving SKUs into *sets* (one issue =
one zodiac animal/year, with its stamp sheets / miniature sheet / FDC / folder /
envelope as member products).

  - list:    https://shop.pos.com.my/shop.html?cat=3838
             -> <li class="item product product-item"> blocks, each with
                product name, product id, product .html URL and a grid image.
  - detail:  each member product's own .html page embeds a Magento
             "mage/gallery/gallery" JSON config -> full-res image array,
             plus two description blocks (overview + "This Product Includes" /
             date & place of issue).
  - images:  assets.pos.com.my/pos-shop/media/catalog/product/{a}/{b}/{file}.jpg
             (CloudFront). The gallery `full` URL carries a /cache/{hash}/ segment
             which we strip to fetch the original full-res file.

tier=official, source id `my-posmalaysia`. Lands into data/raw/my-posmalaysia/{code}/.

Malaysia's zodiac output is historically discontinuous; the current "Setem Ku" /
animal-named series is stable from ~2021. The online shop only carries in-stock
SKUs, so a series may be partial (sold-out sheets drop off the catalogue). We
record faithfully whatever the live storefront exposes.

`code` = "{year}-{animal_en}" (e.g. 2026-horse, 2025-snake), unique per issue.
CNY "Setem Ku" festive sets that are not a single zodiac animal use "{year}-cny".

Each set -> data/raw/my-posmalaysia/{code}/{raw.json, products/*.html, img/*}

Usage:
    uv run scripts/scrape_my_posmalaysia.py --list-only   # list sets, no download
    uv run scripts/scrape_my_posmalaysia.py               # full scrape + images
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests

LIST_URL = "https://shop.pos.com.my/shop.html?cat=3838"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "my-posmalaysia"
DELAY = 1.0  # polite delay between requests (seconds)
SOURCE = {"id": "my-posmalaysia", "tier": "official"}

# Malay zodiac animal names -> English label. Matched as whole words so that
# substrings like "ox" in "box/tote" or "ular" in "funikular/regular" do NOT
# trigger false positives.
ZODIAC_MALAY = {
    "tikus": "Rat",
    "lembu": "Ox",
    "kerbau": "Ox",
    "harimau": "Tiger",
    "arnab": "Rabbit",
    "naga": "Dragon",
    "ular": "Snake",
    "kuda": "Horse",
    "kambing": "Goat",
    "biri-biri": "Goat",
    "monyet": "Monkey",
    "ayam": "Rooster",
    "anjing": "Dog",
    "babi": "Pig",
    "khinzir": "Pig",
}
ANIMAL_SLUG = {
    "Rat": "rat", "Ox": "ox", "Tiger": "tiger", "Rabbit": "rabbit",
    "Dragon": "dragon", "Snake": "snake", "Horse": "horse", "Goat": "goat",
    "Monkey": "monkey", "Rooster": "rooster", "Dog": "dog", "Pig": "pig",
}
ZODIAC_BRANCH = {
    "Rat": "子", "Ox": "丑", "Tiger": "寅", "Rabbit": "卯", "Dragon": "辰",
    "Snake": "巳", "Horse": "午", "Goat": "未", "Monkey": "申", "Rooster": "酉",
    "Dog": "戌", "Pig": "亥",
}
# Current-cycle lunar year per animal (the issues actually carried by the live
# shop, ~2021 onwards). Used only as a last-resort fallback when a product page
# exposes no explicit issue date / year (e.g. the Ular series). Flagged in the
# output as year_inferred so downstream can treat it as needing verification.
ANIMAL_CYCLE_YEAR = {
    "Rat": "2020", "Ox": "2021", "Tiger": "2022", "Rabbit": "2023",
    "Dragon": "2024", "Snake": "2025", "Horse": "2026", "Goat": "2027",
    "Monkey": "2028", "Rooster": "2029", "Dog": "2030", "Pig": "2031",
}
# CNY "Setem Ku" festive zodiac sets (e.g. "CNY 2024 Setem Ku Set").
CNY_RE = re.compile(r"\bcny\s*(\d{4})\b.*\bsetem\s*ku\b", re.I)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", htmllib.unescape(text)).strip()


def strip_cache(url: str) -> str:
    """Drop the Magento /cache/{hash}/ segment to get the original full-res file."""
    return re.sub(r"/cache/[0-9a-f]+/", "/", url)


def match_zodiac(name: str) -> tuple[str | None, bool]:
    """Return (animal_en | None, is_cny). Whole-word Malay animal match + CNY rule."""
    low = name.lower()
    cny = bool(CNY_RE.search(low))
    for malay, animal in ZODIAC_MALAY.items():
        if re.search(rf"\b{re.escape(malay)}\b", low):
            return animal, cny
    return (None, cny)


def parse_list(html: str) -> list[dict]:
    """Extract every product item on the category page."""
    blocks = re.split(r'<li class="item product product-item">', html)[1:]
    items: list[dict] = []
    for b in blocks:
        m_name = re.search(
            r'product name product-item-name">\s*(.*?)\s*</strong>', b, re.S
        )
        if not m_name:
            continue
        name = clean(m_name.group(1))
        m_url = re.search(
            r'href="([^"]+\.html)"\s+class="product photo product-item-photo"', b
        )
        m_pid = re.search(r'name="product" value="(\d+)"', b)
        m_img = re.search(r'class="product-grid-image"\s+src="([^"]+)"', b)
        items.append(
            {
                "name": name,
                "product_id": m_pid.group(1) if m_pid else None,
                "url": m_url.group(1) if m_url else None,
                "grid_image": m_img.group(1) if m_img else None,
            }
        )
    return items


def filter_zodiac(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    for it in items:
        if not it["url"]:
            continue
        animal, cny = match_zodiac(it["name"])
        if not animal and not cny:
            continue
        it = {**it, "animal": animal, "is_cny": cny}
        out.append(it)
    return out


def derive_year(name: str, desc: str = "") -> str:
    """Issue year: prefer 'Date of issue: DD.MM.YYYY' in the detail desc,
    else a 4-digit year in the name, else a 2-digit suffix in the slug (kuda26)."""
    m = re.search(r"date of issue:\s*\d{1,2}[.\-/]\d{1,2}[.\-/](\d{4})", desc, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b(19|20)\d{2}\b", name)
    if m:
        return m.group(0)
    m = re.search(r"(\d{2})\b", name)  # e.g. "KUDA SIRI 2" has no year -> caller handles
    return ""


def parse_detail(html: str) -> dict:
    """Pull gallery images + description blocks + sku from a product page."""
    images: list[str] = []
    m = re.search(r'"data":\s*(\[\{"thumb".*?\}\])', html, re.S)
    if m:
        try:
            for g in json.loads(m.group(1)):
                full = g.get("full") or g.get("img") or g.get("thumb")
                if full:
                    images.append(strip_cache(full))
        except ValueError:
            pass
    if not images:  # fallback to the og:image / main image
        m = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        if m:
            images.append(strip_cache(m.group(1)))

    def block(cls: str) -> str:
        mm = re.search(rf'class="{cls}">(.*?)</div>', html, re.S)
        if not mm:
            return ""
        txt = re.sub(r"<[^>]+>", "\n", mm.group(1))
        return clean(htmllib.unescape(txt))

    desc_one = block("custom-attribute-top-desp one")
    desc_two = block("custom-attribute-top-desp two")

    m_sku = re.search(
        r'product attribute sku.*?value">\s*([^<]+?)\s*<', html, re.S
    )
    sku = clean(m_sku.group(1)) if m_sku else ""

    m_iss = re.search(
        r"date of issue:\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})", desc_two, re.I
    )
    m_place = re.search(r"place of issue:\s*([^\n]+)", desc_two, re.I)

    return {
        "sku": sku,
        "description": desc_one,
        "contents": desc_two,
        "issue_date_raw": m_iss.group(1) if m_iss else "",
        "place_of_issue": clean(m_place.group(1)) if m_place else "",
        "image_urls": images,
    }


def norm_date(raw: str) -> str:
    """DD.MM.YYYY -> YYYY-MM-DD (best effort)."""
    m = re.match(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", raw)
    if not m:
        return ""
    d, mo, y = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"      ! image failed {url}: {e}", file=sys.stderr)
        return False


def group_sets(zodiac_items: list[dict], session: requests.Session) -> dict[str, dict]:
    """Fetch each member's detail, derive year, group into {code: set}."""
    members: list[dict] = []
    for it in zodiac_items:
        url = it["url"]
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            detail = parse_detail(r.text)
            it["_html"] = r.text
        except requests.RequestException as e:
            print(f"  ! detail failed {url}: {e}", file=sys.stderr)
            detail = {"image_urls": [it["grid_image"]] if it["grid_image"] else []}
            it["_html"] = ""
        it["detail"] = detail
        year = derive_year(it["name"], detail.get("contents", ""))
        inferred = False
        # series-level year fallback by slug suffix (e.g. kuda26 -> 2026)
        if not year:
            slug = Path(urlparse(url).path).stem
            ms = re.search(r"(\d{2})\b", slug)
            if ms:
                yy = int(ms.group(1))
                year = f"20{yy:02d}" if yy < 90 else f"19{yy:02d}"
        # last resort: infer from the animal's current-cycle lunar year
        if not year and it["animal"]:
            year = ANIMAL_CYCLE_YEAR.get(it["animal"], "")
            inferred = bool(year)
        it["year"] = year
        it["year_inferred"] = inferred
        members.append(it)
        print(
            f"  · {it['name'][:50]:50} animal={it['animal'] or '-':7} "
            f"year={year or '?'} imgs={len(detail.get('image_urls', []))}",
            file=sys.stderr,
        )
        time.sleep(DELAY)

    # Group by (year, animal) for animal sets; (year, 'cny') for CNY festive sets.
    grouped: dict[str, list[dict]] = defaultdict(list)
    for m in members:
        if m["animal"]:
            slug = ANIMAL_SLUG.get(m["animal"], m["animal"].lower())
            code = f"{m['year'] or 'unknown'}-{slug}"
        else:  # CNY-only festive set
            code = f"{m['year'] or 'unknown'}-cny"
        grouped[code].append(m)

    sets: dict[str, dict] = {}
    for code, mem in grouped.items():
        animals = sorted({m["animal"] for m in mem if m["animal"]})
        animal = animals[0] if animals else None
        years = sorted({m["year"] for m in mem if m["year"]})
        # best issue_date among members
        dates = sorted({m["detail"].get("issue_date_raw") for m in mem if m["detail"].get("issue_date_raw")})
        sets[code] = {
            "animal": animal,
            "year": years[0] if years else "",
            "year_inferred": all(m.get("year_inferred") for m in mem) and bool(years),
            "issue_date_raw": dates[0] if dates else "",
            "members": mem,
        }
    return sets


def scrape_set(code: str, s: dict, session: requests.Session) -> dict:
    set_dir = OUT_DIR / code
    img_dir = set_dir / "img"
    prod_dir = set_dir / "products"
    img_dir.mkdir(parents=True, exist_ok=True)
    prod_dir.mkdir(parents=True, exist_ok=True)

    products: list[dict] = []
    n_img = 0
    seen_files: set[str] = set()
    for m in s["members"]:
        # persist the raw product HTML for traceability / re-parse
        if m.get("_html"):
            slug = Path(urlparse(m["url"]).path).name
            (prod_dir / slug).write_text(m["_html"], encoding="utf-8")
        detail = m["detail"]
        imgs: list[dict] = []
        for u in detail.get("image_urls", []):
            fname = Path(urlparse(u).path).name
            if fname in seen_files:
                # shared file across SKUs -> reference, don't redownload
                imgs.append({"image_url": u, "image_file": f"img/{fname}"})
                continue
            ok = download(session, u, img_dir / fname)
            if ok:
                seen_files.add(fname)
                n_img += 1
            imgs.append(
                {"image_url": u, "image_file": f"img/{fname}" if ok else None}
            )
            time.sleep(DELAY)
        products.append(
            {
                "name": m["name"],
                "product_id": m["product_id"],
                "url": m["url"],
                "sku": detail.get("sku", ""),
                "description": detail.get("description", ""),
                "contents": detail.get("contents", ""),
                "place_of_issue": detail.get("place_of_issue", ""),
                "images": imgs,
            }
        )

    animal = s["animal"]
    record = {
        "code": code,
        "source": SOURCE,
        "region": {"code": "MY", "name": "Pos Malaysia"},
        "year": s["year"],
        "year_inferred": s.get("year_inferred", False),
        "zodiac_animal": animal,
        "zodiac_branch": ZODIAC_BRANCH.get(animal, "") if animal else "",
        "is_cny_festive": animal is None,
        "issue_date": norm_date(s["issue_date_raw"]),
        "issue_date_raw": s["issue_date_raw"],
        "list_url": LIST_URL,
        "n_products": len(products),
        "n_images": n_img,
        "products": products,
    }
    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="list sets, no download")
    args = ap.parse_args()

    session = make_session()
    print(f"Fetching category list: {LIST_URL}", file=sys.stderr)
    r = session.get(LIST_URL, timeout=60)
    r.raise_for_status()
    all_items = parse_list(r.text)
    print(f"Total catalogue items: {len(all_items)}", file=sys.stderr)
    time.sleep(DELAY)

    zodiac = filter_zodiac(all_items)
    print(f"Zodiac-matched SKUs: {len(zodiac)}", file=sys.stderr)
    for it in zodiac:
        print(f"  [{it['animal'] or 'CNY'}] {it['name']}", file=sys.stderr)

    print("\nFetching detail pages to group into sets...", file=sys.stderr)
    sets = group_sets(zodiac, session)
    print(f"\nGrouped into {len(sets)} sets:", file=sys.stderr)
    for code, s in sorted(sets.items()):
        print(
            f"  {code:16} animal={s['animal'] or '-':7} "
            f"members={len(s['members'])} issue={s['issue_date_raw'] or '?'}",
            file=sys.stderr,
        )

    if args.list_only:
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
    for i, (code, s) in enumerate(sorted(sets.items()), 1):
        print(f"\n[{i}/{len(sets)}] {code}", file=sys.stderr)
        try:
            rec = scrape_set(code, s, session)
        except Exception as e:  # noqa: BLE001 - keep going on a single set failure
            print(f"  ! set failed: {e}", file=sys.stderr)
            continue
        print(
            f"  -> {rec['n_products']} products, {rec['n_images']} images",
            file=sys.stderr,
        )
        index.append(
            {
                "code": rec["code"],
                "year": rec["year"],
                "zodiac_animal": rec["zodiac_animal"],
                "is_cny_festive": rec["is_cny_festive"],
                "issue_date": rec["issue_date"],
                "n_products": rec["n_products"],
                "n_images": rec["n_images"],
            }
        )

    index.sort(key=lambda x: (x["year"] or "", x["code"]))
    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nDone. {len(index)} sets -> {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
