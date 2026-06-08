# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Scrape Hongkong Post (香港郵政) zodiac stamp issues into data/raw/hk-hongkongpost/.

Source: stamps.hongkongpost.hk philatelic shop (tier=official, government).
This site only carries the CURRENT year's on-sale issues under
`/tc/stamps/latest_stamps_issues/index.html`; historical zodiac rounds are NOT
archived here. We pick the issues whose Chinese title references the current
zodiac (生肖 / 歲次 / the animal name), which for the 5th round includes:
  - the main set (4 stamps + souvenir sheets incl. a laser-cut one)
  - the gold/silver zodiac souvenir sheet (金銀郵票)
  - the HK/China/Macau joint-issue pack (聯合發行)

Each set -> data/raw/hk-hongkongpost/{code}/{raw.json, detail.html, img/*.jpg}
where code = "{year}-{theme}" (unique).

Usage:
    uv run scripts/scrape_hk_hongkongpost.py --list-only   # collect & print matched issues
    uv run scripts/scrape_hk_hongkongpost.py               # full scrape (detail + images)
    uv run scripts/scrape_hk_hongkongpost.py --reparse-local  # re-parse saved HTML (no network)
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

BASE = "https://stamps.hongkongpost.hk"
INDEX_URL = BASE + "/tc/stamps/latest_stamps_issues/index.html"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "hk-hongkongpost"
DELAY = 1.0  # polite delay between requests (seconds)

# Zodiac-issue title markers. HK zodiac stamps are always titled with 歲次 (the
# main set / joint pack) or 生肖 (the gold/silver souvenir sheet). Matching bare
# animal characters would catch unrelated issues (e.g. 龍舟 dragon-boat), so we
# deliberately require these two markers only.
ZODIAC_KEYWORDS = ("生肖", "歲次")
# The error/redirect shell the CDN serves for non-existent paths.
ERROR_MARKERS = ("Redirecting to error page", "redirect.js", "error.js")


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
    html = r.text
    if any(m in html for m in ERROR_MARKERS) and len(html) < 1000:
        raise ValueError(f"server returned error/redirect shell for {url}")
    return html


def collect_issues(session: requests.Session) -> list[dict]:
    """From the latest-issues index, keep links whose title looks zodiac-related."""
    html = fetch_html(session, INDEX_URL)
    soup = BeautifulSoup(html, "html.parser")
    issues: dict[str, dict] = {}
    for a in soup.select("a[href]"):
        href = a["href"]
        m = re.search(r"/latest_stamps_issues/(\d{4})/([^/]+)/index\.html", href)
        if not m:
            continue
        # On the index, the visible title lives in the thumbnail's alt text;
        # the anchor's own text is empty.
        img = a.find("img")
        title = clean(a.get_text()) or (clean(img.get("alt")) if img else "")
        if not any(k in title for k in ZODIAC_KEYWORDS):
            continue
        year, theme = m.group(1), m.group(2)
        code = f"{year}-{theme}"
        issues.setdefault(
            code,
            {
                "code": code,
                "year": year,
                "theme": theme,
                "list_title": title,
                "detail_url": urljoin(BASE, href),
                "source": {"id": "hk-hongkongpost", "tier": "official"},
            },
        )
    return list(issues.values())


def parse_detail(html: str, year: str, theme: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h2.title")
    title = clean(title_el.get_text()) if title_el else ""

    date_el = soup.select_one("h3.date")
    issue_date = ""
    if date_el:
        dm = re.search(r"(\d{4}/\d{1,2}/\d{1,2})", date_el.get_text())
        issue_date = dm.group(1) if dm else clean(date_el.get_text())

    # Intro / design rationale: first accordionItem after the #intro heading.
    description = ""
    intro_h = soup.find(id="intro")
    if intro_h:
        item = intro_h.find_next("div", class_="accordionItem")
        if item:
            description = clean(item.get_text(" "))

    # Products: each <div class="stamps_product">.
    products: list[dict] = []
    for box in soup.select("div.stamps_product"):
        img = box.select_one("div.stamps_img img")
        image_url = urljoin(BASE, img["src"]) if img and img.get("src") else ""
        header = box.select_one("p.header")
        name = clean(header.get_text()) if header else clean(img.get("title")) if img else ""
        fields: dict[str, str] = {}
        for p in box.find_all("p"):
            if p is header:
                continue
            txt = clean(p.get_text())
            mm = re.match(r"(售價|限購|描述|銷售期)\s*[:：]\s*(.*)", txt)
            if mm:
                fields[mm.group(1)] = mm.group(2)
        buy = box.find("a", attrs={"data-product-code": True})
        products.append(
            {
                "name": name,
                "price": fields.get("售價", ""),
                "purchase_limit": fields.get("限購", ""),
                "sale_period": fields.get("銷售期", ""),
                "description": fields.get("描述", ""),
                "product_code": buy["data-product-code"] if buy else "",
                "image_url": image_url,
            }
        )

    return {
        "title": title,
        "issue_date": issue_date,
        "description": description,
        "products": products,
        "n_products": len(products),
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


def scrape_issue(session: requests.Session, meta: dict) -> dict:
    set_dir = OUT_DIR / meta["code"]
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    html = fetch_html(session, meta["detail_url"])
    (set_dir / "detail.html").write_text(html, encoding="utf-8")
    detail = parse_detail(html, meta["year"], meta["theme"])

    seen: set[str] = set()
    n_img = 0
    for prod in detail["products"]:
        url = prod["image_url"]
        if not url:
            continue
        fname = Path(urlparse(url).path).name
        prod["image_file"] = f"img/{fname}"
        if fname in seen:
            continue
        seen.add(fname)
        if download(session, url, img_dir / fname):
            n_img += 1
        time.sleep(DELAY)

    record = {**meta, **detail, "n_images": n_img}
    (set_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def reparse_local() -> None:
    for d in sorted(p for p in OUT_DIR.iterdir() if p.is_dir()):
        rawf, htmlf = d / "raw.json", d / "detail.html"
        if not rawf.exists() or not htmlf.exists():
            continue
        old = json.loads(rawf.read_text(encoding="utf-8"))
        detail = parse_detail(htmlf.read_text(encoding="utf-8"), old.get("year", ""), old.get("theme", ""))
        meta = {k: old[k] for k in ("code", "year", "theme", "list_title", "detail_url", "source") if k in old}
        # preserve previously resolved image_file paths
        for prod in detail["products"]:
            if prod.get("image_url"):
                prod["image_file"] = f"img/{Path(urlparse(prod['image_url']).path).name}"
        record = {**meta, **detail, "n_images": old.get("n_images", 0)}
        rawf.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  reparsed {d.name}: {detail['n_products']} products, desc={len(detail['description'])} chars", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="only collect & print matched issues")
    ap.add_argument("--reparse-local", action="store_true", help="re-parse saved detail.html (no network)")
    args = ap.parse_args()

    if args.reparse_local:
        print("Re-parsing local detail.html files...", file=sys.stderr)
        reparse_local()
        print("Done.", file=sys.stderr)
        return

    session = make_session()
    print("Collecting latest-issues index...", file=sys.stderr)
    issues = collect_issues(session)
    print(f"Matched zodiac issues: {len(issues)}", file=sys.stderr)
    time.sleep(DELAY)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "_index.json").write_text(
        json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.list_only:
        for s in issues:
            print(f"  {s['code']:24} {s['list_title']}")
        return

    for i, meta in enumerate(issues, 1):
        print(f"[{i}/{len(issues)}] {meta['code']} {meta['list_title']}", file=sys.stderr)
        try:
            rec = scrape_issue(session, meta)
            print(f"    {rec['n_products']} products, {rec['n_images']} images, date={rec['issue_date']}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - keep going on a single issue failure
            print(f"    ! issue failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
