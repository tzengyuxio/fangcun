# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Scrape Chunghwa Post (中華郵政) zodiac stamp sets into data/raw/post-tw/.

Source: W_stamphouse subcat "生肖" (type=2802), 7 list pages.
Each set -> data/raw/post-tw/{file_name}/{raw.json, detail.html, img/*.jpg}

Usage:
    uv run scripts/scrape_post_tw.py --list-only   # just collect & print the set list
    uv run scripts/scrape_post_tw.py               # full scrape (detail + images)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.post.gov.tw/post/internet/W_stamphouse/index.jsp"
LIST_PARAMS = "?ID=2802&stamp_subcat_name=%E7%94%9F%E8%82%96&type=2802"
LIST_URL = BASE + LIST_PARAMS
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
N_PAGES = 7
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "post-tw"
DELAY = 1.0  # polite delay between requests (seconds)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.get(LIST_URL, timeout=30)  # establish JSESSIONID
    return s


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("﻿", "")).strip()


def parse_list_page(html: str) -> list[dict]:
    """Extract one set per <li> in ul.content."""
    soup = BeautifulSoup(html, "html.parser")
    sets: list[dict] = []
    for ul in soup.select("ul.content"):
        for li in ul.find_all("li", recursive=False):
            a = li.find("a", href=re.compile(r"ID=2803"))
            if not a:
                continue
            qs = parse_qs(urlparse(a["href"]).query)
            file_name = qs.get("file_name", [""])[0]
            if not file_name:
                continue
            img = li.find("img")
            sets.append(
                {
                    "file_name": file_name,
                    "list_subcat": clean(a.find("p").get_text() if a.find("p") else ""),
                    "list_name": clean(a.find("strong").get_text() if a.find("strong") else ""),
                    "list_issue_date": clean(a.find("em").get_text() if a.find("em") else ""),
                    "list_thumb": urljoin(BASE, img["src"]) if img and img.get("src") else "",
                    "list_thumb_alt": clean(img.get("alt")) if img else "",
                    "detail_url": urljoin(BASE, a["href"]),
                }
            )
    return sets


def collect_sets(session: requests.Session) -> list[dict]:
    seen: dict[str, dict] = {}
    for page in range(1, N_PAGES + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}&topage={page}&PreRowDatas=12"
        r = session.get(url, timeout=30)
        r.encoding = "utf-8"
        page_sets = parse_list_page(r.text)
        for s in page_sets:
            seen.setdefault(s["file_name"], s)  # dedup by file_name, keep first
        print(f"  page {page}: {len(page_sets)} sets (cumulative {len(seen)})", file=sys.stderr)
        time.sleep(DELAY)
    return list(seen.values())


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # Field table: <th class="hd">label</th><td>value</td>
    fields: dict[str, str] = {}
    for th in soup.select("th.hd"):
        td = th.find_next("td")
        label = clean(th.get_text()).replace(" ", "")
        if label:
            fields[label] = clean(td.get_text()) if td else ""

    # Main stamp images: anchors carrying data-cycle-desc in the main cycle gallery.
    stamps: list[dict] = []
    for a in soup.select("a[data-cycle-desc]"):
        href = a.get("href", "")
        if "stamp_pic" not in href:
            continue
        stamps.append(
            {
                "title": clean(a.get("data-cycle-title")),
                "desc": clean(a.get("data-cycle-desc")),
                "image_url": urljoin(BASE, href),
            }
        )

    # Design rationale text lives in div.LineHeight180 (the .pane content block).
    desc_el = soup.select_one("div.LineHeight180")
    desc = clean(desc_el.get_text()) if desc_el else ""

    return {"detail_fields": fields, "stamps": stamps, "description": desc}


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
    file_name = meta["file_name"]
    set_dir = OUT_DIR / file_name
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    r = session.get(meta["detail_url"], timeout=30)
    r.encoding = "utf-8"
    (set_dir / "detail.html").write_text(r.text, encoding="utf-8")
    detail = parse_detail(r.text)

    for st in detail["stamps"]:
        fname = Path(urlparse(st["image_url"]).path).name
        if download(session, st["image_url"], img_dir / fname):
            st["image_file"] = f"img/{fname}"
        time.sleep(DELAY)

    record = {**meta, **detail, "n_stamps": len(detail["stamps"])}
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
        detail = parse_detail(htmlf.read_text(encoding="utf-8"))
        img_map = {
            Path(urlparse(s["image_url"]).path).name: s.get("image_file")
            for s in old.get("stamps", [])
        }
        for s in detail["stamps"]:
            fname = Path(urlparse(s["image_url"]).path).name
            if img_map.get(fname):
                s["image_file"] = img_map[fname]
        meta_keys = (
            "file_name", "list_subcat", "list_name", "list_issue_date",
            "list_thumb", "list_thumb_alt", "detail_url",
        )
        meta = {k: old[k] for k in meta_keys if k in old}
        record = {**meta, **detail, "n_stamps": len(detail["stamps"])}
        rawf.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  reparsed {d.name}: desc={len(detail['description'])} chars", file=sys.stderr)


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
    print("Collecting list pages...", file=sys.stderr)
    sets = collect_sets(session)
    print(f"Total sets: {len(sets)}", file=sys.stderr)

    if args.list_only:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "_index.json").write_text(
            json.dumps(sets, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for s in sets:
            print(f"  {s['file_name']:10} {s['list_issue_date']:20} {s['list_name']}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "_index.json").write_text(
        json.dumps(sets, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for i, meta in enumerate(sets, 1):
        print(f"[{i}/{len(sets)}] {meta['file_name']} {meta['list_name']}", file=sys.stderr)
        try:
            rec = scrape_set(session, meta)
            print(f"    {rec['n_stamps']} images", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - keep going on a single set failure
            print(f"    ! set failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
