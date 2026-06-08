# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Scrape K-stamp (Korea Post 인터넷우표박물관) New Year (연하우표) stamp sets.

Source: official K-stamp museum (tier=official, id=kr-kstamp),
https://stamp.epost.go.kr/ — pure JSP, no anti-scraping, no JS/login needed.

List : /sp2/sg/spsg0103.jsp?stampCode=05&yearCode={decade bucket}&page_num=N
       stampCode=05 = 연하우표; 12 sets per page; walk pages until short page.
       Decade buckets observed to actually return rows: 1960..2020 (1950 empty).
       Earliest set is 1957 (1st 연하우표), which lives in the 1960 bucket.
Detail: /sp2/sg/spsg0102.jsp?tbsmh15seqnum=<A>&tbsmh01seqnum=<B>
        info table (우표번호/종수/발행일/디자이너/액면가격/...) +
        ImgView('http://image.epost.go.kr/stamp/data_img/{so,ss,sw}/<id>.jpg').

Each set -> data/raw/kr-koreapost/{code}/{raw.json, img/<id>.jpg}
where code = "{year}-{stamp_number}" (unique; a year may carry 2 sets).

Usage:
    uv run scripts/scrape_kr_koreapost.py --list-only   # collect & print the set list
    uv run scripts/scrape_kr_koreapost.py               # full scrape (detail + images)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://stamp.epost.go.kr/sp2/sg"
LIST_URL = BASE + "/spsg0103.jsp"
DETAIL_URL = BASE + "/spsg0102.jsp"
STAMP_CODE = "05"  # 연하우표 (New Year)
# Decade buckets that return rows. 1950 is empty; the 1957 set sits in 1960.
DECADE_BUCKETS = ["1960", "1970", "1980", "1990", "2000", "2010", "2020"]
PER_PAGE = 12
MAX_PAGES = 10  # safety cap per bucket
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "kr-koreapost"
DELAY = 1.0  # polite delay between requests (seconds)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.get("https://stamp.epost.go.kr/", timeout=30)  # establish JSESSIONID
    return s


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("﻿", "")).strip()


def parse_list_page(html: str) -> list[dict]:
    """Each result row: <td>stamp_no</td><td><a img></td><td><a title></td><td>date</td>."""
    soup = BeautifulSoup(html, "html.parser")
    sets: list[dict] = []
    for tr in soup.find_all("tr"):
        a = tr.find("a", href=re.compile(r"spsg0102\.jsp"))
        if not a:
            continue
        qs = parse_qs(urlparse(a["href"]).query)
        a_seq = qs.get("tbsmh15seqnum", [""])[0]
        b_seq = qs.get("tbsmh01seqnum", [""])[0]
        if not a_seq or not b_seq:
            continue
        tds = tr.find_all("td", recursive=False)
        cells = [clean(td.get_text()) for td in tds]
        stamp_no = cells[0] if cells else ""
        title = clean(a.get_text()) or (cells[2] if len(cells) > 2 else "")
        issue_date = next((c for c in cells if re.match(r"\d{4}\s*\.", c)), "")
        img = tr.find("img")
        sets.append(
            {
                "tbsmh15seqnum": a_seq,
                "tbsmh01seqnum": b_seq,
                "list_stamp_no": stamp_no,
                "list_title": title,
                "list_issue_date": issue_date,
                "list_thumb": clean(img.get("src")) if img and img.get("src") else "",
                "detail_url": (
                    f"{DETAIL_URL}?tbsmh15seqnum={a_seq}&tbsmh01seqnum={b_seq}"
                    f"&stampCode={STAMP_CODE}"
                ),
            }
        )
    # dedup within page by seqnum pair, keep first
    seen: dict[tuple[str, str], dict] = {}
    for s in sets:
        seen.setdefault((s["tbsmh15seqnum"], s["tbsmh01seqnum"]), s)
    return list(seen.values())


