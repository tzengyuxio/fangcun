# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Fetch 說文解字 (Shuowen Jiezi) small-seal-script SVGs from zi.tools.

For each character we query zi.tools' public API (/api/zi/<char>), read the
`swjz.glyph` id (swjz = 說文解字), and download the matching seal-script SVG
from its CDN. We also grab the simple animal icon_svg when present, as a backup.

Source / licensing: the glyph forms originate from 說文解字 (Xu Shen, c. 100 CE),
which is public domain; zi.tools merely vectorised them. We keep the files in the
repo with attribution (see docs/asset-sources.md).

Output:
  public/img/seal/<char>.svg        seal script (篆書)
  public/img/seal/icon/<char>.svg   simple line icon (animals only, best-effort)

Idempotent; skips files already downloaded. Usage: uv run scripts/fetch_seal_svgs.py
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import requests

API = 'https://zi.tools/api/zi/'
CDN = 'https://ziphoenicia-1300189285.cos.ap-shanghai.myqcloud.com'
OUT = Path('public/img/seal')
ICON_OUT = OUT / 'icon'

ZODIAC = list('鼠牛虎兔龍蛇馬羊猴雞狗豬')
THEME = ['全']
TIANGAN = list('甲乙丙丁戊己庚辛壬癸')
DIZHI = list('子丑寅卯辰巳午未申酉戌亥')
VARIANTS = list('貓猪')  # 越南卯=貓、日本亥=猪(野豬);其他變體動物日後再加
# 說文解字裡更道地的動物本字/象形:豕(豬本字)、犬(狗)、它(蛇本字,象蛇形)、
# 鼠/牛/虎… 已在 ZODIAC。一併備存供日後選用。
ORIGINALS = list('豕犬它')

ANIMALS = set(ZODIAC) | set(VARIANTS) | set(ORIGINALS)  # 這些另存簡圖 icon_svg

SEAL_RE = re.compile(r'"swjz":\{"glyph":\[\["([^"]+)"')


def seal_id(session: requests.Session, ch: str) -> str | None:
    r = session.get(API + requests.utils.quote(ch), timeout=30)
    r.raise_for_status()
    m = SEAL_RE.search(r.text)
    return m.group(1) if m else None


def download(session: requests.Session, url: str, dest: Path) -> bool:
    r = session.get(url, timeout=30)
    if r.status_code != 200 or b'NoSuchKey' in r.content[:200]:
        return False
    dest.write_bytes(r.content)
    return True


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ICON_OUT.mkdir(parents=True, exist_ok=True)
    chars = ZODIAC + THEME + TIANGAN + DIZHI + VARIANTS + ORIGINALS
    s = requests.Session()
    s.headers['User-Agent'] = 'fangcun-zodiac-stamps/0.2 (seal-script fetch; Shuowen Jiezi public domain)'

    ok = miss = skip = icons = 0
    for ch in chars:
        dest = OUT / f'{ch}.svg'
        if dest.exists():
            skip += 1
        else:
            try:
                sid = seal_id(s, ch)
            except Exception as e:  # noqa: BLE001
                print(f'  ! {ch}: API error {e}')
                miss += 1
                continue
            if not sid:
                print(f'  ! {ch}: 無 swjz glyph,跳過')
                miss += 1
                continue
            if download(s, f'{CDN}/swjz/{sid}.svg', dest):
                ok += 1
                print(f'  ✓ {ch} -> swjz/{sid}.svg')
            else:
                print(f'  ! {ch}: swjz/{sid}.svg 下載失敗')
                miss += 1
            time.sleep(0.3)

        # animal line-icon backup (best effort)
        if ch in ANIMALS:
            idest = ICON_OUT / f'{ch}.svg'
            if not idest.exists() and download(s, f'{CDN}/icon_svg/{requests.utils.quote(ch)}.svg', idest):
                icons += 1

    print(f'\nseal: ok={ok} skip(existing)={skip} miss={miss} | icons={icons}')
    print(f'files: {OUT}/  (+ {ICON_OUT}/ for animal icons)')


main()
