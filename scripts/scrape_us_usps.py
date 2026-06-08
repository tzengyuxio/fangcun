# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Scrape U.S. (USPS) Lunar New Year zodiac stamps via the Smithsonian Open Access API.

Source: Smithsonian Open Access API (tier=official, source id `us-smithsonian-npm`),
scoped to the National Postal Museum (unit_code:NPM). This replaces the retired Arago
site. Lands into data/raw/us-usps/{code}/.

Coverage target (three U.S. LNY series):
  - Series 1  1992-2006  (Clarence Lee, 12 singles + 2 souvenir sheets)
  - Series 2  2008-2019  (Kam Mak)
  - Series 3  2020-       (Camille Chew / Antonio Alcala, ongoing)

API notes (verified 2026-06-09):
  - search:  https://api.si.edu/openaccess/api/v1.0/search?q=<q>&api_key=<KEY>&rows=&start=
    Response: .response.rowCount / .response.rows[] ; each row has .unitCode,
    .title, .id, .content.{descriptiveNonRepeating,freetext,indexedStructured}.
  - The query parser ORs free-text tokens, so `unit_code:NPM Lunar New Year` is used to
    pull NPM records, and we filter client-side to true zodiac stamps (title regex +
    object_type) to drop unrelated NPM postal-history material.
  - Images: public-domain items expose media under
    .content.descriptiveNonRepeating.online_media.media[] -> {idsId, content, ...}.
    IIIF full-res: https://ids.si.edu/ids/iiif/{idsId}/full/full/0/default.jpg
    COPYRIGHT LAYERING: Smithsonian only serves media URLs when the underlying work is
    public domain. LNY *designs* remain in copyright, so some items will have metadata
    only and NO image (image_file stays empty / online_media absent) -- recorded faithfully.

