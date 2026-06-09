# /// script
# requires-python = ">=3.10"
# ///
"""Convert data/raw/post-tw (Chunghwa Post) into src/content/catalog Issues.

Zodiac is derived from the issue date (year-end issues belong to the NEXT
zodiac year; year-start issues to the current one), then cross-checked against
the description's 「年肖屬X」 when present.

D8: only D*/S* (新年／生肖郵票); skip B* (郵展小全張) and LD* (郵資票).
verified=false (auto-converted, awaiting human review); source tier=official.
Never overwrites an existing catalog file (preserves hand-verified seeds).

Usage: uv run scripts/convert_post_tw.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAW = Path('data/raw/post-tw')
OUT = Path('src/content/catalog')

# west_year % 12 -> 生肖
ZODIAC = ['猴', '雞', '狗', '豬', '鼠', '牛', '虎', '兔', '龍', '蛇', '馬', '羊']
BRANCH = {'鼠': '子', '牛': '丑', '虎': '寅', '兔': '卯', '龍': '辰', '蛇': '巳',
          '馬': '午', '羊': '未', '猴': '申', '雞': '酉', '狗': '戌', '豬': '亥'}
EN = {'鼠': 'rat', '牛': 'ox', '虎': 'tiger', '兔': 'rabbit', '龍': 'dragon', '蛇': 'snake',
      '馬': 'horse', '羊': 'goat', '猴': 'monkey', '雞': 'rooster', '狗': 'dog', '豬': 'pig'}
CLUE_NORM = {'犬': '狗'}  # description 用「犬」表示狗


def parse_minguo(s: str):
    m = re.search(r'民國(\d+)年(\d+)月(\d+)日', s or '')
    if not m:
        return None
    return int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3))


def main() -> None:
    dry = '--dry-run' in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    written = skipped = warned = 0
    rows = []
    for d in sorted(RAW.iterdir()):
        if not d.is_dir():
            continue
        code = d.name
        if not (code.startswith('D') or code.startswith('S')):  # D8: skip B*/LD*
            continue
        raw = json.loads((d / 'raw.json').read_text(encoding='utf-8'))
        fields = raw.get('detail_fields', {})
        date = parse_minguo(fields.get('發行日期') or raw.get('list_issue_date', ''))
        if not date:
            print(f'  ! {code}: 無法解析發行日,跳過')
            continue
        west, mm, dd = date
        # 非「新年郵票」者(如「特302生肖郵票」全 12 生肖主題票)不屬單一生肖/生肖年。
        is_theme = '新年' not in (raw.get('list_name', '') or '')
        if is_theme:
            zyear = animal = None
            rnd = 1  # schema 要求正整數;主題票無輪次,顯示時隱藏
            slug = f'tw-{west}-zodiac-set'
        else:
            zyear = west + 1 if mm >= 10 else west
            animal = ZODIAC[zyear % 12]

            cm = re.search(r'年肖屬(.)', raw.get('description', ''))
            if cm:
                clue = CLUE_NORM.get(cm.group(1), cm.group(1))
                if clue != animal:
                    print(f'  ⚠ {code}: 日期推算={animal} 但 description={clue}（生肖年 {zyear}）')
                    warned += 1

            rnd = (west - 1968) // 12 + 1
            slug = f'tw-{west}-{EN[animal]}-r{rnd}'
        out = OUT / f'{slug}.json'
        if out.exists():
            skipped += 1
            rows.append((slug, west, zyear, animal, 'skip(種子/重複)'))
            continue

        name = (fields.get('郵票名稱') or raw.get('list_name', '')).strip('「」')
        series = re.sub(r'[（(]\d+年版[)）]', '', re.sub(r'^特?\d+\s*', '', name)).strip()
        lm = re.search(r'(特|紀)\d+', raw.get('list_name', ''))
        local = lm.group(0) if lm else None

        items = [{
            'type': 'stamp',
            'denomination': {'value': None, 'currency': 'TWD'},
            'mintage': None,
            'description': st.get('title', ''),
            'image': st.get('image_url', ''),
        } for st in raw.get('stamps', [])]
        if not items:
            items = [{'type': 'stamp', 'denomination': {'value': None, 'currency': 'TWD'},
                      'description': '', 'image': ''}]

        rec = {
            'id': slug,
            'region': {'code': 'TW', 'name': '中華郵政'},
            'zodiac': None if is_theme else {'animal': animal, 'branch': BRANCH[animal]},
            'zodiac_year': zyear,
            'issue_date': f'{west:04d}-{mm:02d}-{dd:02d}',
            'round': rnd,
            'series_name': series or ('生肖郵票' if is_theme else '新年郵票'),
            'catalog_number': {'local': local, 'scott': None},
            'designer': fields.get('設計者') or fields.get('繪圖者') or '',
            'printer': fields.get('承印者') or '',
            'printing_process': fields.get('印法') or '',
            'perforation': fields.get('齒度') or '',
            'items': items,
            'significance': '',
            'notes': ('【自動轉換自中華郵政「郵票寶藏」詳情頁,待人工複核】 '
                      + (raw.get('description', '') or '')).strip(),
            'images': [raw['list_thumb']] if raw.get('list_thumb') else [],
            'sources': [{'ref': 'post-stamphouse', 'tier': 'official'}],
            'verified': False,
            'updated_at': '2026-06-10',
        }
        rows.append((slug, west, zyear, animal, 'write'))
        if not dry:
            out.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        written += 1

    print(f'\nwritten={written} skipped(existing)={skipped} warned={warned}')
    for slug, west, zyear, animal, act in rows:
        print(f'  {slug:26} 發行{west} 生肖年{zyear or "—"} {animal or "全12生肖"}  {act}')


main()
