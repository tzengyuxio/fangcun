# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Scrape Japan New Year (年賀) stamps for 1950–1996 into data/raw/jp-japanpost/.

Fills the historical gap not covered by the official feed (which only goes back to
1997). Metadata and images come from two reference (tier=reference) sources:

- metadata: http://dorama.tank.jp/d/nengakittehtml.html
  歴代一覧表 (Shift_JIS). Columns per year row: 西暦 / 和暦 / 干支 / 図案名 / 面額 /
  発行日. Continuous 1950–2009. Provides every year's metadata.
- images:   https://www.yuubinsyumi.com/shopbrand/ct285/ (昭和年賀, EUC-JP).
  Product titles encode 昭和NN年用 -> use-year = 1925 + NN. The full 500x500 image
  is the CDN object keyed by the 12-digit product id with no suffix:
  https://makeshop-multi-images.akamaized.net/yuubinsyumi/itemimages/{pid}.jpg
  Stock-driven, so 1990–1996 (post-昭和) have no image here; that's expected.

Each year -> data/raw/jp-japanpost/{year}/{raw.json, img/{year}.jpg}
  code = year (西暦). Range capped at 1996 so it never collides with the existing
  official 1997–2025 sets.

Usage:
    uv run scripts/scrape_jp_nenga_legacy.py --list-only   # parse sources, print plan
    uv run scripts/scrape_jp_nenga_legacy.py               # metadata + images
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

DORAMA_URL = "http://dorama.tank.jp/d/nengakittehtml.html"
YUU_URL = "https://www.yuubinsyumi.com/shopbrand/ct285/"
CDN = "https://makeshop-multi-images.akamaized.net/yuubinsyumi/itemimages/{pid}.jpg"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "jp-japanpost"
YEAR_MIN, YEAR_MAX = 1950, 1996
DELAY = 0.7

DORAMA_SRC = {"id": "jp-dorama", "tier": "reference"}
YUU_SRC = {"id": "jp-yuubinsyumi", "tier": "reference"}

_ZEN2HAN = str.maketrans("０１２３４５６７８９", "0123456789")


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text.replace("&nbsp;", " ")).strip()


def parse_dorama(html: str) -> dict[int, dict]:
    """Return {year: {kanreki, zodiac, design, denomination, issue_date}}."""
    out: dict[int, dict] = {}
    for row in re.findall(r"<TR>(.*?)</TR>", html, re.S | re.I):
        tds = [clean(t) for t in re.findall(r"<TD[^>]*>(.*?)</TD>", row, re.S | re.I)]
        if len(tds) < 6:
            continue
        m = re.match(r"^((?:19|20)\d\d)年", tds[0])
        if not m:
            continue
        year = int(m.group(1))
        if not (YEAR_MIN <= year <= YEAR_MAX):
            continue
        out[year] = {
            "kanreki": tds[1],
            "zodiac": tds[2],
            "design": tds[3],
            "denomination": tds[4],
            "issue_date": tds[5],
        }
    return out


def parse_yuubinsyumi(html: str) -> dict[int, str]:
    """Return {use_year: product_id} for plain 昭和NN年用 年賀切手 items in range.

    use_year = 1925 + 昭和NN. Prefer the shortest title per year (the plain set,
    not variant/sheet listings).
    """
    best: dict[int, tuple[str, str]] = {}  # year -> (pid, title)
    for blk in re.split(r"(?=/shopdetail/\d{12}/ct285/)", html):
        mid = re.match(r"/shopdetail/(\d{12})/ct285/", blk)
        if not mid:
            continue
        pid = mid.group(1)
        mt = re.search(r"(年賀切手[^<\"]*昭和[0-9０-９]+年用[^<\"]*)", blk)
        if not mt:
            continue
        title = clean(mt.group(1)).translate(_ZEN2HAN)
        ms = re.search(r"昭和(\d+)年用", title)
        if not ms:
            continue
        year = 1925 + int(ms.group(1))
        if not (YEAR_MIN <= year <= YEAR_MAX):
            continue
        if year not in best or len(title) < len(best[year][1]):
            best[year] = (pid, title)
    return {y: pid for y, (pid, _t) in best.items()}


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def build_records(
    dorama: dict[int, dict], yuu: dict[int, str]
) -> list[dict]:
    records: list[dict] = []
    for year in range(YEAR_MIN, YEAR_MAX + 1):
        meta = dorama.get(year)
        if not meta:
            print(f"  ! no dorama row for {year}", file=sys.stderr)
            continue
        sources = [DORAMA_SRC]
        pid = yuu.get(year)
        rec: dict = {
            "code": str(year),
            "year": str(year),
            "title": f"{year}年用年賀切手",
            "kanreki": meta["kanreki"],
            "zodiac": meta["zodiac"],
            "design": meta["design"],
            "denomination": meta["denomination"],
            "issue_date": meta["issue_date"],
            "image_url": "",
            "image_file": "",
            "source": sources,
        }
        if pid:
            rec["image_url"] = CDN.format(pid=pid)
            rec["yuu_product_id"] = pid
            sources.append(YUU_SRC)
        records.append(rec)
    return records


def scrape() -> None:
    session = make_session()

    print("Fetching dorama 歴代一覧 (Shift_JIS)...", file=sys.stderr)
    r = session.get(DORAMA_URL, timeout=30)
    r.raise_for_status()
    dorama = parse_dorama(r.content.decode("shift_jis", errors="replace"))
    print(f"  dorama years parsed (1950–1996): {len(dorama)}", file=sys.stderr)
    time.sleep(DELAY)

    print("Fetching yuubinsyumi 昭和年賀 catalog (EUC-JP)...", file=sys.stderr)
    r = session.get(YUU_URL, timeout=30)
    r.raise_for_status()
    yuu = parse_yuubinsyumi(r.content.decode("euc-jp", errors="replace"))
    print(f"  yuubinsyumi image candidates (1950–1996): {len(yuu)}", file=sys.stderr)
    time.sleep(DELAY)

    return dorama, yuu


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="parse sources, no download")
    args = ap.parse_args()

    dorama, yuu = scrape()
    records = build_records(dorama, yuu)
    print(f"Records built: {len(records)} (expected ~47)", file=sys.stderr)

    if args.list_only:
        for rec in records:
            img = "img" if rec["image_url"] else "  -"
            print(
                f"  {rec['code']}  {rec['zodiac']}  {img}  "
                f"{rec['denomination']:10}  {rec['design']}"
            )
        return

    session = make_session()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_img = 0
    for i, rec in enumerate(records, 1):
        print(f"[{i}/{len(records)}] {rec['code']} {rec['zodiac']}", file=sys.stderr)
        set_dir = OUT_DIR / rec["code"]
        img_dir = set_dir / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        if rec["image_url"]:
            dest = img_dir / f"{rec['code']}.jpg"
            if download(session, rec["image_url"], dest):
                rec["image_file"] = f"img/{rec['code']}.jpg"
                n_img += 1
            time.sleep(DELAY)
        (set_dir / "raw.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    (OUT_DIR / "_index_legacy.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Done. {len(records)} years written, {n_img} with images.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
