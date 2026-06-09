# /// script
# requires-python = ">=3.10"
# ///
"""Convert data/raw/jp-japanpost (年賀切手) into catalog Issues.

Two raw shapes are present:
  - dorama (older years): has `zodiac` (animal char), `issue_date` (Y/M/D),
    `denomination`, `design`; source jp-dorama (tier=reference).
  - japanpost archive (recent years): has `date` (Y/M/D ...), `detail_url`;
    source jp-japanpost-archive (tier=official). Zodiac derived from the date.

年賀切手 issued in the latter half of a year are for the NEXT zodiac year, so
zodiac_year = issue_year (+1 if issued in month >= 7). 亥 maps to the 12-animal
enum 豬 (Japan calls it 猪/wild boar — a variant for later, see backlog).

Images copied to public/img/stamps/jp/<year>/ (gitignored). verified=false.
Never overwrites (preserves the hand-made jp-1950 seed).

Usage: uv run scripts/convert_jp.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

RAW = Path('data/raw/jp-japanpost')
OUT = Path('src/content/catalog')
IMG_DEST = Path('public/img/stamps/jp')

ZODIAC = ['猴', '雞', '狗', '豬', '鼠', '牛', '虎', '兔', '龍', '蛇', '馬', '羊']  # west % 12
EN = {'鼠': 'rat', '牛': 'ox', '虎': 'tiger', '兔': 'rabbit', '龍': 'dragon', '蛇': 'snake',
      '馬': 'horse', '羊': 'goat', '猴': 'monkey', '雞': 'rooster', '狗': 'dog', '豬': 'pig'}
BRANCH = {'鼠': '子', '牛': '丑', '虎': '寅', '兔': '卯', '龍': '辰', '蛇': '巳',
          '馬': '午', '羊': '未', '猴': '申', '雞': '酉', '狗': '戌', '豬': '亥'}
# dorama 用日本漢字寫生肖,正規化到本站 12-enum
JP_NORM = {'寅': '虎', '丑': '牛', '卯': '兔', '辰': '龍', '巳': '蛇', '午': '馬', '未': '羊',
           '申': '猴', '酉': '雞', '戌': '狗', '亥': '豬', '子': '鼠',
           '龙': '龍', '马': '馬', '鸡': '雞', '猪': '豬', '猫': '貓'}
DATE_RE = re.compile(r'(\d{4})\s*[/年-]\s*(\d{1,2})\s*[/月-]\s*(\d{1,2})')


def first_source(src):
    if isinstance(src, dict):
        return src
    if isinstance(src, list) and src:
        return src[0]
    return {'id': 'jp-dorama', 'tier': 'reference'}


def main() -> None:
    dry = '--dry-run' in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    written = skipped = bad = 0
    rows = []
    for d in sorted(RAW.iterdir()):
        if not d.is_dir():
            continue
        code = d.name
        raw = json.loads((d / 'raw.json').read_text(encoding='utf-8'))

        # 年份以「目錄名」為錨(可靠):dorama dir = 年用目標年(=生肖年);archive dir =
        # 發行年。日期欄位只取月/日(來源年份偶有損壞,如 1985 寫成 1684)。
        code_year = int(code) if code.isdigit() and 1945 <= int(code) <= 2100 else None
        is_dorama = bool(raw.get('zodiac'))
        dm = DATE_RE.search(raw.get('issue_date') or raw.get('date') or '')
        mm = int(dm.group(2)) if dm else 1
        dd = int(dm.group(3)) if dm else 1
        if not (1 <= mm <= 12):
            mm = 1
        if not (1 <= dd <= 31):
            dd = 1
        date_year = int(dm.group(1)) if dm else None
        date_year_ok = bool(date_year and 1945 <= date_year <= 2100)
        if code_year is None:
            bad += 1
            print(f'  ! {code}: 目錄名非有效年份,跳過')
            continue
        if is_dorama:
            zyear = code_year                       # dir = 年用目標(生肖)年
            iyear = date_year if date_year_ok else (zyear - 1 if mm >= 7 else zyear)
        else:
            iyear = code_year                       # archive dir = 發行年
            zyear = iyear + 1 if mm >= 7 else iyear  # 年賀:下半年發行 = 次年生肖

        animal = ZODIAC[zyear % 12]
        zchar = raw.get('zodiac')
        if zchar:  # dorama 有明確生肖,正規化後交叉檢查
            norm = JP_NORM.get(zchar, zchar)
            if norm in EN:
                if norm != animal:
                    print(f'  ⚠ {code}: 日期推算={animal} 但 raw.zodiac={norm}（用 raw）')
                animal = norm

        rnd = (zyear - 1950) // 12 + 1
        slug = f'jp-{iyear}-{EN[animal]}-r{rnd}'
        out = OUT / f'{slug}.json'
        if out.exists():
            skipped += 1
            rows.append((slug, code, zyear, animal, 'skip(種子/重複)'))
            continue

        local_imgs = []
        f = raw.get('image_file')
        if f and (d / f).is_file():
            dest = IMG_DEST / code / Path(f).name
            if not dry:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(d / f, dest)
            local_imgs.append(f'/img/stamps/jp/{code}/{Path(f).name}')

        item = {'type': 'stamp', 'description': raw.get('design', '') or '', 'image': ''}
        denom = raw.get('denomination')
        if denom:
            m = re.match(r'([\d.]+)\s*(円|圓|銭)', denom)
            if m:
                item['denomination'] = {'value': float(m.group(1)) if '.' in m.group(1) else int(m.group(1)),
                                        'currency': m.group(2)}

        src = first_source(raw.get('source'))
        src_entry = {'ref': src.get('id', 'jp-dorama'), 'tier': src.get('tier', 'reference')}
        if raw.get('detail_url'):
            src_entry['url'] = raw['detail_url']

        rec = {
            'id': slug,
            'region': {'code': 'JP', 'name': '日本郵便'},
            'zodiac': {'animal': animal, 'branch': BRANCH[animal]},
            'zodiac_year': zyear,
            'issue_date': f'{iyear:04d}-{mm:02d}-{dd:02d}',
            'round': rnd,
            'series_name': '年賀郵票',
            'catalog_number': {'local': None, 'scott': None},
            'designer': '',
            'printer': '',
            'printing_process': '',
            'perforation': '',
            'items': [item],
            'significance': '',
            'notes': ('【自動轉換自' + ('日本郵便切手アーカイブ' if src_entry['ref'].endswith('archive')
                      else '年賀切手データベース(dorama)') + ',待人工複核】 '
                      + (raw.get('title', '') or '')).strip(),
            'images': local_imgs,
            'sources': [src_entry],
            'verified': False,
            'updated_at': '2026-06-10',
        }
        rows.append((slug, code, zyear, animal, 'write'))
        if not dry:
            out.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        written += 1

    print(f'\nwritten={written} skipped(existing)={skipped} bad={bad}')
    for slug, code, zyear, animal, act in rows:
        print(f'  {slug:24} [{code}] 生肖年{zyear} {animal}  {act}')


main()
