# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Scrape Japan Post (日本郵便) New Year (年賀) stamp sets into data/raw/jp-japanpost/.

Source: official stamp archive JSON (tier=official), filtered to title containing 年賀.
Covers 1997–2025 年度 (28 sets; the 2007 年度 is absent from the official feed).
The 1950–1996 historical gap is NOT covered here (not in the official source).

Each set -> data/raw/jp-japanpost/{code}/{raw.json, img/<main>.jpg}

Usage:
    uv run scripts/scrape_jp_japanpost.py --list-only   # list matched sets
    uv run scripts/scrape_jp_japanpost.py               # download metadata + main image
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

BASE = "https://www.post.japanpost.jp"
JSON_URL = BASE + "/enjoy/culture/stamp/archive/json/stamp.json"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "jp-japanpost"
DELAY = 0.5


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def fetch_feed(session: requests.Session) -> list[dict]:
    r = session.get(JSON_URL, timeout=30)
    r.raise_for_status()
    # feed is UTF-8 with BOM
    return json.loads(r.content.decode("utf-8-sig"))


def select_nenga(feed: list[dict]) -> list[dict]:
    sets: list[dict] = []
    for s in feed:
        if "年賀" not in s.get("title", ""):
            continue
        sets.append(
            {
                "code": s.get("year", ""),  # one 年賀 set per year -> unique
                "title": s.get("title", ""),
                "year": s.get("year", ""),
                "date": s.get("date", ""),
                "type": s.get("type", ""),
                "keyword": s.get("keyword", ""),
                "detail_url": urljoin(BASE, s.get("url", "")),
                "pdf_url": urljoin(BASE, s["pdf"]) if s.get("pdf") else "",
                "image_url": urljoin(BASE, s["img"]) if s.get("img") else "",
                "source": {"id": "jp-japanpost-archive", "tier": "official"},
            }
        )
    # newest-first in feed; present oldest-first for readability
    return sorted(sets, key=lambda x: x["year"])


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
    if meta["image_url"]:
        fname = Path(urlparse(meta["image_url"]).path).name
        if download(session, meta["image_url"], img_dir / fname):
            record["image_file"] = f"img/{fname}"
        time.sleep(DELAY)

    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="only list matched sets")
    args = ap.parse_args()

    session = make_session()
    print("Fetching official stamp feed...", file=sys.stderr)
    feed = fetch_feed(session)
    sets = select_nenga(feed)
    print(f"Matched 年賀 sets: {len(sets)}", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "_index.json").write_text(
        json.dumps(sets, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.list_only:
        for s in sets:
            print(f"  {s['code']:14} {s['year']}  {s['title']}")
        return

    for i, meta in enumerate(sets, 1):
        print(f"[{i}/{len(sets)}] {meta['code']} {meta['title']}", file=sys.stderr)
        try:
            scrape_set(session, meta)
        except Exception as e:  # noqa: BLE001 - keep going on a single set failure
            print(f"    ! set failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
