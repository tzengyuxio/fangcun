# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Scrape Isle of Man Post (iomstamps.com) Chinese zodiac stamp sets into data/raw/im-iompost/.

Source: official Shopify storefront products feed (tier=official, id=im-iomstamps).
The store is a live shop and only lists *currently stocked* products, so historical
zodiac years that have sold out are absent from the feed. As of the last run only the
most recent years (Snake, Horse) are available; this is a real limitation of the source,
not a scraper bug. We discover zodiac products from /products.json (no guessed handles),
group them by zodiac animal/year, and download a representative high-res image per set.

Each set -> data/raw/im-iompost/{code}/{raw.json, img/<rep>.jpg}
  code: zodiac animal slug (e.g. "horse", "snake") -- one zodiac year per code, unique.

Image URLs come from each product's images[].src (Shopify CDN); we request ?width=1600
for a high-resolution copy.

Usage:
    uv run scripts/scrape_im_iompost.py --list-only   # discover & print zodiac sets
    uv run scripts/scrape_im_iompost.py               # download metadata + rep image
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

BASE = "https://iomstamps.com"
PRODUCTS_URL = BASE + "/products.json"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "im-iompost"
DELAY = 1.0  # polite delay between requests (seconds)
IMG_WIDTH = 1600

# The 12 zodiac animals (singular, lowercase) used to detect & slug products.
ZODIAC = [
    "rat", "ox", "tiger", "rabbit", "dragon", "snake",
    "horse", "goat", "sheep", "ram", "monkey", "rooster", "dog", "pig", "boar",
]
TITLE_RE = re.compile(r"chinese year of the\s+([a-z]+)", re.IGNORECASE)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def fetch_products(session: requests.Session) -> list[dict]:
    """Page through the Shopify products feed until an empty page."""
    products: list[dict] = []
    page = 1
    while True:
        r = session.get(PRODUCTS_URL, params={"limit": 250, "page": page}, timeout=30)
        r.raise_for_status()
        batch = r.json().get("products", [])
        if not batch:
            break
        products.extend(batch)
        print(f"  page {page}: {len(batch)} products (cumulative {len(products)})", file=sys.stderr)
        page += 1
        time.sleep(DELAY)
    return products


def zodiac_of(title: str) -> str | None:
    """Return the zodiac animal slug for a 'Chinese Year of the X' title, else None."""
    m = TITLE_RE.search(title)
    if not m:
        return None
    animal = m.group(1).lower()
    return animal if animal in ZODIAC else None


def hires(src: str) -> str:
    """Force a high-resolution Shopify CDN variant via the width parameter."""
    sep = "&" if "?" in src else "?"
    return f"{src}{sep}width={IMG_WIDTH}"


def product_summary(p: dict) -> dict:
    variants = p.get("variants") or []
    prices = [v.get("price") for v in variants if v.get("price")]
    return {
        "id": p.get("id"),
        "title": p.get("title", ""),
        "handle": p.get("handle", ""),
        "product_type": p.get("product_type", ""),
        "published_at": p.get("published_at", ""),
        "tags": p.get("tags", []),
        "url": f"{BASE}/products/{p.get('handle', '')}",
        "price": prices[0] if prices else "",
        "currency": "GBP",
        "skus": [v.get("sku") for v in variants if v.get("sku")],
        "image_urls": [hires(im["src"]) for im in (p.get("images") or []) if im.get("src")],
    }


def group_zodiac(products: list[dict]) -> list[dict]:
    """Group genuine zodiac products by animal into one set per zodiac year."""
    groups: dict[str, list[dict]] = {}
    for p in products:
        animal = zodiac_of(p.get("title", ""))
        if animal:
            groups.setdefault(animal, []).append(p)

    sets: list[dict] = []
    for animal, prods in groups.items():
        prods = sorted(prods, key=lambda x: x.get("title", ""))
        # Earliest published_at across the set -> approximate issue year.
        dates = [p.get("published_at", "") for p in prods if p.get("published_at")]
        year = min(dates)[:4] if dates else ""
        # Prefer a "Set" product for the representative image; else first with images.
        rep = next((p for p in prods if "set" in p.get("title", "").lower()), prods[0])
        rep = rep if (rep.get("images")) else next((p for p in prods if p.get("images")), rep)
        rep_imgs = [im["src"] for im in (rep.get("images") or []) if im.get("src")]
        sets.append(
            {
                "code": animal,
                "zodiac": animal,
                "year": year,
                "title": f"Chinese Year of the {animal.capitalize()}",
                "n_products": len(prods),
                "rep_image_url": hires(rep_imgs[0]) if rep_imgs else "",
                "products": [product_summary(p) for p in prods],
                "source": {"id": "im-iomstamps", "tier": "official"},
            }
        )
    return sorted(sets, key=lambda x: (x["year"], x["code"]))


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def scrape_set(session: requests.Session, meta: dict) -> dict:
    set_dir = OUT_DIR / meta["code"]
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    record = dict(meta)
    if meta["rep_image_url"]:
        fname = Path(urlparse(meta["rep_image_url"]).path).name
        if download(session, meta["rep_image_url"], img_dir / fname):
            record["rep_image_file"] = f"img/{fname}"
        time.sleep(DELAY)

    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="only discover & print sets")
    args = ap.parse_args()

    session = make_session()
    print("Fetching Shopify products feed...", file=sys.stderr)
    products = fetch_products(session)
    print(f"Total products: {len(products)}", file=sys.stderr)
    sets = group_zodiac(products)
    print(f"Zodiac sets found: {len(sets)}", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "_index.json").write_text(
        json.dumps(sets, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.list_only:
        for s in sets:
            print(f"  {s['code']:8} {s['year']}  {s['n_products']} products  {s['title']}")
        return

    for i, meta in enumerate(sets, 1):
        print(f"[{i}/{len(sets)}] {meta['code']} {meta['title']} ({meta['n_products']} products)",
              file=sys.stderr)
        try:
            scrape_set(session, meta)
        except Exception as e:  # noqa: BLE001 - keep going on a single set failure
            print(f"    ! set failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
