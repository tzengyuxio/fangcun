#!/usr/bin/env python3
"""Backlog #8 — CN prose rewrite, batch 2: the 21 sparse modern entries
(round 3 2004-2015 + round 4 2016-2026). Same house style as batch 1.

Sparse by nature: significance carries round+animal+designer (designer from the
already-reliable structured field); notes left brief or empty where sources are
thin (per user: don't force it). Notable designs (2016/2023 黃永玉) get full notes
from verified web sources. Round-4 phrasing is kept count-neutral because items[]
currently holds only 1 stamp while round 4 is in fact 2-stamp sets (flagged
separately as a data-completeness fix).
"""
import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "src" / "content" / "catalog"

REWRITES = {
    # ---- Round 3 (2004-2015), genuinely single-stamp ----
    "cn-2004-1": {"significance": "第三輪生肖郵票首套，甲申猴年，陳紹華設計。", "notes": ""},
    "cn-2005-1": {"significance": "第三輪雞年票，呂勝中設計，另發行小本票。", "notes": ""},
    "cn-2007-1": {"significance": "第三輪豬年票，陳紹華設計。", "notes": ""},
    "cn-2008-1": {"significance": "第三輪鼠年票，於平、任憑設計，另發行小本票。", "notes": ""},
    "cn-2009-1": {"significance": "第三輪牛年票，陳紹華設計，另發行小本票。", "notes": ""},
    "cn-2010-1": {"significance": "第三輪虎年票，馬剛設計，另發行小本票。", "notes": ""},
    "cn-2011-1": {"significance": "第三輪兔年票，吳冠英設計。", "notes": ""},
    "cn-2012-1": {"significance": "第三輪龍年票，陳紹華設計，另發行小本票。", "notes": ""},
    "cn-2014-1": {"significance": "第三輪馬年票，甲午馬年。", "notes": ""},
    "cn-2015-1": {"significance": "第三輪羊年票，吳冠英設計。", "notes": ""},
    # ---- Round 4 (2016-2026); count-neutral phrasing (items[] 2nd stamp pending) ----
    "cn-2016-1": {
        "significance": "第四輪生肖郵票開篇之作，92 歲黃永玉於 1980 年「庚申金猴」之後 36 年再執畫筆。",
        "notes": "由 1980 年首枚猴票作者、九旬畫家黃永玉再度執筆。「靈猴獻瑞」繪金猴攀枝纏桃、手捧壽桃，寓捧桃獻瑞；「福壽雙至」繪金猴懷抱兩隻橘色小猴，象徵親情團圓、福壽雙至。",
    },
    "cn-2017-1": {"significance": "第四輪雞年票，藝術家韓美林設計。", "notes": ""},
    "cn-2018-1": {"significance": "第四輪狗年票，百歲畫家周令釗設計。", "notes": ""},
    "cn-2019-1": {"significance": "第四輪豬年票，韓美林設計。", "notes": ""},
    "cn-2020-1": {"significance": "第四輪鼠年票，韓美林設計。", "notes": ""},
    "cn-2021-1": {"significance": "第四輪牛年票，姚鍾華設計。", "notes": ""},
    "cn-2022-1": {"significance": "第四輪虎年票，工筆虎名家馮大中設計。", "notes": ""},
    "cn-2023-1": {
        "significance": "第四輪兔年票，99 歲黃永玉設計，「藍兔」造型引發網路熱議。",
        "notes": "由黃永玉設計，含《同圓共生》與《癸卯寄福》兩枚。《癸卯寄福》繪一手執筆、一手持信的全身藍兔，藍色諧音「藍圖」，寓百歲老人新春寄福；其紅眼藍身的奇特造型曾在網路引發「妖氣」熱議，也有評其敢於創新、延續黃永玉「頑童」風格。",
        "designer": "黃永玉",
    },
    "cn-2024-1": {"significance": "第四輪龍年票，王虎鳴設計。", "notes": ""},
    "cn-2025-1": {"significance": "第四輪蛇年票，潘虎、張旺設計。", "notes": ""},
    "cn-2026-1": {"significance": "第四輪馬年票，丙午馬年。", "notes": ""},
}


def main() -> None:
    changed = 0
    for sid, fields in REWRITES.items():
        p = CATALOG / f"{sid}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["significance"] = fields["significance"]
        d["notes"] = fields["notes"]
        if "designer" in fields and not d.get("designer"):
            d["designer"] = fields["designer"]
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed += 1
    print(f"rewrote {changed} sparse CN entries (batch 2)")


if __name__ == "__main__":
    main()
