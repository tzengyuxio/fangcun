#!/usr/bin/env python3
"""Convert CN entries' user-facing text fields Simplified -> Traditional (opencc s2t).

Scope: display text only. Canonical identifiers (id, catalog_number, dates, image
paths, sources ref) and structured numerics are left untouched. Idempotent
(already-Traditional text passes through unchanged). Uses opencc s2t (pure glyph
conversion, no Taiwan-vocabulary localization, faithful to mainland proper nouns).
"""
import json
import subprocess
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "src" / "content" / "catalog"
FIELDS = ["region.name", "series_name", "designer", "printer",
          "printing_process", "perforation"]  # + items[].description handled separately


def s2t_batch(strings):
    """Convert a list of strings via one opencc call (newline-joined)."""
    if not strings:
        return []
    joined = "\n".join(strings)
    out = subprocess.run(["opencc", "-c", "s2t.json"], input=joined,
                         capture_output=True, text=True, check=True).stdout
    res = out.split("\n")
    # opencc preserves line count; guard anyway
    return res[:len(strings)] + strings[len(res):]


def main():
    files = sorted(CATALOG.glob("cn-*.json"))
    # gather all strings to convert, with locations, then one batch call
    strings, locs = [], []  # locs: (file_idx, kind, key_or_index)
    docs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    for i, d in enumerate(docs):
        for f in FIELDS:
            if "." in f:
                k1, k2 = f.split(".")
                v = (d.get(k1) or {}).get(k2)
                if isinstance(v, str) and v:
                    strings.append(v); locs.append((i, "nested", (k1, k2)))
            else:
                v = d.get(f)
                if isinstance(v, str) and v:
                    strings.append(v); locs.append((i, "flat", f))
        for j, it in enumerate(d.get("items", [])):
            v = it.get("description")
            if isinstance(v, str) and v:
                strings.append(v); locs.append((i, "item", j))

    conv = s2t_batch(strings)
    for (i, kind, key), new in zip(locs, conv):
        d = docs[i]
        if kind == "flat":
            d[key] = new
        elif kind == "nested":
            d[key[0]][key[1]] = new
        elif kind == "item":
            d["items"][key]["description"] = new

    changed = 0
    for f, d in zip(files, docs):
        new_text = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
        if new_text != f.read_text(encoding="utf-8"):
            f.write_text(new_text, encoding="utf-8"); changed += 1
    print(f"converted display fields in {changed} CN files")


if __name__ == "__main__":
    main()