def collect_sets(session: requests.Session) -> list[dict]:
    seen: dict[tuple[str, str], dict] = {}
    for yc in DECADE_BUCKETS:
        page = 1
        bucket_count = 0
        while page <= MAX_PAGES:
            url = (
                f"{LIST_URL}?stampCode={STAMP_CODE}&yearCode={yc}&page_num={page}"
            )
            r = session.get(url, timeout=30)
            r.encoding = "utf-8"
            page_sets = parse_list_page(r.text)
            for s in page_sets:
                key = (s["tbsmh15seqnum"], s["tbsmh01seqnum"])
                if key not in seen:
                    s["year_bucket"] = yc
                    seen[key] = s
                    bucket_count += 1
            time.sleep(DELAY)
            if len(page_sets) < PER_PAGE:
                break
            page += 1
        print(
            f"  bucket {yc}: +{bucket_count} new (cumulative {len(seen)})",
            file=sys.stderr,
        )
    sets = list(seen.values())
    return sorted(sets, key=_sort_key)


def _year_of(meta: dict) -> str:
    m = re.match(r"(\d{4})", meta.get("list_issue_date", "").replace(" ", ""))
    return m.group(1) if m else "0000"


def _sort_key(meta: dict) -> tuple[str, str]:
    return (_year_of(meta), meta.get("list_stamp_no", ""))


def make_code(meta: dict) -> str:
    """Unique, non-colliding code: {year}-{stamp_no}, falling back to seqnum."""
    year = _year_of(meta)
    no = re.sub(r"\D", "", meta.get("list_stamp_no", ""))
    if no:
        return f"{year}-{no}"
    return f"{year}-s{meta['tbsmh15seqnum']}"


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # Info table: <th>label</th><td>value</td>. Skip the section-header th (연하우표).
    fields: dict[str, str] = {}
    for th in soup.find_all("th"):
        label = clean(th.get_text())
        td = th.find_next_sibling("td")
        if not label or td is None:
            continue
        if label in ("연하우표", "이미지", "제목", "조회수"):
            continue
        fields[label] = clean(td.get_text())

    # Images: ImgView('http://image.epost.go.kr/stamp/data_img/{so,ss,sw}/<id>.jpg')
    # Modern sets use numeric ids (116061947698230.jpg); early sets use
    # alphanumeric ids (SO0244.jpg). Match both.
    img_urls: list[str] = []
    for m in re.finditer(
        r"data_img/(?:so|ss|sw)/[\w-]+\.jpg", html, re.IGNORECASE
    ):
        url = "http://image.epost.go.kr/stamp/" + m.group(0)
        if url not in img_urls:
            img_urls.append(url)

    return {"detail_fields": fields, "image_urls": img_urls}


def get_with_retry(
    session: requests.Session, url: str, *, timeout: int, retries: int = 3
) -> requests.Response:
    """GET with linear backoff; the http image host resets connections sporadically."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(DELAY * (attempt + 1))
    assert last is not None
    raise last


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = get_with_retry(session, url, timeout=60)
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def scrape_set(session: requests.Session, meta: dict) -> dict:
    code = make_code(meta)
    set_dir = OUT_DIR / code
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    r = get_with_retry(session, meta["detail_url"], timeout=30)
    r.encoding = "utf-8"
    detail = parse_detail(r.text)

    images: list[dict] = []
    for url in detail["image_urls"]:
        fname = Path(urlparse(url).path).name
        entry = {"image_url": url}
        if download(session, url, img_dir / fname):
            entry["image_file"] = f"img/{fname}"
        images.append(entry)
        time.sleep(DELAY)

    record = {
        "code": code,
        "title": meta.get("list_title", ""),
        "year": _year_of(meta),
        "issue_date": meta.get("list_issue_date", ""),
        "stamp_no": meta.get("list_stamp_no", ""),
        "detail_url": meta["detail_url"],
        "detail_fields": detail["detail_fields"],
        "images": images,
        "n_images": len(images),
        "source": {"id": "kr-kstamp", "tier": "official"},
    }
    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--list-only", action="store_true", help="only collect & print the set list"
    )
    args = ap.parse_args()

    session = make_session()
    print("Collecting 연하우표 list (decade buckets)...", file=sys.stderr)
    sets = collect_sets(session)
    print(f"Total sets: {len(sets)}", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = [
        {**s, "code": make_code(s), "year": _year_of(s)} for s in sets
    ]
    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.list_only:
        for s in index:
            print(f"  {s['code']:12} {s['list_issue_date']:14} {s['list_title']}")
        return

    for i, meta in enumerate(sets, 1):
        code = make_code(meta)
        print(f"[{i}/{len(sets)}] {code} {meta['list_title']}", file=sys.stderr)
        try:
            rec = scrape_set(session, meta)
            print(f"    {rec['n_images']} images", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - keep going on a single set failure
            print(f"    ! set failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
