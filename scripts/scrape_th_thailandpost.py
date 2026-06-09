# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Scrape Thailand Post zodiac (Chinese New Year) stamp sets into data/raw/th-thailandpost/.

Thailand Post's own site is unreachable, so this is a reference-tier scrape
(source id `th-siamstamp`) stitched from two static third-party catalogues:

  - siamstamp.com  (recent: 2017-2026)
    Year nav:  index.php?year=YYYY  -> a table whose rows link to detail pages.
    Detail:    index.php?id=NNNN    -> fields table + images.
    Images:    stamp/YYYY/TH{YYYY}-{id}{KIND}.jpg  (ST=stamp, CO=cover, FST=full sheet).
    NOTE: its HTTPS cert is expired, so we go over http:// (and verify=False as a
    belt-and-braces fallback).

  - thailex.info   (early: 2003-2014, a complete 12-animal cycle)
    Static .htm pages under LEXICON/, one per "Zodiac - Year of the X (YYYY)".
    A "Full Series (2003-2014)" page enumerates them all. Image lives at a
    parallel THAILEXPICS/ path with the same descriptive filename.

We keep only the Chinese-zodiac issues (illustrated by Princess Maha Chakri
Sirindhorn). siamstamp's generic "New Year" stamps (Thai sweets, amulets, ...)
are NOT zodiac issues and are filtered out.

`code` = issue year (unique per set). 2015 and 2016 are absent from both sources
(gap between thailex's 2014 end and siamstamp's 2017 start); we record only what
the sources expose.

