# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Scrape Vietnam Post / Vietnam Stamp Company (con giáp / Tết) zodiac stamp sets.

Source: https://vietnamstamp.com.vn/ (static PHP, product `.html` slugs).
tier=official, source id `vn-vietnamstamp`. Lands into data/raw/vn-vietnampost/{code}/.

Vietnamese zodiac specialty is recorded faithfully in raw.json `animal`:
the Cat (Mèo) replaces the Rabbit (Mão years), the Water Buffalo (Trâu)
replaces the Ox (Sửu years).

Product slugs are discovered via the site search (`/tim?q=...`). Each product
page (`/{slug}.html`) is a single stamp-set detail page:
  - title:   h1.product-name-detail
  - set code (Mã bộ): in .product-code-detail
  - fields:  table.tbl-summary-detail (issue date, stamps/set, size, designer, ...)
  - desc:    #tab1 rich text
  - images:  main #img-large a.MagicZoom[href], .product-slider .item a[href]
             (full-res via href; the visible img src are 120_ thumbs) and the
             stamp scans embedded in #tab1 img[src] (/media/lib/...).
We take image URLs from the page's actual links/src (never guessed/cached).

Each set -> data/raw/vn-vietnampost/{code}/{raw.json, detail.html, img/*}

Usage:
    uv run scripts/scrape_vn_vietnampost.py --list-only   # discover & print slugs
    uv run scripts/scrape_vn_vietnampost.py               # full scrape + images
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

BASE = "https://vietnamstamp.com.vn/"
SEARCH = urljoin(BASE, "tim")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "vn-vietnampost"
DELAY = 1.0  # polite delay between requests (seconds)
SOURCE = {"id": "vn-vietnamstamp", "tier": "official"}

# Search terms that surface Tết / con giáp products on the static site.
SEARCH_TERMS = ["tet", "con giap", "12 con giap", "giap ngo", "tem tet"]

# Vietnamese lunar-year second word (chi / earthly branch) -> zodiac animal.
# Vietnam swaps two animals vs. the Chinese zodiac:
#   Mão -> Cat (Mèo), not Rabbit;  Sửu -> Water Buffalo (Trâu), not Ox.
BRANCH_ANIMAL = {
    "Tý": {"branch": "Tý", "animal": "鼠/Chuột", "en": "Rat"},
    "Sửu": {"branch": "Sửu", "animal": "水牛/Trâu", "en": "Water Buffalo", "vn_special": True},
    "Dần": {"branch": "Dần", "animal": "虎/Hổ", "en": "Tiger"},
    "Mão": {"branch": "Mão", "animal": "貓/Mèo", "en": "Cat", "vn_special": True},
    "Mẹo": {"branch": "Mão", "animal": "貓/Mèo", "en": "Cat", "vn_special": True},
    "Thìn": {"branch": "Thìn", "animal": "龍/Rồng", "en": "Dragon"},
    "Tỵ": {"branch": "Tỵ", "animal": "蛇/Rắn", "en": "Snake"},
    "Tị": {"branch": "Tỵ", "animal": "蛇/Rắn", "en": "Snake"},
    "Ngọ": {"branch": "Ngọ", "animal": "馬/Ngựa", "en": "Horse"},
    "Mùi": {"branch": "Mùi", "animal": "羊/Dê", "en": "Goat"},
    "Thân": {"branch": "Thân", "animal": "猴/Khỉ", "en": "Monkey"},
    "Dậu": {"branch": "Dậu", "animal": "雞/Gà", "en": "Rooster"},
    "Tuất": {"branch": "Tuất", "animal": "狗/Chó", "en": "Dog"},
    "Hợi": {"branch": "Hợi", "animal": "豬/Lợn", "en": "Pig"},
}


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("﻿", "")).strip()


def discover_slugs(session: requests.Session) -> list[str]:
    """Find Tết / con giáp product slugs via the site search."""
    slugs: dict[str, None] = {}
    pat = re.compile(r"^/((?:tet|tem-tet)[a-z0-9-]*)\.html$")
    for term in SEARCH_TERMS:
        r = session.get(SEARCH, params={"q": term}, timeout=30)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        found = 0
        for a in soup.find_all("a", href=pat):
            m = pat.match(a["href"])
            if m:
                slugs.setdefault(m.group(1), None)
                found += 1
        print(f"  search '{term}': {found} tet-links (cumulative {len(slugs)})", file=sys.stderr)
        time.sleep(DELAY)
    return list(slugs)


def derive_zodiac(title: str) -> dict:
    """Map a Tết title (e.g. 'Tết Quý Mão') to its zodiac animal."""
    words = clean(title).split()
    info: dict = {"branch": "", "animal": "", "animal_en": "", "vn_special": False}
    for w in reversed(words):  # earthly branch is the last word
        key = w.strip(".,")
        if key in BRANCH_ANIMAL:
            d = BRANCH_ANIMAL[key]
            info["branch"] = d["branch"]
            info["animal"] = d["animal"]
            info["animal_en"] = d["en"]
            info["vn_special"] = d.get("vn_special", False)
            break
    return info


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.select_one("h1.product-name-detail")
    title = clean(h1.get_text()) if h1 else ""

    # Set code "Mã bộ : 1167"
    set_code = ""
    code_el = soup.select_one(".product-code-detail")
    if code_el:
        m = re.search(r"M[ãa]\s*bộ\s*:\s*(\d+)", clean(code_el.get_text()))
        if m:
            set_code = m.group(1)

    # Summary field table
    fields: dict[str, str] = {}
    for tr in soup.select("table.tbl-summary-detail tr"):
        tds = tr.find_all("td")
        if len(tds) >= 2:
            label = clean(tds[0].get_text())
            value = clean(tds[1].get_text()).lstrip(":").strip()
            if label:
                fields[label] = value

    # Description rich text (#tab1)
    tab1 = soup.select_one("#tab1")
    description = clean(tab1.get_text(" ")) if tab1 else ""

    # Images: prefer full-res hrefs over the visible 120_ thumbnails.
    image_urls: list[str] = []
    seen: set[str] = set()

    def add(url: str | None) -> None:
        if not url:
            return
        full = urljoin(BASE, url.strip())
        if full not in seen:
            seen.add(full)
            image_urls.append(full)

    main = soup.select_one("#img-large a.MagicZoom")
    if main and main.get("href"):
        add(main["href"])
    for a in soup.select(".product-slider .item a[href]"):
        add(a["href"])  # href = full-res; child img src = 120_ thumb
    if tab1:
        for img in tab1.select("img[src]"):  # /media/ stamp scans only
            src = img.get("src", "")
            if "/media/" in src:  # skip off-site junk (e.g. fbcdn emoji)
                add(src)

    return {
        "title": title,
        "set_code": set_code,
        "detail_fields": fields,
        "description": description,
        "image_urls": image_urls,
    }


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def parse_issue_date(fields: dict) -> tuple[str, str]:
    """Return (issue_date dd/mm/yyyy, year YYYY) from the field table."""
    for label, value in fields.items():
        if "phát hành" in label.lower() or "phat hanh" in label.lower():
            m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
            if m:
                return value, m.group(3)
    return "", ""


def scrape_set(session: requests.Session, slug: str) -> dict | None:
    url = urljoin(BASE, f"{slug}.html")
    r = session.get(url, timeout=30)
    r.encoding = "utf-8"
    if r.status_code != 200:
        print(f"    ! HTTP {r.status_code} for {url}", file=sys.stderr)
        return None
    detail = parse_detail(r.text)

    issue_date, issue_year = parse_issue_date(detail["detail_fields"])
    zodiac = derive_zodiac(detail["title"])
    # code: prefer issue year (unique per Tết set); fall back to set_code/slug.
    code = issue_year or detail["set_code"] or slug

    set_dir = OUT_DIR / code
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    (set_dir / "detail.html").write_text(r.text, encoding="utf-8")

    images: list[dict] = []
    for u in detail["image_urls"]:
        fname = Path(urlparse(u).path).name
        ok = download(session, u, img_dir / fname)
        images.append({"image_url": u, "image_file": f"img/{fname}" if ok else None})
        time.sleep(DELAY)

    record = {
        "code": code,
        "source": SOURCE,
        "slug": slug,
        "detail_url": url,
        "title": detail["title"],
        "set_code": detail["set_code"],
        "issue_date": issue_date,
        "year": issue_year,
        "zodiac": zodiac,
        "detail_fields": detail["detail_fields"],
        "description": detail["description"],
        "images": images,
        "n_images": sum(1 for im in images if im["image_file"]),
    }
    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="only discover & print slugs")
    args = ap.parse_args()

    session = make_session()
    print("Discovering Tết / con giáp product slugs...", file=sys.stderr)
    slugs = discover_slugs(session)
    print(f"Total slugs: {len(slugs)}", file=sys.stderr)

    if args.list_only:
        for s in slugs:
            print(f"  {s}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
    for i, slug in enumerate(slugs, 1):
        print(f"[{i}/{len(slugs)}] {slug}", file=sys.stderr)
        try:
            rec = scrape_set(session, slug)
        except Exception as e:  # noqa: BLE001 - keep going on a single set failure
            print(f"    ! set failed: {e}", file=sys.stderr)
            rec = None
        if rec:
            z = rec["zodiac"]
            flag = " [VN-special]" if z.get("vn_special") else ""
            print(
                f"    {rec['title']} | year={rec['year']} | "
                f"{z['animal']} ({z['animal_en']}){flag} | {rec['n_images']} imgs",
                file=sys.stderr,
            )
            index.append(
                {
                    "code": rec["code"],
                    "slug": rec["slug"],
                    "title": rec["title"],
                    "year": rec["year"],
                    "issue_date": rec["issue_date"],
                    "set_code": rec["set_code"],
                    "animal": z["animal"],
                    "animal_en": z["animal_en"],
                    "branch": z["branch"],
                    "vn_special": z.get("vn_special", False),
                    "n_images": rec["n_images"],
                    "detail_url": rec["detail_url"],
                }
            )
        time.sleep(DELAY)

    index.sort(key=lambda x: x["year"] or "")
    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Done. {len(index)} sets -> {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
