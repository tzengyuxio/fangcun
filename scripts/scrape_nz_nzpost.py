# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Scrape New Zealand Post (NZ Post Collectables) zodiac stamps into data/raw/nz-nzpost/.

Source: NZ Post Collectables online shop (BigCommerce, store hash s-364g6nmu99),
    tier=official, id=nz-nzpost. https://collectables.nzpost.co.nz/

Enumeration: the BigCommerce XML product sitemap
    https://collectables.nzpost.co.nz/xmlsitemap.php?type=products&page=1
lists every product. We filter to "Year of the ..." products (1997-2026, 30 lunar
years, ~235 products) and then pick ONE representative issue per year.

⚠ Variant explosion: recent years carry dozens of premium/numbered variants
(numbered gold-foiled framed sheets #1..#100+, perspex stands, medallions, pins,
presentation packs, plate/value/barcode/logo blocks, individual single stamps and
stamp sheets, FDCs, merchandise like tea towels / stickers / art prints). The CNY
"collection" page only surfaces those premium variants, never the plain set.

Representative selection per year, in priority order:
  1. "... Set of Mint Stamps"  (the gummed set, recent years)
  2. plain miniature sheet ("... Mint Miniature Sheet" or "... Miniature Sheet")
  3. fallback: the bare issue product ("{year} Year of the {animal}[ descriptive]")
     used by older years (1997-2021) which list a single product.
All numbered / premium / block / single-stamp / merchandise variants are dropped.

code = the lunar year (one issue per year; unique). When a year keeps two
representatives (mint set + miniature sheet), the miniature sheet code is suffixed
"-ms" to stay unique while the set keeps the bare year.

