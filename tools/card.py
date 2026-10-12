# -*- coding: utf-8 -*-
"""card.py — the 1200x630 link card, data/images/card.jpg (build.py copies it to docs/images/).

  python3 tools/card.py

A dark plate with the title and counts on the left, the Highsmith photograph of the
Public Market Center sign on the right.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, IMAGES, jload   # noqa: E402

W, H, PW = 1200, 630, 590
NIGHT, INK, DIM, GOLD, RED = (20, 16, 13), (247, 241, 230), (216, 206, 189), (240, 191, 76), (216, 53, 42)
TTC = "/System/Library/Fonts/Avenir Next Condensed.ttc"


def font(size: int, name: bytes = b"Demi Bold") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(TTC, size)
    try:
        f.set_variation_by_name(name)
    except Exception:                                            # noqa: BLE001
        pass
    return f


def main() -> None:
    C = jload(DATA / "analysis.json")["counts"]
    lic, roster = "{:,}".format(C["city_licences"]), "{:,}".format(C["market_roster"])
    im = Image.new("RGB", (W, H), NIGHT)
    ph = Image.open(IMAGES / "hero.jpg").convert("RGB")
    box = (700, 190, 1600, 1100)                    # clock, MARKET and the awning
    ph = ph.crop(box).resize((W - PW, H), Image.LANCZOS)
    im.paste(ph, (PW, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([PW - 6, 0, PW, H], fill=RED)
    x = 52
    d.text((x, 62), "PIKE PLACE MARKET · SEATTLE", font=font(22, b"Medium"), fill=DIM)
    d.text((x, 118), "Twelve acres,", font=font(88), fill=INK)
    d.text((x, 208), "counted", font=font(88), fill=INK)
    d.text((x, 340), lic, font=font(78), fill=GOLD)
    d.text((x + 150, 372), "with a licence", font=font(30, b"Medium"), fill=DIM)
    d.text((x, 438), roster, font=font(78), fill=GOLD)
    d.text((x + 150, 470), "on the Market's roster", font=font(30, b"Medium"), fill=DIM)
    d.text((x, 566), "Photograph: Carol M. Highsmith, public domain",
           font=font(20, b"Medium"), fill=DIM)
    out = IMAGES / "card.jpg"
    im.save(out, "JPEG", quality=88, optimize=True, progressive=True)
    print("card  %s  %d KB" % (out, out.stat().st_size // 1024))


if __name__ == "__main__":
    main()
