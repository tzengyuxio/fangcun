# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Scrape Christmas Island (Australia Post) zodiac stamp sets into data/raw/cx-christmasisland/.

Source: Australia Post Collectables (AEM), tier=official, id=cx-auspost.
    https://collectables.auspost.com.au/stamp-issues/view-all-stamp-issues

The "view all stamp issues" listing is an AEM page-card-listing component whose "Load
more" button is JS-driven: the client fetches successive HTML fragments via the
selector-based endpoint

    /stamp-issues/view-all-stamp-issues.offset{N}.html   (20 items per page)

(discovered in clientlib-site.js: `await T(`${h}.offset${e}`)`). The whole catalogue
(~435 issues) is walked in steps of 20 to harvest every detail slug, then filtered to
Christmas Island Lunar New Year / zodiac issues. Slugs are read from the list, never
hardcoded, because they are irregular (2014 is misspelled "chirstmas", and 2016/2026
drop the "christmas-island" prefix).

Detail pages (e.g. /stamp-issues/view-all-stamp-issues/{slug}) are static and direct.
The main stamp gallery images are Adobe Dynamic Media assets

    https://collectables.auspost.com.au/adobe/dynamicmedia/deliver/dm-aid--{UUID}/{file}.png?quality=85

identified by their `data-cmp-filereference` DAM folder (stamp-releases-{YEAR} /
stamp-issues-{YEAR}/...), which lets us keep this issue's own images and drop the
"you may also like" cross-sell cards that always reference other years' folders.
The technical spec table (issue date, denominations, designer, printer, FDI postmark
"Christmas Island WA 6798", etc.) is parsed too.

code = lunar year (e.g. "2024"), unique per issue.