Each issue -> data/raw/nz-nzpost/{code}/{raw.json, detail.html, img/*.jpg}
Plus a top-level _index.json.

Images: BigCommerce CDN; the stencil size segment is rewritten to 1280x1280 for
the largest available render.

Usage:
    uv run scripts/scrape_nz_nzpost.py --list-only      # collect & print the list
    uv run scripts/scrape_nz_nzpost.py                  # full scrape (detail + images)
    uv run scripts/scrape_nz_nzpost.py --reparse-local  # re-parse saved detail.html
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests

BASE = "https://collectables.nzpost.co.nz"
SITEMAP = f"{BASE}/xmlsitemap.php?type=products&page=1"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "nz-nzpost"
DELAY = 1.0  # polite delay between requests (seconds)
MAX_RETRIES = 3
SOURCE = {"id": "nz-nzpost", "tier": "official"}

# Lunar animal -> the year(s) it falls on; used to derive the animal from a slug.
ANIMALS = (
    "rat", "ox", "tiger", "rabbit", "dragon", "snake",
    "horse", "sheep", "goat", "monkey", "rooster", "dog", "pig",
)

# Variant noise to drop (premium / numbered / blocks / singles / merchandise).
EXCLUDE_KEYWORDS = (
    "numbered", "gold-foiled", "gold-plated", "perspex", "medallion", "pin",
    "presentation", "block", "cancelled", "first-day", "framed", "silver",
    "stickers", "tea-towel", "art-print", "limited-edition",
)

# A single-denomination stamp / stamp sheet, e.g. "...-4-70-stamp" or "...-stamp-sheet".
SINGLE_STAMP_RE = re.compile(r"-\d+-\d+-stamp(-sheet)?/?$")


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def get(session: requests.Session, url: str, timeout: int = 60) -> requests.Response:
    """GET with retries; raise on persistent failure."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last_exc = e
            wait = DELAY * attempt
            print(f"    ! GET attempt {attempt} failed {url}: {e} (retry in {wait:.1f}s)",
                  file=sys.stderr)
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def html_to_text(html: str) -> str:
    text = re.sub(r"<\s*br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</\s*(p|li|div|h\d)\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&nbsp;", " ").replace("&#39;", "'")
                .replace("&rsquo;", "’").replace("&ldquo;", "“")
                .replace("&rdquo;", "”"))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_balanced_div(html: str, start: int) -> str:
    """Return the inner HTML of the <div> whose opening tag begins at `start`,
    matching nested <div>/</div> by depth so deeply-nested content isn't truncated."""
    open_end = html.index(">", start) + 1
    depth = 1
    i = open_end
    for m in re.finditer(r"<(/?)div\b[^>]*>", html[open_end:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            i = open_end + m.start()
            break
    return html[open_end:i]


def is_clean_variant(slug: str) -> bool:
    return (
        not any(k in slug for k in EXCLUDE_KEYWORDS)
        and not SINGLE_STAMP_RE.search(slug)
    )


def derive_animal(slug: str) -> str:
    m = re.match(r"(?:19|20)\d{2}-year-of-the-([a-z]+)", slug)
    if not m:
        return ""
    a = m.group(1)
    if a == "sheep":
        return "goat"  # normalise to a single canonical animal key
    return a if a in ANIMALS else a


def collect_sets(session: requests.Session) -> list[dict]:
    """Enumerate the product sitemap and pick one representative issue per year."""
    r = get(session, SITEMAP)
    urls = [m.group(1) for m in re.finditer(r"<loc>([^<]+)</loc>", r.text)]
    slugs = [
        u.replace(f"{BASE}/", "").rstrip("/")
        for u in urls
        if "year-of-the" in u.lower()
    ]

    by_year: dict[int, list[str]] = defaultdict(list)
    for slug in slugs:
        m = re.match(r"((?:19|20)\d{2})-year-of-the-[a-z]+", slug)
        if m:
            by_year[int(m.group(1))].append(slug)

    sets: list[dict] = []
    for year in sorted(by_year):
        year_slugs = by_year[year]
        animal = derive_animal(year_slugs[0])
        reps: list[tuple[str, str]] = []  # (slug, role)

        # 1. gummed set
        for s in year_slugs:
            if s.endswith("set-of-mint-stamps"):
                reps.append((s, "stamp_set"))
                break

        # 2. plain miniature sheet (prefer "mint miniature sheet")
        sheets = [
            s for s in year_slugs
            if "miniature-sheet" in s and is_clean_variant(s)
            and "first-day" not in s and "set-of" not in s
        ]
        pref = (
            [s for s in sheets if "mint-miniature-sheet" in s]
            or [s for s in sheets if re.fullmatch(
                rf"(?:19|20)\d{{2}}-year-of-the-[a-z]+-miniature-sheet", s)]
            or sheets
        )
        if pref:
            reps.append((pref[0], "miniature_sheet"))

        # 3. fallback: bare issue product (older years list a single product)
        if not reps:
            bare = [
                s for s in year_slugs
                if is_clean_variant(s)
                and "stamp" not in s and "sheet" not in s and "set-of" not in s
                and "tea" not in s
            ]
            exact = [
                s for s in bare
                if re.fullmatch(rf"(?:19|20)\d{{2}}-year-of-the-{animal}", s)
            ]
            chosen = exact[:1] or bare[:1]
            if chosen:
                reps.append((chosen[0], "issue"))

        if not reps:
            print(f"  ! {year}: no representative found among {len(year_slugs)} products",
                  file=sys.stderr)
            continue

        # Build records; suffix the miniature-sheet code so a year's two reps stay unique.
        for idx, (slug, role) in enumerate(reps):
            code = str(year) if (idx == 0 and role != "miniature_sheet") else f"{year}-ms"
            if role == "miniature_sheet" and len(reps) == 1:
                code = str(year)  # the sheet is the only rep -> own the bare year
            sets.append(
                {
                    "code": code,
                    "year": year,
                    "animal": animal,
                    "role": role,
                    "slug": slug,
                    "detail_url": f"{BASE}/{slug}/",
                }
            )
    return sets


def to_1280(url: str) -> str:
    """Rewrite a BigCommerce stencil image URL to the 1280x1280 render."""
    return re.sub(r"/stencil/[0-9wx]+/", "/stencil/1280x1280/", url)


def parse_detail(html: str) -> dict:
    """Extract title, sku, price, description and main-gallery images."""
    title = ""
    m = re.search(r'<h1[^>]*class="[^"]*productView-title[^"]*"[^>]*>(.*?)</h1>',
                  html, re.S)
    if m:
        title = clean(re.sub(r"<[^>]+>", "", m.group(1)))

    sku = ""
    m = re.search(r'"sku"\s*:\s*"([^"]+)"', html) or re.search(
        r"data-product-sku[^>]*>([^<]+)<", html)
    if m:
        sku = clean(m.group(1))

    # Price from the product info block (best-effort; some out-of-stock items lack it).
    price = ""
    m = re.search(r'class="productView-price">(.*?)</div>', html, re.S)
    if m:
        mp = re.search(r"\$[\d,]+\.\d{2}", m.group(1))
        if mp:
            price = mp.group(0)

    # Official stamp blurb lives in the description tab. Older imported pages nest
    # the text in field divs after a header image, so a fixed "</div></div>" cut
    # truncates them — extract the whole balanced <div id="tab-description"> block.
    description = ""
    m = re.search(r'<div[^>]*id="tab-description"[^>]*>', html)
    if m:
        description = html_to_text(extract_balanced_div(html, m.start()))

    # Main product gallery: the thumbnails carousel exposes each image's zoom URL.
    image_urls: list[str] = []
    m = re.search(r'<ul class="productView-thumbnails"[^>]*>(.*?)</ul>', html, re.S)
    if m:
        for z in re.findall(r'data-image-gallery-zoom-image-url="([^"]+)"', m.group(1)):
            u = to_1280(z)
            if u not in image_urls:
                image_urls.append(u)
    # Fallback: single-image products without a thumbnails carousel.
    if not image_urls:
        m = re.search(r'data-zoom-image="([^"]+)"', html)
        if m:
            image_urls.append(to_1280(m.group(1)))

    return {
        "page_title": title,
        "sku": sku,
        "price": price,
        "description": description,
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


def build_record(meta: dict, detail: dict, images: list[dict]) -> dict:
    return {
        "code": meta["code"],
        "year": meta["year"],
        "animal": meta["animal"],
        "role": meta["role"],
        "slug": meta["slug"],
        "detail_url": meta["detail_url"],
        "page_title": detail["page_title"],
        "sku": detail["sku"],
        "price": detail["price"],
        "description": detail["description"],
        "images": images,
        "n_images": len([i for i in images if i.get("image_file")]),
        "source": SOURCE,
    }


def scrape_set(session: requests.Session, meta: dict) -> dict:
    set_dir = OUT_DIR / meta["code"]
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    r = get(session, meta["detail_url"], timeout=60)
    (set_dir / "detail.html").write_text(r.text, encoding="utf-8")
    detail = parse_detail(r.text)

    images: list[dict] = []
    for url in detail["image_urls"]:
        fname = Path(urlparse(url).path).name
        img = {"image_url": url}
        if download(session, url, img_dir / fname):
            img["image_file"] = f"img/{fname}"
        images.append(img)
        time.sleep(DELAY)

    record = build_record(meta, detail, images)
    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def reparse_local() -> None:
    """Re-parse saved detail.html into raw.json without hitting the server."""
    for d in sorted(p for p in OUT_DIR.iterdir() if p.is_dir()):
        rawf, htmlf = d / "raw.json", d / "detail.html"
        if not rawf.exists() or not htmlf.exists():
            continue
        old = json.loads(rawf.read_text(encoding="utf-8"))
        detail = parse_detail(htmlf.read_text(encoding="utf-8"))
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
        meta = {k: old[k] for k in ("code", "year", "animal", "role", "slug", "detail_url")}
        record = build_record(meta, detail, images)
        rawf.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  reparsed {d.name}: desc={len(detail['description'])} chars, "
              f"{len(images)} images", file=sys.stderr)


def write_index(sets: list[dict]) -> None:
    idx = [
        {
            "code": s["code"],
            "year": s["year"],
            "animal": s["animal"],
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
                    help="re-parse saved detail.html into raw.json (no network)")
    args = ap.parse_args()

    if args.reparse_local:
        print("Re-parsing local detail.html files...", file=sys.stderr)
        reparse_local()
        print("Done.", file=sys.stderr)
        return

    session = make_session()
    print("Collecting zodiac issues from product sitemap...", file=sys.stderr)
    sets = collect_sets(session)
    print(f"Total representative issues: {len(sets)} "
          f"(years {sets[0]['year']}-{sets[-1]['year']})", file=sys.stderr)

    write_index(sets)

    if args.list_only:
        for s in sets:
            print(f"  {s['code']:8} {s['animal']:8} {s['role']:16} {s['slug']}")
        return

    for i, meta in enumerate(sets, 1):
        print(f"[{i}/{len(sets)}] {meta['code']} {meta['slug']}", file=sys.stderr)
        try:
            rec = scrape_set(session, meta)
            print(f"    images={rec['n_images']} desc={len(rec['description'])} chars "
                  f"sku={rec['sku']}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - keep going on a single issue failure
            print(f"    ! issue failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
