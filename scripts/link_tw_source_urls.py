# /// script
# requires-python = ">=3.10"
# ///
"""Point each TW catalog Issue's official source at its specific stamphouse page.

The shared Source `post-stamphouse` only has the generic index.jsp URL. Each
raw set, however, carries a per-set `detail_url` (…?file_name=D055…). This adds
that URL as a per-issue override on the `post-stamphouse` source entry, so the
detail page links straight to the right stamp instead of the landing page.

Slug derivation mirrors scripts/convert_post_tw.py (date-based zodiac). Only the
`post-stamphouse` entry is touched; idempotent.

Usage: uv run scripts/link_tw_source_urls.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAW = Path('data/raw/post-tw')
CATALOG = Path('src/content/catalog')

ZODIAC = ['猴', '雞', '狗', '豬', '鼠', '牛', '虎', '兔', '龍', '蛇', '馬', '羊']
EN = {'鼠': 'rat', '牛': 'ox', '虎': 'tiger', '兔': 'rabbit', '龍': 'dragon', '蛇': 'snake',
      '馬': 'horse', '羊': 'goat', '猴': 'monkey', '雞': 'rooster', '狗': 'dog', '豬': 'pig'}


def parse_minguo(s: str):
    m = re.search(r'民國(\d+)年(\d+)月(\d+)日', s or '')
    return (int(m.group(1)) + 1911, int(m.group(2))) if m else None


def main() -> None:
    dry = '--dry-run' in sys.argv

    # build slug -> detail_url from raw
    slug_url: dict[str, str] = {}
    for d in sorted(RAW.iterdir()):
        if not d.is_dir() or not (d.name.startswith('D') or d.name.startswith('S')):
            continue
        raw = json.loads((d / 'raw.json').read_text(encoding='utf-8'))
        url = raw.get('detail_url')
        if not url:
            continue
        date = parse_minguo(raw.get('detail_fields', {}).get('發行日期') or raw.get('list_issue_date', ''))
        if not date:
            continue
        west, mm = date
        if '新年' not in (raw.get('list_name', '') or ''):  # 全 12 生肖主題票
            slug_url[f'tw-{west}-zodiac-set'] = url
            continue
        zyear = west + 1 if mm >= 10 else west
        animal = ZODIAC[zyear % 12]
        rnd = (west - 1968) // 12 + 1
        slug_url[f'tw-{west}-{EN[animal]}-r{rnd}'] = url

    updated = missing = 0
    for jf in sorted(CATALOG.glob('tw-*.json')):
        slug = jf.stem
        url = slug_url.get(slug)
        if not url:
            missing += 1
            continue
        data = json.loads(jf.read_text(encoding='utf-8'))
        changed = False
        for s in data.get('sources', []):
            if s.get('ref') == 'post-stamphouse' and s.get('url') != url:
                s['url'] = url
                changed = True
        if changed:
            updated += 1
            if not dry:
                jf.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    tag = '[dry-run] ' if dry else ''
    print(f'{tag}updated {updated} catalog files; {missing} tw files without a raw detail_url match')


main()
