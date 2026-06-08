# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Scrape Mongol Post (mongolstamps.com) Lunar New Year zodiac stamp sets.

Source: https://mongolstamps.com/en is a Nuxt/Vue SPA whose `window.__NUXT__`
is a minified positional-arg IIFE (not plain JSON), so we go straight to the
Laravel JSON backend the SPA itself calls:

  - base:    https://api.mongolstamps.com  (axios baseURL, found in /_nuxt/*.js)
  - cats:    api/front/categories          -> category id 6 = "Lunar new year"
  - list:    api/front/types/{type}/products?category=6
             (type 1 = "Stamps"; the lunar-new-year category lives only here)
  - detail:  api/front/products/{id}
             (returns the product + related; adds `descriptions` & `attributes`
              not present in the list view)
  - images:  the product's own `images` JSON array, full-res, directly curl-able
             (e.g. https://api.mongolstamps.com/images/products/{id}/<file>.jpeg)

tier=official, source id `mn-mongolpost`. Lands into data/raw/mn-mongolpost/{code}/.

Mongolia uses the standard 12 zodiac animals (no Vietnamese cat-year variant);
the festive frame is Tsagaan Sar (the "White Moon" lunar new year). The online
catalogue only carries recent issues (not a full historical 12-year cycle); we
record faithfully whatever the official API exposes.

`code` = issue year (unique per set); a -N suffix disambiguates the rare case of
two sets issued the same year (e.g. a stamp + souvenir sheet for 2026).

Each set -> data/raw/mn-mongolpost/{code}/{raw.json, detail.json, img/*}

Usage:
    uv run scripts/scrape_mn_mongolpost.py --list-only   # list the sets, no download
    uv run scripts/scrape_mn_mongolpost.py               # full scrape + images
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

API = "https://api.mongolstamps.com"
SITE = "https://mongolstamps.com/en"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "mn-mongolpost"
DELAY = 1.0  # polite delay between requests (seconds)
SOURCE = {"id": "mn-mongolpost", "tier": "official"}

LUNAR_CATEGORY_ID = 6  # "Жилийн марк" / "Lunar new year"
STAMP_TYPE_ID = 1  # "Марк" / "Stamps" (the type the lunar category lives under)

# Standard Mongolian (Cyrillic) zodiac animal -> EN, for cross-referencing the
# English product titles. Mongolia keeps the classic 12 (no cat-year swap).
ZODIAC_EN = {
    "rat": "Rat", "mouse": "Rat", "ox": "Ox", "tiger": "Tiger",
    "rabbit": "Rabbit", "hare": "Rabbit", "dragon": "Dragon", "snake": "Snake",
    "horse": "Horse", "goat": "Goat", "sheep": "Goat", "ram": "Goat",
    "monkey": "Monkey", "rooster": "Rooster", "cock": "Rooster",
    "chicken": "Rooster", "dog": "Dog", "pig": "Pig", "boar": "Pig",
}


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.headers["Accept"] = "application/json"
    return s


def label_en(labels_json: str | None) -> str:
    """Pick the English value out of a labels/title JSON-string array."""
    if not labels_json:
        return ""
    try:
        for item in json.loads(labels_json):
            if item.get("key") == "en" and item.get("value"):
                return item["value"].strip()
    except (ValueError, TypeError, AttributeError):
        pass
    return ""


def derive_zodiac(title_en: str) -> str:
    """Best-effort zodiac animal from an English title like 'Year of the Snake'."""
    low = title_en.lower()
    for key, animal in ZODIAC_EN.items():
        if re.search(rf"\b{key}\b", low):
            return animal
    return ""


def derive_year(item: dict) -> str:
    """Issue year from created_date (YYYY-MM-DD), falling back to a title year."""
    cd = item.get("created_date") or ""
    m = re.match(r"(\d{4})", cd)
    if m:
        return m.group(1)
    m = re.search(r"(19|20)\d{2}", label_en(item.get("title")))
    return m.group(0) if m else ""


def fetch_json(session: requests.Session, path: str) -> object:
    r = session.get(f"{API}/{path}", timeout=30)
    r.raise_for_status()
    return r.json()


def collect_sets(session: requests.Session) -> list[dict]:
    """List lunar-new-year stamp products from the official API."""
    data = fetch_json(
        session,
        f"api/front/types/{STAMP_TYPE_ID}/products?category={LUNAR_CATEGORY_ID}",
    )
    items = data if isinstance(data, list) else data.get("data", [])
    return items


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def find_in_detail(detail: object, pid: int) -> dict | None:
    """The detail endpoint returns [product, ...related]; pick our product."""
    items = detail if isinstance(detail, list) else [detail]
    for it in items:
        if isinstance(it, dict) and it.get("id") == pid:
            return it
    return items[0] if items and isinstance(items[0], dict) else None


def unique_code(year: str, fallback: str, used: set[str]) -> str:
    base = year or fallback
    code = base
    n = 2
    while code in used:
        code = f"{base}-{n}"
        n += 1
    used.add(code)
    return code


def scrape_set(session: requests.Session, item: dict, used_codes: set[str]) -> dict:
    pid = item["id"]
    title_en = label_en(item.get("title"))
    year = derive_year(item)
    code = unique_code(year, str(pid), used_codes)

    set_dir = OUT_DIR / code
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    # Detail (adds descriptions + attributes); keep raw for traceability.
    detail_raw = fetch_json(session, f"api/front/products/{pid}")
    (set_dir / "detail.json").write_text(
        json.dumps(detail_raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    detail = find_in_detail(detail_raw, pid) or item

    # Images come from the product's own `images` array (full-res, curl-able).
    try:
        image_urls = json.loads(detail.get("images") or item.get("images") or "[]")
    except (ValueError, TypeError):
        image_urls = []

    images: list[dict] = []
    for u in image_urls:
        u = u.strip()
        if not u:
            continue
        fname = Path(urlparse(u).path).name
        ok = download(session, u, img_dir / fname)
        images.append({"image_url": u, "image_file": f"img/{fname}" if ok else None})
        time.sleep(DELAY)

    # Flatten the multilingual attributes into label_en -> value pairs.
    attributes: dict[str, str] = {}
    for attr in detail.get("attributes", []) or []:
        name = label_en(attr.get("labels")) or attr.get("name") or ""
        value = (attr.get("pivot") or {}).get("value")
        if name and value not in (None, ""):
            attributes[name] = str(value)

    # Multilingual descriptions (often empty on this site, recorded as-is).
    descriptions: dict[str, str] = {}
    for d in detail.get("descriptions", []) or []:
        lang = d.get("id") or d.get("name")
        text = (d.get("pivot") or {}).get("description")
        if lang and text:
            descriptions[lang] = text

    record = {
        "code": code,
        "source": SOURCE,
        "product_id": pid,
        "product_code": detail.get("product_code") or item.get("product_code"),
        "detail_url": f"{SITE}/marks/{pid}",
        "api_detail": f"{API}/api/front/products/{pid}",
        "title": title_en,
        "title_mn": detail.get("name") or item.get("name"),
        "year": year,
        "zodiac": derive_zodiac(title_en),
        "issue_date": item.get("created_date") or "",
        "type_name_en": label_en(item.get("type", {}).get("labels"))
        or item.get("type_name"),
        "sub_type_name": item.get("sub_type_name") or "",
        "category_name_en": label_en(item.get("category", {}).get("labels"))
        or item.get("category_name"),
        "size": item.get("size") or "",
        "price": item.get("price"),
        "attributes": attributes,
        "descriptions": descriptions,
        "images": images,
        "n_images": sum(1 for im in images if im["image_file"]),
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
    print("Fetching lunar-new-year product list from API...", file=sys.stderr)
    items = collect_sets(session)
    print(f"Total sets: {len(items)}", file=sys.stderr)

    if args.list_only:
        for it in items:
            t = label_en(it.get("title"))
            print(f"  id={it['id']:5} code={it.get('product_code',''):6} "
                  f"{derive_year(it):4} {t}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    used_codes: set[str] = set()
    index: list[dict] = []
    for i, item in enumerate(items, 1):
        print(f"[{i}/{len(items)}] id={item['id']} {label_en(item.get('title'))}",
              file=sys.stderr)
        try:
            rec = scrape_set(session, item, used_codes)
        except Exception as e:  # noqa: BLE001 - keep going on a single set failure
            print(f"    ! set failed: {e}", file=sys.stderr)
            time.sleep(DELAY)
            continue
        print(f"    code={rec['code']} year={rec['year']} "
              f"zodiac={rec['zodiac'] or '?'} {rec['n_images']} imgs",
              file=sys.stderr)
        index.append(
            {
                "code": rec["code"],
                "product_id": rec["product_id"],
                "product_code": rec["product_code"],
                "title": rec["title"],
                "year": rec["year"],
                "zodiac": rec["zodiac"],
                "issue_date": rec["issue_date"],
                "type_name_en": rec["type_name_en"],
                "n_images": rec["n_images"],
                "detail_url": rec["detail_url"],
            }
        )
        time.sleep(DELAY)

    index.sort(key=lambda x: (x["year"] or "", x["code"]))
    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Done. {len(index)} sets -> {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
