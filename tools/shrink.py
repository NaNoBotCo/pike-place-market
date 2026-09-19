# -*- coding: utf-8 -*-
"""shrink.py — re-encode the pictures so the page loads on a phone in a market aisle.

Commons hands back a rendition at the width asked for, at whatever quality the original
was saved with, which for a 7,000 px camera file is several megabytes. This re-encodes
every picture in data/images to 1600 px at quality 78 and every thumbnail to 560 px at
74, progressive, and reports what came off.

  python3 tools/shrink.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import IMAGES   # noqa: E402

try:
    from PIL import Image
except ImportError:                                               # noqa: BLE001
    raise SystemExit("Pillow is not installed — pip3 install Pillow")


def one(p: Path, width: int, q: int) -> tuple:
    before = p.stat().st_size
    im = Image.open(p)
    im = im.convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(p, "JPEG", quality=q, optimize=True, progressive=True)
    return before, p.stat().st_size


def main() -> None:
    b = a = 0
    n = 0
    for p in sorted(IMAGES.glob("*.jpg")):
        thumb = p.name.endswith(".thumb.jpg")
        x, y = one(p, 560 if thumb else 1600, 74 if thumb else 78)
        b += x
        a += y
        n += 1
    print("images %d files · %.1f MB in · %.1f MB out · %d%% off"
          % (n, b / 1e6, a / 1e6, round(100 * (1 - a / max(b, 1)))))


if __name__ == "__main__":
    main()
