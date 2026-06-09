# /// script
# requires-python = ">=3.10"
# ///
"""Convert data/raw/cn-chinapost (scraped from 5151sc 点购收藏网) into catalog Issues.

Zodiac comes from the 干支 in each title (e.g.「庚申年（猴票）」→ 申 → 猴); the 地支
maps to the animal, sidestepping simplified/traditional name differences. China
issues its zodiac stamps at the start of the zodiac year, so zodiac_year == the
issue's Gregorian year. Round comes from the raw `round` field.

Source note: 5151sc is a commercial collector site, not an official postal or an
authoritative catalogue — registered as tier=secondary, verified=false, pending
verification against 中国邮政 / a graded catalogue.

D8: skip p* entries (珍藏册/大全套 merchandise bundles, not single issues) and any
set without an issue date (e.g. not-yet-issued). Images are copied to
public/img/stamps/cn/<code>/ (gitignored, like the TW images). Never overwrites.

Usage: uv run scripts/convert_cn.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

RAW = Path('data/raw/cn-chinapost')
OUT = Path('src/content/catalog')
IMG_DEST = Path('public/img/stamps/cn')

BRANCH_ANIMAL = {'子': '鼠', '丑': '牛', '寅': '虎', '卯': '兔', '辰': '龍', '巳': '蛇',
                 '午': '馬', '未': '羊', '申': '猴', '酉': '雞', '戌': '狗', '亥': '豬'}
EN = {'鼠': 'rat', '牛': 'ox', '虎': 'tiger', '兔': 'rabbit', '龍': 'dragon', '蛇': 'snake',
      '馬': 'horse', '羊': 'goat', '猴': 'monkey', '雞': 'rooster', '狗': 'dog', '豬': 'pig'}

# 天干含「已」以容忍來源把「己」誤寫成「已」(如 T133「已巳年」);地支才是取生肖的依據。
# 不強制「年」字(有的標題作「乙酉鸡」);呼叫前先去除零寬字元。
GANZHI_RE = re.compile(r'[甲乙丙丁戊己庚辛壬癸已]([子丑寅卯辰巳午未申酉戌亥])')
DATE_RE = re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日')
MD_RE = re.compile(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*发行')  # 「1月5日发行」
MARK_RE = re.compile(r'[（(]\s*\d+\s*-\s*\d+\s*[)）]')
VALUE_RE = re.compile(r'(\d[\d.]*)\s*(分|元)')
MINT_RE = re.compile(r'(\d[\d.]*)\s*万\s*[枚套]')


def parse_items(dfv: str) -> list[dict]:
    """Best-effort split of design_face_value into per-stamp items."""
    dfv = (dfv or '').strip()
    if not dfv:
        return []
    parts = MARK_RE.split(dfv)[1:]  # drop text before first marker
    items = []
    for seg in parts:
        seg = seg.strip()
        vm = VALUE_RE.search(seg)
        mm = MINT_RE.search(seg)
        desc = (seg[:vm.start()] if vm else seg)
        desc = re.sub(r'^[T\s]+', '', desc).strip()  # leading "T"/spaces
        item = {'type': 'stamp', 'description': desc, 'image': ''}
        if vm:
            item['denomination'] = {'value': float(vm.group(1)) if '.' in vm.group(1) else int(vm.group(1)),
                                    'currency': vm.group(2)}
        if mm:
            v = mm.group(1)
            item['mintage'] = int(float(v) * 10000) if '.' in v else int(v) * 10000
        items.append(item)
    return items


def main() -> None:
    dry = '--dry-run' in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    written = skipped = no_date = no_ganzhi = bundles = 0
    rows = []
    for d in sorted(RAW.iterdir()):
        if not d.is_dir():
            continue
        code = d.name
        if code.startswith('p'):  # D8: 珍藏册/大全套 bundles
            bundles += 1
            continue
        raw = json.loads((d / 'raw.json').read_text(encoding='utf-8'))
        f = raw.get('fields', {})
        title = (raw.get('list_title') or f.get('name', '')).replace('​', '').replace('﻿', '')
        desc = raw.get('description', '') or ''

        gm = GANZHI_RE.search(title)
        if not gm:
            no_ganzhi += 1
            print(f'  ! {code}: 標題無干支,跳過 -> {title}')
            continue
        branch = gm.group(1)
        animal = BRANCH_ANIMAL[branch]

        # Year: from the code prefix (编年 like 2007-1T) or, for T-series, the field date.
        # Never take the year from description (it cites unrelated comparison years).
        west_code = int(code[:4]) if code[:4].isdigit() else None
        full = DATE_RE.search(f.get('issue_date') or '')
        inferred = False
        if full:
            west = west_code or int(full.group(1))
            mm, dd = int(full.group(2)), int(full.group(3))
        else:
            west = west_code
            md = MD_RE.search(desc)
            if md:
                mm, dd = int(md.group(1)), int(md.group(2))
            else:
                mm, dd = 1, 5  # 中國生肖票近年慣例:1月5日(推定,verified=false)
                inferred = True
        if west is None:
            no_date += 1
            print(f'  · {code}: 無法判定年份,跳過 -> {title}')
            continue
        zyear = west  # China issues within the zodiac year
        rnd = raw.get('round') or ((west - 1980) // 12 + 1)

        slug = f'cn-{west}-{EN[animal]}-r{rnd}'
        out = OUT / f'{slug}.json'
        if out.exists():
            skipped += 1
            rows.append((slug, code, zyear, animal, 'skip(已存在)'))
            continue

        local_imgs = []
        for im in raw.get('images', []):
            src = d / im.get('image_file', '')
            if src.is_file():
                dest = IMG_DEST / code / src.name
                if not dry:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                local_imgs.append(f'/img/stamps/cn/{code}/{src.name}')

        items = parse_items(f.get('design_face_value', ''))
        if not items:
            items = [{'type': 'stamp', 'description': '', 'image': ''}]

        detail_url = raw.get('detail_url')
        src_entry = {'ref': 'cn-5151sc', 'tier': 'secondary'}
        if detail_url:
            src_entry['url'] = detail_url

        rec = {
            'id': slug,
            'region': {'code': 'CN', 'name': '中国邮政'},  # 官方簡體正名
            'zodiac': {'animal': animal, 'branch': branch},
            'zodiac_year': zyear,
            'issue_date': f'{west:04d}-{mm:02d}-{dd:02d}',
            'round': rnd,
            'series_name': '生肖郵票',
            'catalog_number': {'local': code, 'scott': None},
            'designer': '',
            'printer': '',
            'printing_process': '',
            'perforation': '',
            'items': items,
            'significance': '',
            'notes': ('【自動轉換自 5151sc 点购收藏网(commercial collector site, tier=secondary),'
                      '待以中国邮政官方/集郵目錄複核】 '
                      + ('（發行月日以中國生肖票近年 1/5 慣例推定,待官方複核）' if inferred else '')
                      + desc).strip(),
            'images': local_imgs,
            'sources': [src_entry],
            'verified': False,
            'updated_at': '2026-06-10',
        }
        rows.append((slug, code, zyear, animal, f'write({len(items)}枚,{len(local_imgs)}圖)'))
        if not dry:
            out.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        written += 1

    print(f'\nwritten={written} skipped(existing)={skipped} '
          f'no_date={no_date} no_ganzhi={no_ganzhi} bundles(p*)={bundles}')
    for slug, code, zyear, animal, act in rows:
        print(f'  {slug:22} [{code:8}] {zyear} {animal}  {act}')


main()
