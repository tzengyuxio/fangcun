# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Scrape mainland China (中国邮政) zodiac stamp sets into data/raw/cn-chinapost/.

China Post has no structured historical catalogue, so we use 5151sc.com
(点购收藏网), a static PHP collector-shop site (tier=reference, id=cn-5151sc).

The four-round zodiac singles each live in their own category:
    一轮单枚 imgs-137 (T46 1980 庚申猴 .. T159 1991 羊)
    二轮单枚 imgs-286 (1992-1 .. 2003-1)
    三轮单枚 imgs-235 (2004-1T .. 2015-1T)
    四轮单枚 imgs-435 (2016- onward)

Category list page: imgs-{cat}-{page}.html  (gb2312, dl/dt anchors -> pro-{id}.html)
Product page:       pro-{id}.html
    - spec block in <div class="product_content" id="p1"> as 【label】value pairs
    - main image <img id="_middleImage" ... longdesc="http://pic.5151sc.com/b/.../*.jpg">
      (longdesc = full-size 800x600; src=/i/ medium; /s/,/sm/ are tiny -> ignore)

Each set -> data/raw/cn-chinapost/{code}/{raw.json, detail.html, img/*.jpg}
code is derived from the catalogue number in the title (e.g. T46, 1992-1, 2004-1T),
falling back to the product id for album/non-set entries. Plus a top-level _index.json.

Usage:
    uv run scripts/scrape_cn_chinapost.py --list-only   # collect & print the set list
    uv run scripts/scrape_cn_chinapost.py               # full scrape (detail + images)
    uv run scripts/scrape_cn_chinapost.py --reparse-local  # re-parse saved detail.html
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

BASE = "http://www.5151sc.com"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "cn-chinapost"
DELAY = 1.5  # polite delay; site may WAF foreign IPs, keep it slow
MAX_RETRIES = 4
SOURCE = {"id": "cn-5151sc", "tier": "reference"}

# Mainland zodiac singles, one category per round.
CATEGORIES = [
    {"cat": 137, "round": 1, "name": "一轮单枚"},
    {"cat": 286, "round": 2, "name": "二轮单枚"},
    {"cat": 235, "round": 3, "name": "三轮单枚"},
    {"cat": 435, "round": 4, "name": "四轮单枚"},
]


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.headers["Accept-Language"] = "zh-CN,zh;q=0.9"
    return s


def get(session: requests.Session, url: str, timeout: int = 30) -> requests.Response:
    """GET with retries/backoff; the site can be flaky / rate-limited for foreign IPs."""
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


def decode_gb(r: requests.Response) -> str:
    """The site is gb2312; use gb18030 (superset) to avoid decode errors."""
    return r.content.decode("gb18030", errors="replace")


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("﻿", "").replace("\xa0", " ")).strip()


def derive_code(title: str, pro_id: str) -> str:
    """Extract a unique catalogue code from a product title.

    Examples: 'T46 庚申年（猴票）' -> T46 ; '1992-1 壬申年（猴票）' -> 1992-1 ;
    '2004-1T《甲申年》特种邮票' -> 2004-1T . Albums / odd titles -> p{pro_id}.
    """
    t = title.strip()
    m = re.match(r"^(T\d+)", t)  # round 1: T46, T58 ...
    if m:
        return m.group(1)
    m = re.match(r"^(\d{4}-\d+T?)", t)  # round 2/3/4: 1992-1, 2004-1T, 2017-1
    if m:
        return m.group(1)
    return f"p{pro_id}"


def parse_list(html: str) -> list[dict]:
    """One entry per product in the category grid.

    The page also has a 'hot/recommended' sidebar with the same pro- links but no
    title attribute, so we anchor on the grid marker `dd.p_title` (one per product)
    and read the title from its sibling `dt` anchor (which carries title=).
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for dd in soup.select("dd.p_title"):
        dl = dd.find_parent("dl")
        if not dl:
            continue
        dt = dl.find("dt")
        a = dt.find("a", href=re.compile(r"pro-\d+\.html")) if dt else None
        a = a or dd.find("a", href=re.compile(r"pro-\d+\.html"))
        if not a:
            continue
        href = a["href"]
        m = re.search(r"pro-(\d+)\.html", href)
        pro_id = m.group(1) if m else ""
        # Title attribute is cleanest; fall back to the p_title link text.
        title = clean(a.get("title")) or clean(dd.get_text())
        img = dt.find("img") if dt else None
        out.append(
            {
                "pro_id": pro_id,
                "title": title,
                "detail_url": urljoin(BASE + "/", href),
                "list_thumb": clean(img.get("src")) if img and img.get("src") else "",
            }
        )
    return out


def parse_pagination(html: str, cat: int) -> int:
    """Highest page number for this category."""
    pages = [int(n) for n in re.findall(rf"imgs-{cat}-(\d+)\.html", html)]
    return max(pages) if pages else 1


def collect_sets(session: requests.Session) -> list[dict]:
    seen: dict[str, dict] = {}
    for c in CATEGORIES:
        cat = c["cat"]
        first = get(session, f"{BASE}/imgs-{cat}-1.html")
        html = decode_gb(first)
        n_pages = parse_pagination(html, cat)
        round_entries: dict[str, dict] = {}
        for page in range(1, n_pages + 1):
            if page > 1:
                html = decode_gb(get(session, f"{BASE}/imgs-{cat}-{page}.html"))
                time.sleep(DELAY)
            for e in parse_list(html):
                e["round"] = c["round"]
                e["round_name"] = c["name"]
                e["code"] = derive_code(e["title"], e["pro_id"])
                round_entries.setdefault(e["pro_id"], e)
        for e in round_entries.values():
            seen.setdefault(e["pro_id"], e)
        print(f"  round {c['round']} {c['name']} (cat {cat}, {n_pages}p): "
              f"{len(round_entries)} products", file=sys.stderr)
        time.sleep(DELAY)
    return list(seen.values())


SPEC_LABELS = {
    "藏品名称": "name",
    "藏品志号": "catalog_no",
    "图案面值": "design_face_value",
    "发行日期": "issue_date",
    "邮票规格": "stamp_size",
    "齿孔度数": "perforation",
    "整张枚数": "sheet_count",
    "版别": "printing_type",
    "防伪方式": "anti_counterfeit",
    "设计者": "designer",
    "雕刻者": "engraver",
    "责任编辑": "editor",
    "印制厂": "printer",
}


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = clean(soup.title.get_text()) if soup.title else ""

    # Product code 商品编号：Y01394
    pc_el = soup.select_one("div.pr_number")
    product_code = ""
    if pc_el:
        pm = re.search(r"商品编号[：:]\s*(\S+)", pc_el.get_text())
        product_code = pm.group(1) if pm else ""

    # Spec + intro live in the detail tab <div class="product_content" id="p1">.
    content = soup.select_one("#p1.product_content") or soup.select_one("#p1")
    fields: dict[str, str] = {}
    description = ""
    if content:
        text = content.get_text("\n")
        text = text.replace("\xa0", " ")
        # Split on 【label】 markers; pair each label with the text until the next marker.
        parts = re.split(r"【\s*([^】]+?)\s*】", text)
        # parts[0] is preamble; then label, value, label, value, ...
        for i in range(1, len(parts) - 1, 2):
            label = re.sub(r"\s+", "", parts[i])
            value = clean(parts[i + 1])
            if label in ("邮票介绍", "图片赏析", "藏品介绍"):
                description = description or value
                continue
            value = value.lstrip("：:").strip()  # some rows render "label】：value"
            key = SPEC_LABELS.get(label)
            if key and key not in fields:
                fields[key] = value

    # Main full-size image: longdesc of #_middleImage (the /b/ big version).
    images: list[str] = []
    mid = soup.select_one("#_middleImage")
    if mid:
        big = mid.get("longdesc") or mid.get("src")
        if big:
            images.append(big)
    # Extra gallery views: small selector strip carries name="YYYYMMDD/file.jpg".
    for im in soup.find_all("img"):
        name = im.get("name", "")
        if re.match(r"\d{8}/.+\.jpg$", name):
            big = f"http://pic.5151sc.com/b/{name}"
            if big not in images:
                images.append(big)
    # Dedup keeping order.
    seen_i: set[str] = set()
    images = [u for u in images if not (u in seen_i or seen_i.add(u))]

    return {
        "page_title": title,
        "product_code": product_code,
        "fields": fields,
        "description": description,
        "image_urls": images,
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


def scrape_set(session: requests.Session, meta: dict) -> dict:
    code = meta["code"]
    set_dir = OUT_DIR / code
    img_dir = set_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    r = get(session, meta["detail_url"])
    html = decode_gb(r)
    (set_dir / "detail.html").write_text(html, encoding="utf-8")
    detail = parse_detail(html)

    images: list[dict] = []
    for url in detail["image_urls"]:
        fname = Path(urlparse(url).path).name
        img = {"image_url": url}
        if download(session, url, img_dir / fname):
            img["image_file"] = f"img/{fname}"
        images.append(img)
        time.sleep(DELAY)

    record = {
        "code": code,
        "round": meta["round"],
        "round_name": meta["round_name"],
        "list_title": meta["title"],
        "pro_id": meta["pro_id"],
        "detail_url": meta["detail_url"],
        "page_title": detail["page_title"],
        "product_code": detail["product_code"],
        "fields": detail["fields"],
        "description": detail["description"],
        "images": images,
        "n_images": len([i for i in images if i.get("image_file")]),
        "source": SOURCE,
    }
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
        record = {**old}
        record.update(
            {
                "page_title": detail["page_title"],
                "product_code": detail["product_code"],
                "fields": detail["fields"],
                "description": detail["description"],
                "images": images,
                "n_images": len([i for i in images if i.get("image_file")]),
            }
        )
        rawf.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  reparsed {d.name}: fields={len(detail['fields'])} "
              f"desc={len(detail['description'])} chars", file=sys.stderr)


def write_index(sets: list[dict]) -> None:
    idx = [
        {
            "code": s["code"],
            "round": s["round"],
            "round_name": s["round_name"],
            "title": s["title"],
            "pro_id": s["pro_id"],
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
    ap.add_argument("--list-only", action="store_true", help="only collect & print the set list")
    ap.add_argument("--reparse-local", action="store_true",
                    help="re-parse saved detail.html into raw.json (no network)")
    args = ap.parse_args()

    if args.reparse_local:
        print("Re-parsing local detail.html files...", file=sys.stderr)
        reparse_local()
        print("Done.", file=sys.stderr)
        return

    session = make_session()
    print("Collecting category list pages...", file=sys.stderr)
    sets = collect_sets(session)
    print(f"Total products: {len(sets)}", file=sys.stderr)

    write_index(sets)

    if args.list_only:
        for s in sorted(sets, key=lambda x: (x["round"], x["code"])):
            print(f"  R{s['round']} {s['code']:10} {s['title']}")
        return

    for i, meta in enumerate(sets, 1):
        print(f"[{i}/{len(sets)}] R{meta['round']} {meta['code']} {meta['title']}",
              file=sys.stderr)
        try:
            rec = scrape_set(session, meta)
            print(f"    fields={len(rec['fields'])} images={rec['n_images']}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - keep going on a single set failure
            print(f"    ! set failed: {e}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
