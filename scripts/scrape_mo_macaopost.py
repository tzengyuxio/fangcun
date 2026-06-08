# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Scrape Macao zodiac stamps into data/raw/mo-macaopost/.

Source: Communications Museum of Macao (通訊博物館) zodiac special site
`https://www.cmm.gov.mo/special/zodiac/eng/{n}_{animal}.html` (tier=reference,
source id "mo-cmm"). 12 animal pages, one per zodiac sign.

IMPORTANT — this is an EDITORIAL comparison site, not a per-set catalog. Each
animal page shows zodiac stamps from MANY postal authorities (China, Vietnam,
Korea, La Poste, Mongolia, NZ, Hongkong Post, CTT Macao, Canada, Christmas
Island, Singapore, ...). Images carry empty alt text; the only country signal is
the explanatory <p> sitting in the same Bootstrap `.row` as the images. We
therefore:
  - download ALL images per page (raw-everything principle), and
  - for each image attach the associated paragraph text + a `macau_likely` flag
    (true when that paragraph mentions Macao / CTT) so a human can filter CTT's
    own stamps at the curation stage.

Each animal -> data/raw/mo-macaopost/{animal}/{raw.json, page_eng.html, img/*}
where {animal} = "rat", "ox", ... (unique, derived from the page filename).

Usage:
    uv run scripts/scrape_mo_macaopost.py --list-only   # collect & print the 12 pages
    uv run scripts/scrape_mo_macaopost.py               # full scrape (pages + images)
    uv run scripts/scrape_mo_macaopost.py --reparse-local  # re-parse saved HTML (no network)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.cmm.gov.mo/special/zodiac/"
LANG = "eng"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "mo-macaopost"
DELAY = 1.0  # polite delay between requests (seconds)
SOURCE = {"id": "mo-cmm", "tier": "reference"}

# 12 zodiac pages: "{n}_{animal}.html". Order/spelling per the site's own nav.
ANIMALS = [
    (1, "rat"), (2, "ox"), (3, "tiger"), (4, "rabbit"),
    (5, "dragon"), (6, "snake"), (7, "horse"), (8, "sheep"),
    (9, "monkey"), (10, "rooster"), (11, "dog"), (12, "pig"),
]
# Phrases in a paragraph that flag the adjacent images as CTT Macao's own stamps.
MACAU_MARKERS = ("CTT Macao", "Macao", "Macau")
# Tiny error page the server returns for missing image paths (~1.2 KB).
IMG_404_MAX = 2000


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("﻿", "")).strip()


def fetch_html(session: requests.Session, url: str) -> str:
    r = session.get(url, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def parse_page(html: str, page_url: str) -> dict:
    """Extract intro text and the per-image country-association from one page."""
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("div.col-lg-8 h1")
    title = clean(title_el.get_text()) if title_el else ""

    # First paragraph after H1 is the generic animal symbolism intro.
    intro = ""
    if title_el:
        p = title_el.find_next("p")
        if p:
            intro = clean(p.get_text())

    images: list[dict] = []
    seen: set[str] = set()
    # All stamp images live in the central content column `col-lg-8` (the
    # col-lg-2 side columns hold only the zodiac nav buttons). Page layouts vary
    # a lot: some wrap each country's images + paragraph in their own `.row`,
    # some cram everything as flat siblings in one `.row`, and some (e.g. dragon)
    # drop most images directly into `col-lg-8` with no inner row at all. So we
    # ignore row structure entirely and walk the content column's descendants in
    # document order, attaching to each <img> the nearest PRECEDING <p>. The
    # country signal is always in that prose (alt text is empty), so
    # `macau_likely` is set when the chosen caption mentions Macao / CTT.
    content = soup.select_one("div.col-lg-8")
    if content is None:
        return {"title": title, "intro": intro, "images": images}
    last_para = ""
    for el in content.descendants:
        name = getattr(el, "name", None)
        if name == "p":
            last_para = clean(el.get_text())
            continue
        if name != "img":
            continue
        src = el.get("src", "")
        if "/images/" not in src or not re.search(r"/\d+_", src):
            continue
        url = urljoin(page_url, src)
        if url in seen:
            continue
        seen.add(url)
        images.append(
            {
                "image_url": url,
                "caption": last_para,
                "macau_likely": any(m in last_para for m in MACAU_MARKERS),
            }
        )
    return {"title": title, "intro": intro, "images": images}


def probe_extra_images(session: requests.Session, n: int, animal: str, known: set[str]) -> list[dict]:
    """Probe sequential imageNNN.{jpg,png} past those referenced in the HTML.

    The HTML usually references every image, but the research notes say files
    increment "until 404", so we keep going a few indices past the max-known to
    catch any unreferenced extras. Country attribution is unknown for these.
    """
    img_base = f"{BASE}images/{n}_{animal}/"
    known_names = {Path(urlparse(u).path).name for u in known}
    nums = [int(m.group(1)) for u in known_names if (m := re.search(r"image(\d+)", u))]
    start = (max(nums) + 1) if nums else 1
    extras: list[dict] = []
    misses = 0
    idx = start
    while misses < 3 and idx <= start + 30:
        found = False
        for ext in ("jpg", "png"):
            name = f"image{idx:03d}.{ext}"
            if name in known_names:
                found = True
                break
            url = img_base + name
            try:
                r = session.get(url, timeout=30)
            except requests.RequestException:
                continue
            if r.status_code == 200 and len(r.content) > IMG_404_MAX:
                extras.append(
                    {
                        "image_url": url,
                        "caption": "",
                        "macau_likely": False,
                        "_content": r.content,  # carry bytes so we don't refetch
                    }
                )
                found = True
                break
            time.sleep(DELAY)
        misses = 0 if found else misses + 1
        idx += 1
    return extras


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=60)
        r.raise_for_status()
        if len(r.content) <= IMG_404_MAX:
            print(f"    ! skip (looks like 404 page) {url}", file=sys.stderr)
            return False
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def scrape_page(session: requests.Session, meta: dict) -> dict:
    n, animal = meta["index"], meta["animal"]
    set_dir = OUT_DIR / animal
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    html = fetch_html(session, meta["page_url"])
    (set_dir / f"page_{LANG}.html").write_text(html, encoding="utf-8")
    parsed = parse_page(html, meta["page_url"])

    known = {im["image_url"] for im in parsed["images"]}
    time.sleep(DELAY)
    extras = probe_extra_images(session, n, animal, known)
    parsed["images"].extend(extras)

    n_img = 0
    n_macau = 0
    for im in parsed["images"]:
        fname = Path(urlparse(im["image_url"]).path).name
        cached = im.pop("_content", None)
        dest = img_dir / fname
        if cached is not None:
            dest.write_bytes(cached)
            ok = True
        else:
            ok = download(session, im["image_url"], dest)
            time.sleep(DELAY)
        if ok:
            im["image_file"] = f"img/{fname}"
            n_img += 1
            if im["macau_likely"]:
                n_macau += 1

    record = {
        **meta,
        "title": parsed["title"],
        "intro": parsed["intro"],
        "images": parsed["images"],
        "n_images": n_img,
        "n_macau_likely": n_macau,
        "source": SOURCE,
    }
    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def build_index() -> list[dict]:
    return [
        {
            "code": animal,
            "animal": animal,
            "index": n,
            "page_url": f"{BASE}{LANG}/{n}_{animal}.html",
        }
        for n, animal in ANIMALS
    ]


def reparse_local() -> None:
    for d in sorted(p for p in OUT_DIR.iterdir() if p.is_dir()):
        rawf = d / "raw.json"
        htmlf = d / f"page_{LANG}.html"
        if not rawf.exists() or not htmlf.exists():
            continue
        old = json.loads(rawf.read_text(encoding="utf-8"))
        parsed = parse_page(htmlf.read_text(encoding="utf-8"), old["page_url"])
        # preserve already-resolved image_file paths by filename
        prev = {
            Path(urlparse(im["image_url"]).path).name: im.get("image_file")
            for im in old.get("images", [])
        }
        n_macau = 0
        for im in parsed["images"]:
            fname = Path(urlparse(im["image_url"]).path).name
            if prev.get(fname):
                im["image_file"] = prev[fname]
            if im["macau_likely"]:
                n_macau += 1
        meta = {k: old[k] for k in ("code", "animal", "index", "page_url") if k in old}
        record = {
            **meta,
            "title": parsed["title"],
            "intro": parsed["intro"],
            "images": parsed["images"],
            "n_images": old.get("n_images", 0),
            "n_macau_likely": n_macau,
            "source": SOURCE,
        }
        rawf.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"  reparsed {d.name}: {len(parsed['images'])} imgs, {n_macau} macau-likely",
            file=sys.stderr,
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="only collect & print the page list")
    ap.add_argument("--reparse-local", action="store_true", help="re-parse saved HTML (no network)")
    args = ap.parse_args()

    if args.reparse_local:
        print("Re-parsing local HTML files...", file=sys.stderr)
        reparse_local()
        print("Done.", file=sys.stderr)
        return

    index = build_index()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.list_only:
        for s in index:
            print(f"  {s['code']:10} {s['page_url']}")
        return

    session = make_session()
    for i, meta in enumerate(index, 1):
        print(f"[{i}/{len(index)}] {meta['code']} {meta['page_url']}", file=sys.stderr)
        try:
            rec = scrape_page(session, meta)
            print(
                f"    {rec['n_images']} images ({rec['n_macau_likely']} macau-likely)",
                file=sys.stderr,
            )
        except Exception as e:  # noqa: BLE001 - keep going on a single page failure
            print(f"    ! page failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
