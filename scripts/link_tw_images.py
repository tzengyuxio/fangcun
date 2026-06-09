# /// script
# requires-python = ">=3.10"
# ///
"""Copy scraped Chunghwa Post images into public/ and point catalog at them.

Interim step (see docs/backlog.md): use the already-scraped raw images as
placeholders until proper scans replace them. Images are NOT version-controlled
(public/img/stamps/ is gitignored); on GitHub Pages they 404 and the page falls
back to public/img/stamp-fallback.svg via <img onerror>. Locally (npm run dev)
the real images are present and show.

What it does:
1. Flatten-copy data/raw/post-tw/{D,S}*/img/* into public/img/stamps/tw/.
2. Rewrite every post.gov.tw image URL in src/content/catalog/tw-*.json
   (images[] and items[].image) to /img/stamps/tw/<basename>.

Idempotent. Seeds with hand-curated local paths are left untouched.

Usage: uv run scripts/link_tw_images.py [--dry-run]
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

RAW = Path('data/raw/post-tw')
DEST = Path('public/img/stamps/tw')
CATALOG = Path('src/content/catalog')


def to_local(url: str) -> str | None:
    """post.gov.tw image URL -> /img/stamps/tw/<basename>, else None."""
    if isinstance(url, str) and 'post.gov.tw' in url and '/' in url:
        return f'/img/stamps/tw/{url.rsplit("/", 1)[1]}'
    return None


def main() -> None:
    dry = '--dry-run' in sys.argv

    # 1. copy images
    copied = 0
    if not dry:
        DEST.mkdir(parents=True, exist_ok=True)
    for d in sorted(RAW.iterdir()):
        if not d.is_dir() or not (d.name.startswith('D') or d.name.startswith('S')):
            continue
        img_dir = d / 'img'
        if not img_dir.is_dir():
            continue
        for f in sorted(img_dir.iterdir()):
            if f.is_file():
                if not dry:
                    shutil.copy2(f, DEST / f.name)
                copied += 1

    # 2. rewrite catalog image fields
    rewritten = files_touched = 0
    for jf in sorted(CATALOG.glob('tw-*.json')):
        data = json.loads(jf.read_text(encoding='utf-8'))
        changed = False

        imgs = data.get('images') or []
        for i, u in enumerate(imgs):
            loc = to_local(u)
            if loc:
                imgs[i] = loc
                changed = True
                rewritten += 1

        for it in data.get('items') or []:
            loc = to_local(it.get('image'))
            if loc:
                it['image'] = loc
                changed = True
                rewritten += 1

        if changed:
            files_touched += 1
            if not dry:
                jf.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    tag = '[dry-run] ' if dry else ''
    print(f'{tag}copied {copied} images -> {DEST}')
    print(f'{tag}rewrote {rewritten} image refs across {files_touched} catalog files')


main()
