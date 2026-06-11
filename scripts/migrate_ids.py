#!/usr/bin/env python3
"""One-shot migration to canonical issue IDs (docs/id-scheme.md v1).

Old: {region}-{year}-{animal}-r{round}   New: {region}-{designator}[+collision]
  - Track A (TW, CN): official catalogue code -> token + number (no zero-pad).
  - Track B (HK, JP, ...): issue_date yyyymmdd; same-day collisions get -a/-b/-c
    suffix ordered by series_name (deterministic freeze).

Operates on raw file text (replaces every old id -> new id, guarded by id-char
lookarounds) so the internal "id" field AND in-notes cross-refs both update with
zero JSON reformatting. Then `git mv` renames the files.

Default = dry-run (prints the mapping, writes nothing). Pass --apply to execute.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "src" / "content" / "catalog"

# Track A category char -> ASCII token (docs/id-scheme.md §4).
TW_TOKEN = {"紀": "comm", "特": "sp", "常": "def", "航": "air",
            "欠": "due", "軍": "mil", "慈": "cha"}

TRACK_A_REGIONS = {"tw", "cn"}


def designator_track_a(region: str, local: str, series: str) -> str:
    """Derive Track A designator from the official catalogue code."""
    raw = (local or "").strip()
    if not raw:
        # fallback: pull the code out of series_name, e.g. "特 598 新年郵票"
        m = re.search(r"([紀特常航欠軍慈])\s*0*(\d+)", series)
        if not m:
            raise ValueError(f"[{region}] no catalogue code in local or series: {series!r}")
        raw = m.group(1) + m.group(2)

    if region == "tw":
        m = re.match(r"^([紀特常航欠軍慈])\s*0*(\d+)$", raw)
        if not m:
            raise ValueError(f"[tw] unparseable local {raw!r}")
        cat, num = m.group(1), str(int(m.group(2)))  # int() strips leading zeros
        return f"{TW_TOKEN[cat]}{num}"

    # cn: Latin-prefixed (T146/J123) -> lowercase; year-based (1992-1, also the
    # 5151sc "2004-1T" variant) -> keep "YYYY-N", drop any trailing letter.
    if re.match(r"^[A-Za-z]+\d+$", raw):
        return raw.lower()
    m = re.match(r"^(\d{4}-\d+)[A-Za-z]?$", raw)
    if m:
        return m.group(1)
    raise ValueError(f"[cn] unexpected local format {raw!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    args = ap.parse_args()

    files = sorted(CATALOG.glob("*.json"))
    rows = []  # (path, region, old_id, designator|None, date, series)
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        region = d["region"]["code"].lower()
        old_id = d.get("id") or f.stem
        if old_id != f.stem:
            print(f"⚠ id/filename mismatch: {f.name} has id={old_id!r}", file=sys.stderr)
        rows.append({
            "path": f, "region": region, "old": old_id,
            "date": d["issue_date"],
            "series": d.get("series_name", ""),
            "zodiac": d.get("zodiac"),  # None = companion product (gold-silver, etc.)
            "local": (d.get("catalog_number") or {}).get("local") or "",
        })

    # --- compute new ids ---
    mapping: dict[str, str] = {}
    errors = []
    # Track A first
    for r in rows:
        if r["region"] in TRACK_A_REGIONS:
            try:
                r["new"] = f"{r['region']}-{designator_track_a(r['region'], r['local'], r['series'])}"
            except ValueError as e:
                errors.append(str(e)); r["new"] = None

    # Track B: group by (region, date), suffix collisions by series_name order
    from collections import defaultdict
    groups = defaultdict(list)
    for r in rows:
        if r["region"] not in TRACK_A_REGIONS:
            groups[(r["region"], r["date"])].append(r)
    for (region, date), members in groups.items():
        ymd = date.replace("-", "")
        base = f"{region}-{ymd}"
        if len(members) == 1:
            members[0]["new"] = base
        else:
            # principal issue (zodiac != null) first -> -a; companions follow,
            # tie-broken by series_name. Deterministic, frozen once assigned.
            order = sorted(members, key=lambda x: (x["zodiac"] is None, x["series"]))
            for i, r in enumerate(order):
                r["new"] = f"{base}-{chr(ord('a') + i)}"

    for r in rows:
        if r.get("new"):
            mapping[r["old"]] = r["new"]

    # --- integrity checks ---
    dup = {}
    for old, new in mapping.items():
        dup.setdefault(new, []).append(old)
    collisions = {n: o for n, o in dup.items() if len(o) > 1}

    # --- report ---
    by_region = defaultdict(list)
    for r in rows:
        by_region[r["region"]].append(r)
    for region in ("tw", "cn", "hk", "jp"):
        rs = sorted(by_region[region], key=lambda x: x["old"])
        print(f"\n=== {region.upper()} ({len(rs)}) ===")
        for r in rs:
            flag = ""
            if r.get("new") and "-" in r["new"].split("-", 1)[1] and r["region"] not in TRACK_A_REGIONS and r["new"][-2] == "-":
                flag = "  ⟵ same-day collision"
            print(f"  {r['old']:32s} → {r.get('new') or '!! FAILED'}{flag}")

    print(f"\n--- {len(mapping)} renames; cross-ref-bearing files updated in same pass ---")
    if errors:
        print("\n‼ PARSE ERRORS:")
        for e in errors:
            print("  " + e)
    if collisions:
        print("\n‼ NEW-ID COLLISIONS (must resolve before apply):")
        for n, olds in collisions.items():
            print(f"  {n} ← {olds}")
    if errors or collisions:
        print("\nAborting (errors present). No changes made.")
        return 1

    if not args.apply:
        print("\n[dry-run] No files changed. Re-run with --apply to execute.")
        return 0

    # --- apply: text-replace all old->new across every file, then git mv ---
    # Guard with id-char lookarounds so partial ids never match.
    pairs = sorted(mapping.items(), key=lambda kv: -len(kv[0]))
    pattern = re.compile(
        r"(?<![a-z0-9-])(" + "|".join(re.escape(o) for o, _ in pairs) + r")(?![a-z0-9-])"
    )
    for r in rows:
        text = r["path"].read_text(encoding="utf-8")
        new_text = pattern.sub(lambda m: mapping[m.group(1)], text)
        if new_text != text:
            r["path"].write_text(new_text, encoding="utf-8")
    # rename files via git mv (preserve history)
    repo_root = CATALOG.parents[2]
    for r in rows:
        new_path = r["path"].with_name(r["new"] + ".json")
        if new_path != r["path"]:
            subprocess.run(["git", "mv", str(r["path"]), str(new_path)],
                           check=True, cwd=repo_root)
    print(f"\n✓ Applied {len(mapping)} renames + cross-ref updates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