Each set -> data/raw/th-thailandpost/{code}/{raw.json, detail.html, img/*}

Usage:
    uv run scripts/scrape_th_thailandpost.py --list-only   # list sets, no download
    uv run scripts/scrape_th_thailandpost.py               # full scrape + images
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib3
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "th-thailandpost"
DELAY = 1.0  # polite delay between requests (seconds)
SOURCE = {"id": "th-siamstamp", "tier": "reference"}

SIAM_BASE = "http://www.siamstamp.com/catalogue/"
SIAM_YEARS = range(2017, 2027)  # 2017..2026 inclusive

THAILEX_BASE = "https://www.thailex.info/THAILEX/THAILEXENG/LEXICON/"
THAILEX_SERIES = (
    THAILEX_BASE
    + "Zodiac - Full Series (2003-2014) Thai Postage Stamp.htm"
)

ZODIAC = {
    "rat": "Rat", "mouse": "Rat", "ox": "Ox", "tiger": "Tiger",
    "rabbit": "Rabbit", "dragon": "Dragon", "snake": "Snake",
    "horse": "Horse", "goat": "Goat", "sheep": "Goat", "ram": "Goat",
    "monkey": "Monkey", "rooster": "Rooster", "cock": "Rooster",
    "dog": "Dog", "pig": "Pig", "boar": "Pig",
}

# siamstamp's expired cert makes requests warn loudly; we silence the warning
# since we deliberately fetch over http and pass verify=False as a fallback.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.verify = False
    return s


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("﻿", "")).strip()


def derive_zodiac(name: str) -> str:
    low = name.lower()
    for key, animal in ZODIAC.items():
        if re.search(rf"\b{key}\b", low):
            return animal
    return ""


def get(session: requests.Session, url: str, retries: int = 3) -> requests.Response:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=45)
            r.raise_for_status()
            return r
        except requests.RequestException as e:  # transient timeouts on siamstamp
            last = e
            if attempt < retries - 1:
                time.sleep(DELAY * (attempt + 2))
    raise last  # type: ignore[misc]


def download(session: requests.Session, url: str, dest: Path, retries: int = 3) -> bool:
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=90)
            r.raise_for_status()
            if not r.content:
                raise requests.RequestException("empty body")
            dest.write_bytes(r.content)
            return True
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(DELAY * (attempt + 2))
                continue
            print(f"    ! image failed {url}: {e}", file=sys.stderr)
    return False


# --------------------------------------------------------------------------- #
# siamstamp.com (2017-2026)
# --------------------------------------------------------------------------- #

def siam_collect(session: requests.Session) -> list[dict]:
    """One zodiac set per siamstamp year page (filter out generic New Year)."""
    sets: list[dict] = []
    for year in SIAM_YEARS:
        url = f"{SIAM_BASE}index.php?year={year}"
        try:
            r = get(session, url)
        except requests.RequestException as e:
            print(f"  ! siam year {year} failed: {e}", file=sys.stderr)
            time.sleep(DELAY)
            continue
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=re.compile(r"index\.php\?id=\d+")):
            name = clean(a.get_text())
            # Only the Chinese-zodiac issue, not generic "New Year ..." stamps.
            if "zodiac" not in name.lower():
                continue
            m = re.search(r"id=(\d+)", a["href"])
            if not m:
                continue
            sets.append(
                {
                    "src": "siamstamp",
                    "year": str(year),
                    "id": m.group(1),
                    "list_name": name,
                    "detail_url": urljoin(url, a["href"]),
                }
            )
            break  # one zodiac set per year
        time.sleep(DELAY)
    return sets


def siam_parse_detail(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # Fields table: <strong>Label :</strong></td><td>value</td>
    fields: dict[str, str] = {}
    for strong in soup.find_all("strong"):
        label = clean(strong.get_text()).rstrip(":").strip()
        if not label:
            continue
        td = strong.find_parent("td")
        val_td = td.find_next_sibling("td") if td else None
        if val_td is not None:
            value = clean(val_td.get_text())
            if value:
                fields[label] = value

    # Images: <img src="stamp/YYYY/TH...jpg">; collect with their nearby label.
    images: list[dict] = []
    seen: set[str] = set()
    for img in soup.find_all("img", src=re.compile(r"stamp/\d{4}/")):
        src = img.get("src", "")
        if src in seen:
            continue
        seen.add(src)
        images.append(
            {
                "image_url": urljoin(base_url, src),
                "caption": clean(img.get("alt")),
            }
        )
    return {"detail_fields": fields, "images": images}


def siam_scrape(session: requests.Session, meta: dict) -> dict:
    set_dir = OUT_DIR / meta["year"]
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    r = get(session, meta["detail_url"])
    r.encoding = "utf-8"
    (set_dir / "detail.html").write_text(r.text, encoding="utf-8")
    detail = siam_parse_detail(r.text, meta["detail_url"])

    n_ok = 0
    for im in detail["images"]:
        fname = Path(urlparse(im["image_url"]).path).name
        if download(session, im["image_url"], img_dir / fname):
            im["image_file"] = f"img/{fname}"
            n_ok += 1
        else:
            im["image_file"] = None
        time.sleep(DELAY)

    name = detail["detail_fields"].get("Issue Name", meta["list_name"])
    record = {
        "code": meta["year"],
        "source": SOURCE,
        "year": meta["year"],
        "zodiac": derive_zodiac(name),
        "title": name,
        "issue_date": detail["detail_fields"].get("Issue Date", ""),
        "siam_id": meta["id"],
        "detail_url": meta["detail_url"],
        "detail_fields": detail["detail_fields"],
        "images": detail["images"],
        "n_images": n_ok,
    }
    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


# --------------------------------------------------------------------------- #
# thailex.info (2003-2014)
# --------------------------------------------------------------------------- #

def thailex_collect(session: requests.Session) -> list[dict]:
    """Enumerate the 2003-2014 zodiac pages from the Full Series index."""
    r = get(session, THAILEX_SERIES)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    sets: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        href = unquote(a["href"])
        if "Zodiac - Year of the" not in href:
            continue
        m = re.search(r"\((\d{4})\)", href)
        if not m:
            continue
        year = m.group(1)
        sets.setdefault(
            year,
            {
                "src": "thailex",
                "year": year,
                "list_name": href.rsplit("/", 1)[-1].replace(".htm", ""),
                "detail_url": urljoin(THAILEX_BASE, a["href"]),
            },
        )
    return [sets[y] for y in sorted(sets)]


def thailex_parse_detail(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # The page renders the fields as inline "Label: value" text. Pull the main
    # content text and parse the known labels out of it.
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = clean(soup.get_text(" "))

    labels = [
        "Issue Name", "Thai Issue Name", "Issue Date", "Cause",
        "Catalogue Number", "Denomination", "Unused Value", "Used Value",
        "Thailex Collection", "Size", "Quantity of Stamps", "Printer",
        "Subject",
    ]
    pat = "|".join(re.escape(lbl) for lbl in labels)
    fields: dict[str, str] = {}
    for m in re.finditer(rf"({pat})\s*:\s*(.*?)(?=(?:{pat})\s*:|Related Link|$)", text):
        fields[m.group(1)] = clean(m.group(2))

    # The set image is the THAILEXPICS file with the page's descriptive name.
    images: list[dict] = []
    for img in soup.find_all("img", src=re.compile(r"THAILEXPICS", re.I)):
        images.append(
            {
                "image_url": urljoin(base_url, img.get("src", "")),
                "caption": clean(img.get("alt")),
            }
        )
    return {"detail_fields": fields, "images": images}


def thailex_scrape(session: requests.Session, meta: dict) -> dict:
    set_dir = OUT_DIR / meta["year"]
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    r = get(session, meta["detail_url"])
    r.encoding = "utf-8"
    (set_dir / "detail.html").write_text(r.text, encoding="utf-8")
    detail = thailex_parse_detail(r.text, meta["detail_url"])

    n_ok = 0
    for im in detail["images"]:
        fname = Path(unquote(urlparse(im["image_url"]).path)).name
        if download(session, im["image_url"], img_dir / fname):
            im["image_file"] = f"img/{fname}"
            n_ok += 1
        else:
            im["image_file"] = None
        time.sleep(DELAY)

    name = detail["detail_fields"].get("Issue Name", meta["list_name"])
    record = {
        "code": meta["year"],
        "source": SOURCE,
        "year": meta["year"],
        "zodiac": derive_zodiac(meta["list_name"]),
        "title": name,
        "title_th": detail["detail_fields"].get("Thai Issue Name", ""),
        "issue_date": detail["detail_fields"].get("Issue Date", ""),
        "detail_url": meta["detail_url"],
        "detail_fields": detail["detail_fields"],
        "images": detail["images"],
        "n_images": n_ok,
    }
    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="list sets, no download")
    args = ap.parse_args()

    session = make_session()

    print("Collecting thailex.info (2003-2014)...", file=sys.stderr)
    thailex_sets = thailex_collect(session)
    print(f"  thailex: {len(thailex_sets)} sets", file=sys.stderr)

    print("Collecting siamstamp.com (2017-2026)...", file=sys.stderr)
    siam_sets = siam_collect(session)
    print(f"  siamstamp: {len(siam_sets)} sets", file=sys.stderr)

    all_sets = sorted(thailex_sets + siam_sets, key=lambda m: m["year"])

    if args.list_only:
        for m in all_sets:
            print(f"  {m['year']}  [{m['src']:9}] "
                  f"{derive_zodiac(m['list_name']) or '?':8} {m['list_name']}")
        print(f"Total: {len(all_sets)} sets", file=sys.stderr)
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
    for i, meta in enumerate(all_sets, 1):
        print(f"[{i}/{len(all_sets)}] {meta['year']} [{meta['src']}] {meta['list_name']}",
              file=sys.stderr)
        try:
            if meta["src"] == "siamstamp":
                rec = siam_scrape(session, meta)
            else:
                rec = thailex_scrape(session, meta)
        except Exception as e:  # noqa: BLE001 - keep going on a single set failure
            print(f"    ! set failed: {e}", file=sys.stderr)
            time.sleep(DELAY)
            continue
        print(f"    code={rec['code']} zodiac={rec['zodiac'] or '?'} "
              f"{rec['n_images']} imgs", file=sys.stderr)
        index.append(
            {
                "code": rec["code"],
                "year": rec["year"],
                "zodiac": rec["zodiac"],
                "title": rec["title"],
                "issue_date": rec["issue_date"],
                "source_site": meta["src"],
                "n_images": rec["n_images"],
                "detail_url": rec["detail_url"],
            }
        )
        time.sleep(DELAY)

    index.sort(key=lambda x: x["code"])
    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Done. {len(index)} sets -> {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
