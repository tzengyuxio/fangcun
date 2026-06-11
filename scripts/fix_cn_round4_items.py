#!/usr/bin/env python3
"""Fix CN round-4 (2016-2026) items: each set is in fact TWO stamps, 1.20元 each,
but our items[] held a single bare placeholder. Populate both stamps with their
official vignette names (cross-verified from China Post / 国家邮政局 / 百度百科 via
a research pass) and denomination. 2023 also gets its UPU/WADP WNS numbers
(CN001/CN002.2023, confirmed via wns-query). Names stored in Traditional.
"""
import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "src" / "content" / "catalog"

# year -> (stamp1 name, stamp2 name); all 36x36mm, 1.20元 each, issued Jan 5.
DATA = {
    "cn-2016-1": ("靈猴獻瑞", "福壽雙至"),
    "cn-2017-1": ("意氣風發", "丁酉大吉"),
    "cn-2018-1": ("犬守平安", "家和業興"),
    "cn-2019-1": ("肥豬旺福", "五福齊聚"),
    "cn-2020-1": ("子鼠開天", "鼠兆豐年"),
    "cn-2021-1": ("奮發圖強", "牛年大吉"),
    "cn-2022-1": ("國運昌隆", "虎蘊吉祥"),
    "cn-2023-1": ("癸卯寄福", "同圓共生"),  # (2-1) / (2-2), per official order
    "cn-2024-1": ("天龍行健", "辰龍獻瑞"),
    "cn-2025-1": ("蛇呈豐稔", "福納百祥"),
    "cn-2026-1": ("馳躍宏圖", "萬駿臻福"),
}
WNS = {"cn-2023-1": ("CN001.2023", "CN002.2023")}


def make_item(name, wns=None):
    it = {
        "type": "stamp",
        "denomination": {"value": 1.2, "currency": "元"},
        "dimensions_mm": {"w": 36.0, "h": 36.0},
        "description": name,
        "image": "",
    }
    if wns:
        it["wns"] = wns
    return it


def main():
    for sid, (n1, n2) in DATA.items():
        p = CATALOG / f"{sid}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        w = WNS.get(sid, (None, None))
        d["items"] = [make_item(n1, w[0]), make_item(n2, w[1])]
        # 2023 notes had the two vignettes in reversed order; fix to (2-1) first.
        if sid == "cn-2023-1":
            d["notes"] = d["notes"].replace(
                "含《同圓共生》與《癸卯寄福》兩枚", "含《癸卯寄福》與《同圓共生》兩枚")
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"fixed {len(DATA)} CN round-4 entries to 2-stamp sets")


if __name__ == "__main__":
    main()
