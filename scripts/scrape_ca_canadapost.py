# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Scrape Canada Post (Postes Canada) zodiac stamps into data/raw/ca-canadapost/.

Canada Post's own site only offers combined cycle/booklet imagery, so we use
postagestampguide.com (a static, image-direct catalogue) as a reference source
(tier=reference, id=ca-postagestampguide). Cross-check against the official
canadapost-postescanada.ca cycle pages where needed.

Series page lists all 58 individual stamps (two cycles, 1997-2021):
    https://postagestampguide.com/canada/stamps/series/1465/chinese-new-year
Each grid item links to a detail page:
    /canada/stamps/{ID}/{slug}
Detail page carries a `table.red-table` of <td><b>label</b></td><td>value</td>
spec rows (Date of Issue, Year, Quantity, Denomination, Perforation, Printer ...),
an "About Stamp" prose block, plus the full-size image at:
    https://images.postagestampguide.com/images/{ID}/{slug}.jpg

Each stamp -> data/raw/ca-canadapost/{code}/{raw.json, detail.html, img/*.jpg}
code is the issue year; when a year has more than one stamp (domestic vs.
international, or the 2021 retrospective singles) it is suffixed with the
postagestampguide stamp ID to stay unique. Plus a top-level _index.json.

Usage:
    uv run scripts/scrape_ca_canadapost.py --list-only      # collect & print the list
    uv run scripts/scrape_ca_canadapost.py                  # full scrape (detail + images)
    uv run scripts/scrape_ca_canadapost.py --reparse-local  # re-parse saved detail.html
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://postagestampguide.com"
SERIES_URL = f"{BASE}/canada/stamps/series/1465/chinese-new-year"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "ca-canadapost"
DELAY = 1.0  # polite delay between requests (seconds)
MAX_RETRIES = 3
SOURCE = {"id": "ca-postagestampguide", "tier": "reference"}

SPEC_LABELS = {
    "Date of Issue": "issue_date",
    "Year": "year",
    "Quantity": "quantity",
    "Denomination": "denomination",
    "Perforation or Dimension": "perforation_or_dimension",
    "Series": "series",
    "Series Time Span": "series_time_span",
    "Printer": "printer",
    "Postal Administration": "postal_administration",
    "Designer": "designer",
}


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.headers["Accept-Language"] = "en-US,en;q=0.9"
    return s


def get(session: requests.Session, url: str, timeout: int = 30) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last_exc = e
            wait = DELAY * attempt
            print(f"    ! GET {url} attempt {attempt} failed: {e} (retry in {wait:.1f}s)",
                  file=sys.stderr)
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("﻿", "").replace("\xa0", " ")).strip()


def parse_series(html: str) -> list[dict]:
    """One entry per grid item on the series page."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    seen_ids: set[str] = set()
    for a in soup.select("a[href^='/canada/stamps/']"):
        href = a.get("href", "")
        m = re.match(r"^/canada/stamps/(\d+)/(\S+)$", href)
        if not m:
            continue
        stamp_id, slug = m.group(1), m.group(2)
        if stamp_id in seen_ids:
            continue
        seen_ids.add(stamp_id)
        img = a.find("img")
        # The grid anchor wraps only the image; the name lives in its alt/title.
        name = clean(a.get_text()) or (clean(img.get("alt")) if img else "")
        out.append(
            {
                "stamp_id": stamp_id,
                "slug": slug,
                "list_name": name,
                "detail_url": urljoin(BASE, href),
                "list_thumb": clean(img.get("src")) if img and img.get("src") else "",
            }
        )
    return out


def derive_codes(entries: list[dict]) -> None:
    """Assign a unique `code` per entry, in place.

    Year is parsed from the slug (e.g. ...-1997-canada-...). Where a year is
    shared by multiple stamps, the postagestampguide ID is appended to keep the
    directory key unique while preserving year-first readability.
    """
    for e in entries:
        ym = re.search(r"-((?:19|20)\d{2})-", e["slug"])
        e["year"] = ym.group(1) if ym else ""
    year_counts = Counter(e["year"] for e in entries if e["year"])
    for e in entries:
        y = e["year"]
        if not y:
            e["code"] = f"id{e['stamp_id']}"
        elif year_counts[y] > 1:
            e["code"] = f"{y}-{e['stamp_id']}"
        else:
            e["code"] = y


def collect_sets(session: requests.Session) -> list[dict]:
    html = get(session, SERIES_URL).text
    entries = parse_series(html)
    derive_codes(entries)
    print(f"  series page: {len(entries)} stamps", file=sys.stderr)
    return entries


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.select_one("h1.page-title")
    name = clean(h1.get_text()) if h1 else ""

    # Spec table: <td><b>label</b></td><td>value</td>
    fields: dict[str, str] = {}
    table = soup.select_one("table.red-table")
    if table:
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) != 2:
                continue
            label = clean(cells[0].get_text())
            value = clean(cells[1].get_text())
            key = SPEC_LABELS.get(label)
            if key and key not in fields:
                fields[key] = value

    # Per-stamp prose: the block following the "About Stamp" header.
    description = ""
    for h2 in soup.select("h2.underline-label"):
        if clean(h2.get_text()) == "About Stamp":
            block = h2.find_parent("div", class_="h2-header")
            sib = block.find_next_sibling() if block else h2.find_next_sibling()
            if sib:
                description = clean(sib.get_text())
            break

    # Full-size image: the main stamp image renders as a `thumb_` file, wrapped in
    # a lightbox <a> pointing at the full-size version. Prefer that anchor; fall
    # back to de-thumbing the img.stamp-image src.
    image_url = ""
    main_img = soup.select_one("img.stamp-image")
    if main_img:
        a = main_img.find_parent("a")
        href = a.get("href", "") if a else ""
        if re.search(r"/images/\d+/", href) and "thumb" not in Path(urlparse(href).path).name:
            image_url = href
        else:
            src = main_img.get("src", "")
            if "/images/" in src:
                image_url = src.replace("/thumb_", "/")

    return {
        "page_name": name,
        "fields": fields,
        "description": description,
        "image_url": image_url,
    }


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = get(session, url, timeout=60)
        if not r.content:
            raise requests.RequestException("empty body")
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def build_record(meta: dict, detail: dict, image: dict | None) -> dict:
    return {
        "code": meta["code"],
        "year": meta["year"],
        "stamp_id": meta["stamp_id"],
        "slug": meta["slug"],
        "list_name": meta["list_name"],
        "detail_url": meta["detail_url"],
        "page_name": detail["page_name"],
        "fields": detail["fields"],
        "description": detail["description"],
        "image": image,
        "source": SOURCE,
    }


def scrape_set(session: requests.Session, meta: dict) -> dict:
    code = meta["code"]
    set_dir = OUT_DIR / code
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    html = get(session, meta["detail_url"]).text
    (set_dir / "detail.html").write_text(html, encoding="utf-8")
    detail = parse_detail(html)

    image: dict | None = None
    url = detail["image_url"]
    if url:
        fname = Path(urlparse(url).path).name
        image = {"image_url": url}
        if download(session, url, img_dir / fname):
            image["image_file"] = f"img/{fname}"
        time.sleep(DELAY)

    record = build_record(meta, detail, image)
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
        image = old.get("image")
        if image and detail["image_url"]:
            image = {"image_url": detail["image_url"], **(
                {"image_file": image["image_file"]} if image.get("image_file") else {})}
        meta = {k: old[k] for k in ("code", "year", "stamp_id", "slug",
                                    "list_name", "detail_url") if k in old}
        record = build_record(meta, detail, image)
        rawf.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  reparsed {d.name}: fields={len(detail['fields'])} "
              f"desc={len(detail['description'])} chars", file=sys.stderr)


def write_index(sets: list[dict]) -> None:
    idx = [
        {
            "code": s["code"],
            "year": s["year"],
            "stamp_id": s["stamp_id"],
            "list_name": s["list_name"],
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
    print("Collecting series page...", file=sys.stderr)
    sets = collect_sets(session)
    print(f"Total stamps: {len(sets)}", file=sys.stderr)

    write_index(sets)

    if args.list_only:
        for s in sorted(sets, key=lambda x: (x["year"], x["stamp_id"])):
            print(f"  {s['code']:14} {s['list_name']}")
        return

    for i, meta in enumerate(sets, 1):
        print(f"[{i}/{len(sets)}] {meta['code']} {meta['list_name']}", file=sys.stderr)
        try:
            rec = scrape_set(session, meta)
            has_img = bool(rec["image"] and rec["image"].get("image_file"))
            print(f"    fields={len(rec['fields'])} image={'yes' if has_img else 'NO'}",
                  file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - keep going on a single failure
            print(f"    ! stamp failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