Each set -> data/raw/cx-christmasisland/{code}/{raw.json, detail.html, img/*.png}
Plus a top-level _index.json. Images are .gitignored (kept locally).

Usage:
    uv run scripts/scrape_cx_christmasisland.py --list-only      # collect & print the list
    uv run scripts/scrape_cx_christmasisland.py                  # full scrape (detail + images)
    uv run scripts/scrape_cx_christmasisland.py --reparse-local  # re-parse saved detail.html
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

BASE = "https://collectables.auspost.com.au"
LIST_PATH = "/stamp-issues/view-all-stamp-issues"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "cx-christmasisland"
DELAY = 1.0  # polite delay between requests (seconds)
PAGE_STEP = 20  # AEM page-card-listing items per offset page
MAX_OFFSET = 2000  # safety bound when walking offset pages
SOURCE = {"id": "cx-auspost", "tier": "official"}

# A Christmas Island zodiac issue is a stamp issue whose slug names a zodiac animal
# (or "lunar-new-year") AND is confirmed to be a Christmas Island release. Slugs are
# irregular, so we match on the animal/lunar keyword and then verify by year folder /
# FDI postmark on the detail page.
ZODIAC_ANIMALS = (
    "rat", "ox", "tiger", "rabbit", "dragon", "snake",
    "horse", "goat", "sheep", "ram", "monkey", "rooster", "dog", "pig", "boar",
)
ZODIAC_RE = re.compile(
    r"year-of-the-(?:" + "|".join(ZODIAC_ANIMALS) + r")|lunar-new-year",
    re.IGNORECASE,
)
DM_IMG_RE = re.compile(r"(dm-aid--[a-f0-9-]+/[^\"?]+\.(?:png|jpg|jpeg))", re.IGNORECASE)
YEAR_RE = re.compile(r"(20[0-9]{2})")


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("﻿", "").replace("\xa0", " ")).strip()


def fetch(session: requests.Session, url: str) -> requests.Response:
    r = session.get(url, timeout=60, allow_redirects=True)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r


# --------------------------------------------------------------------------- listing


def parse_list_page(html: str) -> list[dict]:
    """Extract one entry per card in the page-card-listing."""
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    for card in soup.select(".card-link[data-url]"):
        href = card.get("data-url", "")
        if not href.startswith(LIST_PATH + "/"):
            continue
        slug = href.rsplit("/", 1)[-1]
        article = card.find_parent("article") or card.parent
        title = ""
        title_node = article.select_one(".card-title") if article else None
        if title_node:
            title = clean(title_node.get_text())
        items.append({"slug": slug, "title": title, "detail_url": urljoin(BASE, href)})
    return items


def collect_slugs(session: requests.Session) -> list[dict]:
    """Walk the offset-paginated listing and return every stamp-issue entry."""
    seen: dict[str, dict] = {}
    offset = 0
    while offset <= MAX_OFFSET:
        url = f"{BASE}{LIST_PATH}.offset{offset}.html"
        r = fetch(session, url)
        page = parse_list_page(r.text)
        if not page:
            break
        for it in page:
            seen.setdefault(it["slug"], it)
        print(
            f"  offset {offset}: {len(page)} items (cumulative {len(seen)})",
            file=sys.stderr,
        )
        if len(page) < PAGE_STEP:
            break  # last page
        offset += PAGE_STEP
        time.sleep(DELAY)
    return list(seen.values())


def filter_zodiac(items: list[dict]) -> list[dict]:
    """Keep zodiac/Lunar New Year issues. (Christmas Island confirmation happens on
    the detail page via the FDI postmark / DAM year folder.)"""
    out = []
    for it in items:
        if ZODIAC_RE.search(it["slug"]):
            out.append(it)
    return out


# ---------------------------------------------------------------------------- detail


def parse_spec_table(soup: BeautifulSoup) -> dict[str, str]:
    """The single <table> on the page is the technical-details spec table."""
    fields: dict[str, str] = {}
    table = soup.find("table")
    if not table:
        return fields
    for tr in table.find_all("tr"):
        cells = [clean(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if len(cells) >= 2:
            fields[cells[0]] = " / ".join(cells[1:])
    return fields


def parse_gallery(soup: BeautifulSoup, year: str) -> list[dict]:
    """Collect this issue's own stamp images.

    Each <img>-bearing element carries data-cmp-filereference pointing at its DAM
    path, e.g. /content/dam/collectables/stamp-issues-2024/<issue>/<file>.png. The
    issue's own assets live under stamp-(releases|issues)-{YEAR}/...; "you may also
    like" cross-sell cards reference other years' folders, so filtering by the
    page's own year keeps the real gallery and drops the noise.
    """
    images: dict[str, dict] = {}
    for el in soup.select("[data-cmp-filereference][data-cmp-src]"):
        fref = el.get("data-cmp-filereference", "")
        src = el.get("data-cmp-src", "")
        m = DM_IMG_RE.search(src)
        if not m:
            continue
        # Folder must belong to this issue's release year. Newer pages use
        # stamp-(releases|issues)-{YEAR}/...; older/sparser pages (e.g. 2016) only
        # carry a single hero asset under stamp-issue-stamp-hero/{YEAR}.
        own_year = (
            re.search(rf"stamp-(?:releases|issues)-{year}\b", fref)
            or re.search(rf"stamp-issue-stamp-hero/{year}\b", fref)
        )
        if not own_year:
            continue
        rel = m.group(1)
        full = urljoin(BASE, f"/adobe/dynamicmedia/deliver/{rel}?quality=85")
        if rel in images:
            continue
        alt = clean(el.get("alt") or el.get("data-cmp-alt") or "")
        images[rel] = {
            "image_url": full,
            "filereference": fref,
            "alt": alt,
        }
    return list(images.values())


def parse_descriptions(soup: BeautifulSoup) -> list[str]:
    descs: list[str] = []
    md = soup.find("meta", attrs={"name": "description"})
    if md and md.get("content"):
        descs.append(clean(md["content"]))
    for el in soup.select(".rich-text.card-description"):
        t = clean(el.get_text(" "))
        if len(t) > 40 and t not in descs:
            descs.append(t)
    return descs


def parse_detail(html: str, year: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = clean(h1.get_text()) if h1 else ""
    spec = parse_spec_table(soup)
    images = parse_gallery(soup, year)
    descriptions = parse_descriptions(soup)
    return {
        "title": title,
        "spec": spec,
        "issue_date": spec.get("Issue date", ""),
        "fdi_postmark": spec.get("FDI postmark", ""),
        "descriptions": descriptions,
        "images": images,
    }


# ----------------------------------------------------------------------------- io


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=120)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def scrape_set(session: requests.Session, meta: dict) -> dict:
    year = meta["code"]
    set_dir = OUT_DIR / year
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    r = fetch(session, meta["detail_url"])
    (set_dir / "detail.html").write_text(r.text, encoding="utf-8")
    detail = parse_detail(r.text, year)

    for img in detail["images"]:
        fname = Path(urlparse(img["image_url"]).path).name
        if download(session, img["image_url"], img_dir / fname):
            img["image_file"] = f"img/{fname}"
        time.sleep(DELAY)

    record = {
        "code": year,
        "slug": meta["slug"],
        "list_title": meta.get("title", ""),
        "detail_url": meta["detail_url"],
        **detail,
        "n_images": len(detail["images"]),
        "source": SOURCE,
    }
    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def reparse_local() -> None:
    """Re-parse already-downloaded detail.html into raw.json without hitting the server."""
    dirs = sorted(p for p in OUT_DIR.iterdir() if p.is_dir())
    for d in dirs:
        rawf, htmlf = d / "raw.json", d / "detail.html"
        if not rawf.exists() or not htmlf.exists():
            continue
        old = json.loads(rawf.read_text(encoding="utf-8"))
        year = old["code"]
        detail = parse_detail(htmlf.read_text(encoding="utf-8"), year)
        img_map = {
            Path(urlparse(s["image_url"]).path).name: s.get("image_file")
            for s in old.get("images", [])
        }
        for s in detail["images"]:
            fname = Path(urlparse(s["image_url"]).path).name
            if img_map.get(fname):
                s["image_file"] = img_map[fname]
        record = {
            "code": year,
            "slug": old.get("slug", ""),
            "list_title": old.get("list_title", ""),
            "detail_url": old.get("detail_url", ""),
            **detail,
            "n_images": len(detail["images"]),
            "source": SOURCE,
        }
        rawf.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  reparsed {d.name}: {len(detail['images'])} images", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="only collect & print the set list")
    ap.add_argument(
        "--reparse-local",
        action="store_true",
        help="re-parse saved detail.html into raw.json (no network)",
    )
    args = ap.parse_args()

    if args.reparse_local:
        print("Re-parsing local detail.html files...", file=sys.stderr)
        reparse_local()
        print("Done.", file=sys.stderr)
        return

    session = make_session()
    print("Walking offset-paginated listing...", file=sys.stderr)
    all_items = collect_slugs(session)
    print(f"Total stamp issues in catalogue: {len(all_items)}", file=sys.stderr)

    zodiac = filter_zodiac(all_items)
    # Assign code = lunar year from the slug; keep one entry per year (latest wins).
    sets: dict[str, dict] = {}
    for it in zodiac:
        m = YEAR_RE.search(it["slug"])
        if not m:
            print(f"  ! no year in slug, skipping: {it['slug']}", file=sys.stderr)
            continue
        it["code"] = m.group(1)
        sets[it["code"]] = it
    ordered = [sets[k] for k in sorted(sets)]
    print(f"Christmas Island zodiac issues: {len(ordered)}", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "_index.json").write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.list_only:
        for s in ordered:
            print(f"  {s['code']}  {s['slug']:55}  {s.get('title','')}")
        return

    for i, meta in enumerate(ordered, 1):
        print(f"[{i}/{len(ordered)}] {meta['code']} {meta['slug']}", file=sys.stderr)
        try:
            rec = scrape_set(session, meta)
            print(
                f"    {rec['n_images']} images | issue_date={rec['issue_date']!r}"
                f" | fdi={rec['fdi_postmark']!r}",
                file=sys.stderr,
            )
        except Exception as e:  # noqa: BLE001 - keep going on a single set failure
            print(f"    ! set failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
