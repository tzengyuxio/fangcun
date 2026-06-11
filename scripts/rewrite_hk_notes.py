#!/usr/bin/env python3
"""Backlog #8 — clean HK zodiac-stamp notes.

HK significance is already curated (85/86). The notes carry source-segment
markers and, in 31 entries, long stampshk marketing prose. Per the agreed house
style we: strip every 【…】/〔…〕 marker, drop the catalogue "細節待補" placeholder,
remove the stampshk marketing dump and the 〔WNS〕 provenance line, and clean the
"…待補" meta-phrases — keeping only the factual newsletter cross-refs (which
issues were released the same day). Segments are split on blank lines.

hk-20260105-a (empty significance + a long official 香港郵政 dump) is handled
separately afterwards. verified stays false; raw originals remain in data/raw.
"""
import json
import re
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "src" / "content" / "catalog"

# "…待補" status phrases to drop from kept newsletter text.
META = [
    "設計／承印者／齒孔等規格未見於來源文字，待補。",
    "面值、枚數、設計者等細節待補。",
    "面值、設計等細節待補。",
    "圖片暫無可得來源，待補。",
    "單枚面值未見於來源 newsletter，待補。",
    "面值待補。",
]
# segment header -> action
DROP_PREFIXES = ("〔hkstmp", "〔stampshk", "〔WNS〕")
KEEP_HEADERS = ("〔香港郵政集郵組 newsletter〕", "〔香港郵政集郵組〕", "〔香港郵政〕")


def clean_notes(notes: str) -> str:
    segs = [s.strip() for s in notes.split("\n\n") if s.strip()]
    kept = []
    for s in segs:
        if s.startswith("【") and s.endswith("】"):
            continue  # bare marker line
        if s.startswith(DROP_PREFIXES):
            continue  # catalogue placeholder / stampshk dump / WNS line
        matched = next((h for h in KEEP_HEADERS if s.startswith(h)), None)
        if matched:
            body = s[len(matched):].strip()
            for m in META:
                body = body.replace(m, "")
            body = re.sub(r"\s+", " ", body).strip()
            if body:
                kept.append(body)
            continue
        # any other stray text (shouldn't happen) -> keep trimmed
        kept.append(re.sub(r"\s+", " ", s).strip())
    return "\n\n".join(kept)


def main() -> None:
    changed = 0
    for p in sorted(CATALOG.glob("hk-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if p.stem == "hk-20260105-a":
            continue  # special-cased below
        new = clean_notes(d.get("notes", ""))
        if new != d.get("notes", ""):
            d["notes"] = new
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    print(f"cleaned notes in {changed} HK entries")


if __name__ == "__main__":
    main()
