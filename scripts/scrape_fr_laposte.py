# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Scrape French La Poste lunar-year (Année lunaire) zodiac stamps into data/raw/fr-laposte/.

Source: philatelie-francaise.com (static catalogue, tier=reference).
The site has no per-theme index, but its "recherche_like" full-text search returns
the lunar-new-year stamp pages. We query several French wordings (the naming changed
over the years) and dedup by the internal page id `lig`.

Each stamp page: timbre_affiche/timbre.php?lig=NNNN -> fields + one large image
    image/image-{year}/{file}.jpg

Records are grouped by issue year (one dir per year, code=year):
    data/raw/fr-laposte/{year}/{raw.json, img/*.jpg}
plus a top-level _index.json.

Usage:
    uv run scripts/scrape_fr_laposte.py --list-only   # collect & print the lig index
    uv run scripts/scrape_fr_laposte.py               # full scrape (pages + images)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://philatelie-francaise.com"
SEARCH_POST = f"{BASE}/recherche/recherche_like/like.php"
SEARCH_RESULT = f"{BASE}/recherche/recherche_like/affiche_like.php"
TIMBRE = f"{BASE}/timbre_affiche/timbre.php?lig="
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "fr-laposte"
DELAY = 1.0  # polite delay between requests (seconds)
SOURCE = {"id": "fr-philatelie-francaise", "tier": "reference"}

# Search terms covering the changing French wording across years.
SEARCH_TERMS = [
    "nouvel an chinois",
    "an chinois",
    "année lunaire",
    "année du coq",
    "année du chien",
    "année du lapin",
    "année du tigre",
    "année du dragon",
    "année du serpent",
    "signes astrologiques chinois",
]

# Animal name (FR) per Gregorian start year, for tagging records.
ZODIAC_FR = {
    2005: "Coq", 2006: "Chien", 2007: "Cochon", 2008: "Rat", 2009: "Buffle",
    2010: "Tigre", 2011: "Lapin", 2012: "Dragon", 2013: "Serpent", 2014: "Cheval",
    2015: "Chèvre", 2016: "Singe", 2017: "Coq", 2018: "Chien", 2019: "Cochon",
    2020: "Rat", 2021: "Buffle", 2022: "Tigre", 2023: "Lapin", 2024: "Dragon",
    2025: "Serpent", 2026: "Cheval",
}

SKIP_TITLES = (
    "Classiques", "Carnets", "Blocs", "Souvenirs", "Colis", "Croix", "Grève",
    "Guerre", "Aériens", "Préob", "Service", "Taxe", "Adhésifs", "Affichage",
)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("﻿", "").replace("\xa0", " ")).strip()


def search(session: requests.Session, term: str) -> str:
    """Run one full-text search; the result is stored in the PHP session."""
    session.post(SEARCH_POST, data={"expression": term, "Chercher": "Chercher"}, timeout=30)
    r = session.get(SEARCH_RESULT, timeout=30)
    r.encoding = "utf-8"
    return r.text


def parse_search(html: str) -> dict[str, dict]:
    """Return {lig: {lig, image_rel, year}} for lunar-stamp entries with an image."""
    out: dict[str, dict] = {}
    for m in re.finditer(r"lig=(\d+)\"[^>]*>(.*?)</a>", html, re.S):
        lig = m.group(1)
        inner = m.group(2)
        txt = clean(re.sub(r"<[^>]+>", " ", inner))
        if txt and txt.startswith(SKIP_TITLES):
            continue
        img = re.search(r"(image/(?:image-\d{4}|collector-\d{4}|autoadhesif[^\"']*)/[^\"']+\.jpg)", inner)
        if not img:
            continue
        rel = img.group(1)
        ym = re.search(r"(?:image-|collector-|autoadhesif-)(\d{4})", rel)
        year = ym.group(1) if ym else None
        if not year:
            continue
        out.setdefault(lig, {"lig": lig, "image_rel": rel, "year": year})
    return out


def collect_ligs(session: requests.Session) -> dict[str, dict]:
    seen: dict[str, dict] = {}
    for term in SEARCH_TERMS:
        html = search(session, term)
        found = parse_search(html)
        for lig, e in found.items():
            seen.setdefault(lig, e)
        print(f"  search {term!r}: {len(found)} entries (cumulative {len(seen)})", file=sys.stderr)
        time.sleep(DELAY)
    return seen


# Field labels we keep (FR label substring -> canonical key).
FIELD_MAP = [
    ("Valeur faciale", "valeur_faciale"),
    ("création", "createur"),
    ("Mise en page", "mise_en_page"),
    ("Dentelure", "dentelure"),
    ("Couleur", "couleur"),
    ("Mode d'impression", "impression"),
    ("Format du timbre", "format"),
    ("Quantite émis", "tirage"),
    ("Bande phosphore", "bande_phosphore"),
    ("Catalogue Yvert et Tellier", "yvert"),
    ("Catalogue Maury", "maury"),
    ("Vente générale", "vente_generale"),
]


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = clean(soup.title.get_text()) if soup.title else ""

    year_m = re.search(r"émis en (\d{4})", title)
    page_year = year_m.group(1) if year_m else ""

    # Flatten the field block: strip script/style, turn tags into '|' separators.
    body = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S)
    flat = re.sub(r"<[^>]+>", "|", body)
    flat = re.sub(r"&nbsp;", " ", flat)
    flat = re.sub(r"[ \t]+", " ", flat)
    parts = [clean(p) for p in flat.split("|")]
    parts = [p for p in parts if p]

    # Pair "<label> :" with the following non-empty token.
    fields: dict[str, str] = {}
    for i, p in enumerate(parts):
        if not p.endswith(":"):
            continue
        label = p[:-1].strip()
        value = parts[i + 1] if i + 1 < len(parts) else ""
        if value.endswith(":"):  # next is another label, value missing
            value = ""
        for needle, key in FIELD_MAP:
            if needle.lower() in label.lower() and key not in fields:
                fields[key] = clean(value)
                break

    # Description (FR informational paragraph after "Informations sur le sujet").
    # Keep the French block (stop at the English "The Chinese ..." or "Source").
    desc = ""
    dm = re.search(
        r"Informations sur le sujet du timbre.*?>(.*?)(?:Source\b|The Chinese)",
        body,
        re.S,
    )
    if dm:
        desc = clean(re.sub(r"<[^>]+>", " ", dm.group(1)))

    # Large image (full-size stamp). Keep the leading "image/" so the relative
    # path resolves against the site root.
    img_m = re.search(r"(image/image-\d{4}/[^\"'<> ]+\.jpg)", html)
    image_rel = img_m.group(1) if img_m else ""

    return {
        "page_title": title,
        "page_year": page_year,
        "fields": fields,
        "description": desc,
        "image_rel": image_rel,
    }


def download(session: requests.Session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=60)
        r.raise_for_status()
        if not r.content:
            raise requests.RequestException("empty body")
        dest.write_bytes(r.content)
        return True
    except requests.RequestException as e:
        print(f"    ! image failed {url}: {e}", file=sys.stderr)
        return False


def scrape_year(session: requests.Session, year: str, entries: list[dict]) -> dict:
    year_dir = OUT_DIR / year
    img_dir = year_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    stamps: list[dict] = []
    title = ""
    for e in sorted(entries, key=lambda x: int(x["lig"])):
        lig = e["lig"]
        r = session.get(TIMBRE + lig, timeout=30)
        r.encoding = "utf-8"
        detail = parse_detail(r.text)
        title = title or detail["page_title"]

        image_rel = detail["image_rel"] or e["image_rel"]
        image_url = f"{BASE}/{image_rel}"
        stamp = {
            "lig": lig,
            "detail_url": TIMBRE + lig,
            "title": detail["page_title"],
            "fields": detail["fields"],
            "description": detail["description"],
            "image_url": image_url,
        }
        fname = f"{lig}_{Path(image_rel).name}"
        if download(session, image_url, img_dir / fname):
            stamp["image_file"] = f"img/{fname}"
        stamps.append(stamp)
        time.sleep(DELAY)

    record = {
        "code": year,
        "year": year,
        "zodiac_fr": ZODIAC_FR.get(int(year), ""),
        "title": title,
        "n_stamps": len(stamps),
        "stamps": stamps,
        "source": SOURCE,
    }
    (year_dir / "raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def build_index(by_year: dict[str, list[dict]]) -> list[dict]:
    idx = []
    for year in sorted(by_year):
        ligs = sorted(int(e["lig"]) for e in by_year[year])
        idx.append(
            {
                "code": year,
                "year": year,
                "zodiac_fr": ZODIAC_FR.get(int(year), ""),
                "n_pages": len(ligs),
                "ligs": [str(l) for l in ligs],
                "source": SOURCE,
            }
        )
    return idx


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true", help="only collect & print the lig index")
    args = ap.parse_args()

    session = make_session()
    print("Collecting lunar stamp pages via site search...", file=sys.stderr)
    ligs = collect_ligs(session)

    by_year: dict[str, list[dict]] = {}
    for e in ligs.values():
        by_year.setdefault(e["year"], []).append(e)
    print(f"Total lig pages: {len(ligs)} across {len(by_year)} years", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = build_index(by_year)
    (OUT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.list_only:
        for it in index:
            print(f"  {it['year']} {it['zodiac_fr']:8} pages={it['n_pages']:2} ligs={it['ligs']}")
        return

    for i, year in enumerate(sorted(by_year), 1):
        print(f"[{i}/{len(by_year)}] {year} {ZODIAC_FR.get(int(year),'')}", file=sys.stderr)
        try:
            rec = scrape_year(session, year, by_year[year])
            print(f"    {rec['n_stamps']} pages/images", file=sys.stderr)
        except Exception as ex:  # noqa: BLE001 - keep going on a single year failure
            print(f"    ! year failed: {ex}", file=sys.stderr)
        time.sleep(DELAY)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