DEMO_KEY: api.data.gov DEMO_KEY works but is heavily rate-limited (hourly window, HTTP
429 OVER_RATE_LIMIT). For a full crawl, pass a free dedicated key via --api-key or the
SI_API_KEY env var (request at https://api.data.gov/signup/). The script backs off and
retries on 429; if it still cannot proceed it reports faithfully rather than fabricating.

Each set -> data/raw/us-usps/{code}/{raw.json, img/*.jpg}

Usage:
    uv run scripts/scrape_us_usps.py --list-only            # search + filter, print matches
    uv run scripts/scrape_us_usps.py                        # full scrape + images
    uv run scripts/scrape_us_usps.py --api-key YOUR_KEY     # use a dedicated key
    SI_API_KEY=YOUR_KEY uv run scripts/scrape_us_usps.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

API = "https://api.si.edu/openaccess/api/v1.0"
IIIF = "https://ids.si.edu/ids/iiif/{ids}/full/full/0/default.jpg"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "us-usps"
DELAY = 1.0
SOURCE = {"id": "us-smithsonian-npm", "tier": "official"}

# NPM-scoped search terms (ORed by the parser); kept narrow to LNY/zodiac.
SEARCH_QUERIES = [
    "unit_code:NPM Lunar New Year",
    "unit_code:NPM Chinese New Year",
    "unit_code:NPM Year of the",
]

ZODIAC = [
    "rat", "ox", "tiger", "rabbit", "dragon", "snake",
    "horse", "ram", "goat", "sheep", "monkey", "rooster", "dog", "boar", "pig",
]
ZODIAC_RE = re.compile(
    r"year of the (" + "|".join(ZODIAC) + r")\b", re.IGNORECASE
)
LNY_RE = re.compile(r"lunar new year|chinese new year", re.IGNORECASE)
# Canonical animal label per series-year (USPS uses Ram/Goat/Boar at times).
ANIMAL_NORM = {
    "rat": "Rat", "ox": "Ox", "tiger": "Tiger", "rabbit": "Rabbit",
    "dragon": "Dragon", "snake": "Snake", "horse": "Horse",
    "ram": "Ram", "goat": "Goat", "sheep": "Goat",
    "monkey": "Monkey", "rooster": "Rooster", "dog": "Dog",
    "boar": "Boar", "pig": "Pig",
}


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def api_get(session: requests.Session, path: str, params: dict, *, retries: int = 4) -> dict:
    """GET an API endpoint, retrying with backoff on HTTP 429 (rate limit)."""
    url = f"{API}/{path}"
    backoff = 20.0
    for attempt in range(1, retries + 1):
        r = session.get(url, params=params, timeout=60)
        if r.status_code == 429:
            print(
                f"    ! 429 rate-limited (attempt {attempt}/{retries}); "
                f"sleeping {backoff:.0f}s",
                file=sys.stderr,
            )
            time.sleep(backoff)
            backoff *= 2
            continue
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            code = data["error"].get("code", "")
            if code == "OVER_RATE_LIMIT":
                print(
                    f"    ! OVER_RATE_LIMIT (attempt {attempt}/{retries}); "
                    f"sleeping {backoff:.0f}s",
                    file=sys.stderr,
                )
                time.sleep(backoff)
                backoff *= 2
                continue
            raise RuntimeError(f"API error: {data['error']}")
        return data
    raise RuntimeError(
        "Exhausted retries against Smithsonian API (rate limited). "
        "Pass a dedicated key via --api-key / SI_API_KEY."
    )


def search_all(session: requests.Session, api_key: str, query: str) -> list[dict]:
    """Page through one search query and return NPM rows."""
    rows: list[dict] = []
    start, page = 0, 100
    while True:
        data = api_get(
            session,
            "search",
            {"q": query, "api_key": api_key, "rows": page, "start": start},
        )
        resp = data.get("response", {})
        batch = resp.get("rows", []) or []
        rows.extend(batch)
        total = resp.get("rowCount", 0)
        start += page
        time.sleep(DELAY)
        if start >= total or not batch:
            break
        # Safety cap: NPM lunar queries return a few hundred; never page forever.
        if start >= 600:
            break
    return rows


def is_zodiac_stamp(row: dict) -> bool:
    """Keep only true LNY zodiac postage-stamp items, drop unrelated NPM material."""
    if row.get("unitCode") != "NPM":
        return False
    title = row.get("title", "") or ""
    if not (ZODIAC_RE.search(title) or LNY_RE.search(title)):
        return False
    # Object type sanity check (when present): must be a stamp/philatelic item.
    otypes = []
    idx = (row.get("content", {}) or {}).get("indexedStructured", {}) or {}
    otypes += idx.get("object_type", []) or []
    free = (row.get("content", {}) or {}).get("freetext", {}) or {}
    for o in free.get("objectType", []) or []:
        if isinstance(o, dict):
            otypes.append(o.get("content", ""))
    blob = " ".join(otypes).lower()
    if blob and not re.search(r"stamp|philatel|postage|cover|essay|proof", blob):
        # Has object types but none philatelic -> probably a book/archive about LNY.
        return False
    return True


def freetext_values(free: dict, key: str) -> list[str]:
    out: list[str] = []
    for item in free.get(key, []) or []:
        if isinstance(item, dict):
            v = item.get("content", "")
            if v:
                out.append(v)
        elif isinstance(item, str):
            out.append(item)
    return out


def extract_year(title: str, dates: list[str]) -> str:
    m = re.search(r"\b(19|20)\d{2}\b", title)
    if m:
        return m.group(0)
    for d in dates:
        m = re.search(r"\b(19|20)\d{2}\b", d)
        if m:
            return m.group(0)
    return ""


def extract_animal(title: str) -> str:
    m = ZODIAC_RE.search(title)
    if m:
        return ANIMAL_NORM.get(m.group(1).lower(), m.group(1).title())
    return ""


def extract_media(content: dict) -> list[dict]:
    """Pull online media entries -> [{idsId, iiif_url, content_url, ...}]."""
    dnr = content.get("descriptiveNonRepeating", {}) or {}
    om = dnr.get("online_media", {}) or {}
    media = om.get("media", []) or []
    out: list[dict] = []
    for m in media:
        if not isinstance(m, dict):
            continue
        ids = m.get("idsId") or ""
        entry = {
            "idsId": ids,
            "type": m.get("type", ""),
            "content_url": m.get("content", ""),
            "thumbnail": m.get("thumbnail", ""),
            "usage": (m.get("usage", {}) or {}).get("access", ""),
            "iiif_url": IIIF.format(ids=ids) if ids else "",
        }
        out.append(entry)
    return out


def parse_row(session: requests.Session, api_key: str, row: dict) -> dict:
    """Build a record from a search row, enriching via the content endpoint if needed."""
    content = row.get("content", {}) or {}
    # If the search row lacks online_media, fetch the full content document.
    if not (content.get("descriptiveNonRepeating", {}) or {}).get("online_media"):
        try:
            full = api_get(
                session, "content/" + row["id"], {"api_key": api_key}
            )
            fc = (full.get("response", {}) or {}).get("content")
            if fc:
                content = fc
            time.sleep(DELAY)
        except Exception as e:  # noqa: BLE001 - enrichment is best-effort
            print(f"    ! content fetch failed for {row['id']}: {e}", file=sys.stderr)

    free = content.get("freetext", {}) or {}
    dnr = content.get("descriptiveNonRepeating", {}) or {}
    title = row.get("title", "") or ""

    names = freetext_values(free, "name")
    dates = freetext_values(free, "date")
    notes = freetext_values(free, "notes")
    object_types = freetext_values(free, "objectType")
    identifiers = freetext_values(free, "identifier")

    media = extract_media(content)
    record = {
        "code": "",  # filled by caller (needs uniqueness across the set)
        "source": SOURCE,
        "si_id": row.get("id", ""),
        "title": title,
        "year": extract_year(title, dates),
        "animal": extract_animal(title),
        "designer": names,        # designer/maker often under freetext.name
        "dates": dates,
        "object_type": object_types,
        "identifier": identifiers,
        "notes": notes,
        "record_link": dnr.get("record_link", ""),
        "data_source": dnr.get("data_source", ""),
        "metadata_usage": dnr.get("metadata_usage", {}),
        "media": media,
        "has_image": any(m.get("iiif_url") for m in media),
        "images": [],
    }
    return record


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=120)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def make_code(record: dict, used: set[str]) -> str:
    """Unique, readable code: year-animal, then year, then si_id; de-duped."""
    parts = [p for p in (record.get("year"), record.get("animal")) if p]
    base = "-".join(parts).lower().replace(" ", "-") if parts else record["si_id"]
    code = base
    i = 2
    while code in used:
        code = f"{base}-{i}"
        i += 1
    used.add(code)
    return code


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="search + filter, no download")
    ap.add_argument(
        "--api-key",
        default=os.environ.get("SI_API_KEY", "DEMO_KEY"),
        help="Smithsonian / api.data.gov key (default: env SI_API_KEY or DEMO_KEY)",
    )
    args = ap.parse_args()
    api_key = args.api_key

    session = make_session()
    print(
        f"Searching Smithsonian NPM (key={'DEMO_KEY' if api_key=='DEMO_KEY' else 'custom'})...",
        file=sys.stderr,
    )

    raw_rows: dict[str, dict] = {}
    for q in SEARCH_QUERIES:
        try:
            rows = search_all(session, api_key, q)
        except RuntimeError as e:
            print(f"  ! query '{q}' aborted: {e}", file=sys.stderr)
            continue
        kept = [r for r in rows if is_zodiac_stamp(r)]
        print(f"  '{q}': {len(rows)} NPM rows, {len(kept)} zodiac matches", file=sys.stderr)
        for r in kept:
            raw_rows[r["id"]] = r

    matches = list(raw_rows.values())
    print(f"Total unique zodiac stamp records: {len(matches)}", file=sys.stderr)

    if not matches:
        print(
            "No matches retrieved. If DEMO_KEY is rate-limited (429/OVER_RATE_LIMIT), "
            "rerun later or pass a dedicated key via --api-key / SI_API_KEY.",
            file=sys.stderr,
        )

    if args.list_only:
        for r in sorted(matches, key=lambda x: x.get("title", "")):
            print(f"  {r['id']:24} {r.get('title','')}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    index: list[dict] = []

    for i, row in enumerate(matches, 1):
        print(f"[{i}/{len(matches)}] {row.get('title','')}", file=sys.stderr)
        try:
            record = parse_row(session, api_key, row)
        except Exception as e:  # noqa: BLE001 - keep going on single-record failure
            print(f"    ! parse failed: {e}", file=sys.stderr)
            continue

        code = make_code(record, used)
        record["code"] = code
        set_dir = OUT_DIR / code
        img_dir = set_dir / "img"
        img_dir.mkdir(parents=True, exist_ok=True)

        for j, m in enumerate(record["media"]):
            if not m.get("iiif_url"):
                continue
            fname = f"{m['idsId']}.jpg" if m.get("idsId") else f"img{j}.jpg"
            ok = download(session, m["iiif_url"], img_dir / fname)
            record["images"].append(
                {"iiif_url": m["iiif_url"], "image_file": f"img/{fname}" if ok else None}
            )
            time.sleep(DELAY)

        n_img = sum(1 for im in record["images"] if im["image_file"])
        (set_dir / "raw.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"    {code} | year={record['year'] or '?'} | "
            f"{record['animal'] or '?'} | {n_img} img",
            file=sys.stderr,
        )
        index.append(
            {
                "code": code,
                "si_id": record["si_id"],
                "title": record["title"],
                "year": record["year"],
                "animal": record["animal"],
                "has_image": record["has_image"],
                "n_images": n_img,
                "record_link": record["record_link"],
            }
        )
        time.sleep(DELAY)

    index.sort(key=lambda x: (x["year"] or "", x["code"]))
    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with_img = sum(1 for x in index if x["n_images"] > 0)
    print(
        f"Done. {len(index)} sets -> {OUT_DIR} "
        f"({with_img} with images, {len(index) - with_img} metadata-only)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
