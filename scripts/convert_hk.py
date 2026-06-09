# /// script
# requires-python = ">=3.10"
# ///
"""Convert data/raw/hk-hongkongpost (歲次 生肖郵票) into catalog Issues.

Only the proper zodiac issue「歲次〈干支〉（X年）特別郵票」is taken; gold/silver
sheets (金銀郵票) and joint packs (聯合發行郵品) are skipped (D8). Zodiac comes
from the 干支 in the title; Hong Kong issues within the zodiac year, so
zodiac_year == issue year. Round from「第X輯」in the description.

NOTE: the current raw only covers 2026 — Hong Kong Post's site
(stamps.hongkongpost.hk) has the full 歲次 history and can be scraped for more.

Images copied to public/img/stamps/hk/<code>/ (gitignored). verified=false.

Usage: uv run scripts/convert_hk.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

RAW = Path('data/raw/hk-hongkongpost')
OUT = Path('src/content/catalog')
IMG_DEST = Path('public/img/stamps/hk')

BRANCH_ANIMAL = {'子': '鼠', '丑': '牛', '寅': '虎', '卯': '兔', '辰': '龍', '巳': '蛇',
                 '午': '馬', '未': '羊', '申': '猴', '酉': '雞', '戌': '狗', '亥': '豬'}
EN = {'鼠': 'rat', '牛': 'ox', '虎': 'tiger', '兔': 'rabbit', '龍': 'dragon', '蛇': 'snake',
      '馬': 'horse', '羊': 'goat', '猴': 'monkey', '雞': 'rooster', '狗': 'dog', '豬': 'pig'}
CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}

GANZHI_RE = re.compile(r'歲次[甲乙丙丁戊己庚辛壬癸]([子丑寅卯辰巳午未申酉戌亥])')
DATE_RE = re.compile(r'(\d{4})\s*[/年-]\s*(\d{1,2})\s*[/月-]\s*(\d{1,2})')
ROUND_RE = re.compile(r'第([一二三四五六七八九十]+)輯')


def main() -> None:
    dry = '--dry-run' in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    written = skipped = skip_special = 0
    for d in sorted(RAW.iterdir()):
        if not d.is_dir():
            continue
        code = d.name
        raw = json.loads((d / 'raw.json').read_text(encoding='utf-8'))
        title = raw.get('list_title') or raw.get('title') or ''
        if '特別郵票' not in title or '聯合' in title or '金銀' in title:
            skip_special += 1
            continue
        gm = GANZHI_RE.search(title)
        dm = DATE_RE.search(raw.get('issue_date') or '')
        if not gm or not dm:
            skip_special += 1
            print(f'  ! {code}: 非標準生肖票或無日期,跳過 -> {title}')
            continue
        animal = BRANCH_ANIMAL[gm.group(1)]
        west, mm, dd = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        zyear = west  # HK issues within the zodiac year

        desc = raw.get('description', '') or ''
        rm = ROUND_RE.search(desc)
        rnd = CN_NUM.get(rm.group(1), 1) if rm else max(1, (zyear - 1967) // 12 + 1)

        slug = f'hk-{west}-{EN[animal]}-r{rnd}'
        out = OUT / f'{slug}.json'
        if out.exists():
            skipped += 1
            continue

        seen = set()
        local_imgs = []
        for p in raw.get('products', []):
            f = p.get('image_file')
            if f and f not in seen and (d / f).is_file():
                seen.add(f)
                dest = IMG_DEST / code / Path(f).name
                if not dry:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(d / f, dest)
                local_imgs.append(f'/img/stamps/hk/{code}/{Path(f).name}')

        src_entry = {'ref': 'hk-hongkongpost', 'tier': 'official'}
        if raw.get('detail_url'):
            src_entry['url'] = raw['detail_url']

        rec = {
            'id': slug,
            'region': {'code': 'HK', 'name': '香港郵政'},
            'zodiac': {'animal': animal, 'branch': gm.group(1)},
            'zodiac_year': zyear,
            'issue_date': f'{west:04d}-{mm:02d}-{dd:02d}',
            'round': rnd,
            'series_name': '賀歲生肖郵票',
            'catalog_number': {'local': None, 'scott': None},
            'designer': '',
            'printer': '',
            'printing_process': '',
            'perforation': '',
            'items': [{'type': 'stamp', 'description': '', 'image': ''}],
            'significance': '',
            'notes': ('【自動轉換自香港郵政,待人工複核】 ' + desc).strip(),
            'images': local_imgs,
            'sources': [src_entry],
            'verified': False,
            'updated_at': '2026-06-10',
        }
        print(f'  ✓ {code} -> {slug} ({zyear} {animal}, 第{rnd}輯, {len(local_imgs)}圖)')
        if not dry:
            out.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        written += 1

    print(f'\nwritten={written} skipped(existing)={skipped} skip(special/non-zodiac)={skip_special}')


main()
