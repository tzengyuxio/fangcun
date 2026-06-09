# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Upgrade CN zodiac issues (2007–2026) with official 国家邮政局《新邮赏析》data.

spb.gov.cn (State Post Bureau) is an official source. Its 新邮赏析 channel lists
every issue back to ~2007; the AJAX list endpoint returns JSON, and each detail
page is static HTML with the official issue date, an appreciation text, and the
official stamp images.

For each zodiac article (title「YYYY-1 干支年」) we:
  - read the official issue date (定于YYYY年M月D日) and appreciation text,
  - download the official images to public/img/stamps/cn/<code>/spb_*,
  - upgrade the matching catalog Issue: prepend an official source (spb-gjyzj),
    set the official date, replace images[] with the official ones, and put the
    official appreciation into notes.

5151sc stays as a secondary source. verified stays false (auto-pulled, not yet
human-checked) but the tier is now official. Idempotent-ish: re-running refreshes
the spb fields. Usage: uv run scripts/upgrade_cn_spb.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests

CHANNEL = '0521b56a6e5043f2b05e538df8befad9'  # 新邮赏析
SEARCH = f'https://www.spb.gov.cn/common/search/{CHANNEL}?_isAgg=true&_isJson=true&_template=index&_pageSize=800'
CATALOG = Path('src/content/catalog')
IMG_ROOT = Path('public/img/stamps/cn')

UA = 'fangcun-zodiac-stamps/0.2 (catalog enrichment; official spb.gov.cn data)'
ZODIAC_TITLE = re.compile(r'(\d{4})-1\s*[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]年')
DATE_RE = re.compile(r'定于\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日')
IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
TAG_RE = re.compile(r'<[^>]+>')


def clean_text(html: str) -> str:
    # grab the appreciation body: from「(中国邮政…)定于」onward, strip tags/space
    m = re.search(r'((?:中国邮政|国家邮政局)[^<]{0,40}定于.*?)(?:版权所有|主办单位|相关链接|扫一扫|</body)', html, re.S)
    body = m.group(1) if m else ''
    body = TAG_RE.sub('', body)
    body = re.sub(r'[\s　]+', ' ', body).strip()
    return body[:1500]


def main() -> None:
    dry = '--dry-run' in sys.argv
    s = requests.Session()
    s.headers['User-Agent'] = UA

    res = s.get(SEARCH, timeout=40).json()['data']['results']
    zod = []
    for r in res:
        title = (r.get('title') or '').replace('　', ' ')
        m = ZODIAC_TITLE.search(title)
        if m:
            zod.append((int(m.group(1)), title.strip(), r.get('url')))
    zod.sort()
    print(f'新邮赏析 generic={len(res)} -> 生肖 articles={len(zod)}')

    upgraded = no_match = 0
    for year, title, url in zod:
        files = sorted(CATALOG.glob(f'cn-{year}-*.json'))
        if not files:
            no_match += 1
            print(f'  ? {year} {title}: 無對應 catalog,跳過')
            continue
        jf = files[0]
        data = json.loads(jf.read_text(encoding='utf-8'))
        html = s.get(url, timeout=40).content.decode('utf-8', 'replace')

        dm = DATE_RE.search(html)
        if dm:
            data['issue_date'] = f'{int(dm.group(1)):04d}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}'

        code = (data.get('catalog_number') or {}).get('local') or str(year)
        imgs = []
        for raw_src in IMG_RE.findall(html):
            if 'conac.cn' in raw_src or '/public/' in raw_src or 'images/public' in raw_src:
                continue
            full = urljoin(url, raw_src)
            if not full.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            ext = '.' + full.rsplit('.', 1)[1]
            name = f'spb_{len(imgs) + 1}{ext}'
            dest = IMG_ROOT / code / name
            if not dry:
                try:
                    b = s.get(full, timeout=40).content
                    if b[:200].find(b'NoSuchKey') == -1 and len(b) > 500:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(b)
                        imgs.append(f'/img/stamps/cn/{code}/{name}')
                except Exception:  # noqa: BLE001
                    pass
            else:
                imgs.append(f'/img/stamps/cn/{code}/{name}')
        if imgs:
            data['images'] = imgs
            for it in data.get('items', []):
                it['image'] = ''  # 官方圖未逐枚對應,統一走 images[]

        # sources: official spb first, keep existing (5151sc) after, de-dup spb
        srcs = [x for x in data.get('sources', []) if x.get('ref') != 'spb-gjyzj']
        data['sources'] = [{'ref': 'spb-gjyzj', 'tier': 'official', 'url': url}] + srcs

        desc = clean_text(html)
        data['notes'] = ('【官方·國家郵政局《新郵賞析》】 ' + desc) if desc else \
            '【官方來源:國家郵政局《新郵賞析》;另有 5151sc 商業目錄參照】'
        data['updated_at'] = '2026-06-10'

        if not dry:
            jf.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        upgraded += 1
        print(f'  ✓ {year} {title} -> {jf.name} (date={data["issue_date"]}, {len(imgs)}圖)')

    print(f'\nupgraded={upgraded} no_match={no_match}')


main()
