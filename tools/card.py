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
from common import DATA, DOCS, IMAGES, jload   # noqa: E402

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


def _wrap(d, text, size, max_w, max_lines, name=b"Demi Bold", floor=34):
    """Shrink until the text fits max_lines with every word whole; return (font, lines)."""
    while size > floor:
        f = font(size, name)
        lines, cur = [], ""
        for w in text.split():
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= max_w:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) <= max_lines and all(d.textlength(l, font=f) <= max_w for l in lines):
            return f, lines
        size -= 4
    return font(floor, name), [text]


def _short(text: str, n: int = 100) -> str:
    """The first sentence, or the first clause that fits in n characters."""
    import re
    m = re.match(r"(.{20,%d}?[.!?])(\s|$)" % n, text)
    if m:
        return m.group(1)
    if len(text) <= n:
        return text
    cut = max(text.rfind(c, 20, n) for c in ":;,")
    return text[:cut] if cut > 0 else text[:n].rsplit(" ", 1)[0]


def page_card(out: Path, title: str, sub: str, key: str) -> None:
    """One section's card: the plate of card.py with the page's own title and line, a photograph from data/images/."""
    im = Image.new("RGB", (W, H), NIGHT)
    ph = Image.open(IMAGES / (key + ".jpg")).convert("RGB")
    r = max((W - PW) / ph.width, H / ph.height)
    ph = ph.resize((round(ph.width * r), round(ph.height * r)), Image.LANCZOS)
    left, top = (ph.width - (W - PW)) // 2, (ph.height - H) // 2
    im.paste(ph.crop((left, top, left + W - PW, top + H)), (PW, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([PW - 6, 0, PW, H], fill=RED)
    x, wide = 52, PW - 52 - 40
    d.text((x, 62), "PIKE PLACE MARKET · SEATTLE", font=font(22, b"Medium"), fill=DIM)
    ft, tl = _wrap(d, title, 92, wide, 3)
    fs, sl = _wrap(d, _short(sub), 32, wide, 4, b"Medium", floor=26)
    y = 118
    for line in tl:
        d.text((x, y), line, font=ft, fill=INK)
        y += int(ft.size * 1.02)
    y += 22
    for line in sl:
        d.text((x, y), line, font=fs, fill=GOLD)
        y += int(fs.size * 1.3)
    meta = (jload(DATA / "images" / "index.json") or {}).get("images", {}).get(key, {})
    who = (meta.get("author") or "").strip()
    lic = (meta.get("licence") or "").strip()
    d.text((x, 566), "Photograph: " + ", ".join(v for v in (who[:40].rstrip(", "), lic) if v),
           font=font(20, b"Medium"), fill=DIM)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=86, optimize=True, progressive=True)


def page_cards(cards) -> None:
    """cards: [(slug, title, sub, key)] -> docs/images/cards/<slug>.jpg"""
    for slug, title, sub, key in cards:
        page_card(DOCS / "images" / "cards" / (slug + ".jpg"), title, sub, key)
    print("page cards  %d" % len(cards))


if __name__ == "__main__":
    main()
