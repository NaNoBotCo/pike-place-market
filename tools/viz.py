# -*- coding: utf-8 -*-
"""viz.py — charts drawn as SVG at build time, from data/analysis.json.

No chart library and no client-side drawing: the figure is in the HTML, it prints, it
reads without JavaScript, and it cannot disagree with the table beside it because both
come from the same file.

Every function returns a <figure class="chart"> with a caption that states what the
figure measures and, where it matters, what it does not.
"""
from __future__ import annotations

import html


def E(s) -> str:
    return html.escape(str(s), quote=True)


def _fig(svg: str, cap: str) -> str:
    return '<figure class="chart">%s<figcaption>%s</figcaption></figure>' % (svg, cap)


def bars(pairs: list, cap: str, unit: str = "", w: int = 760, rowh: int = 26,
         alt_after: int = None, label_w: int = 190) -> str:
    """A horizontal bar per row. Counts are printed at the end of the bar, so the chart
    is never the only place a number appears."""
    pairs = [(str(k), float(v)) for k, v in pairs]
    if not pairs:
        return ""
    top = max(v for _, v in pairs) or 1
    h = rowh * len(pairs) + 18
    bw = w - label_w - 64
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, E(cap[:120]))]
    for i, (k, v) in enumerate(pairs):
        y = i * rowh + 6
        cls = "bar alt" if (alt_after is not None and i >= alt_after) else "bar"
        out.append('<text x="%d" y="%d" text-anchor="end">%s</text>'
                   % (label_w - 10, y + rowh * .62, E(k[:34])))
        out.append('<rect class="%s" x="%d" y="%d" width="%.1f" height="%d" rx="2"/>'
                   % (cls, label_w, y + 3, max(1.0, bw * v / top), rowh - 9))
        out.append('<text class="v" x="%.1f" y="%d">%s%s</text>'
                   % (label_w + max(1.0, bw * v / top) + 8, y + rowh * .62,
                      E(("%g" % v)), E(unit)))
    out.append("</svg>")
    return _fig("".join(out), cap)


def columns(pairs: list, cap: str, w: int = 760, h: int = 230, mark: dict = None) -> str:
    """One column per bucket, in the order given — a year, a decade, a band."""
    pairs = [(str(k), float(v)) for k, v in pairs]
    if not pairs:
        return ""
    top = max(v for _, v in pairs) or 1
    pad, base = 34, h - 34
    cw = (w - pad * 2) / len(pairs)
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, E(cap[:120]))]
    out.append('<line class="ax" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (pad, base, w - pad, base))
    for i, (k, v) in enumerate(pairs):
        bh = (base - 26) * v / top
        x = pad + i * cw
        out.append('<rect class="bar" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2"/>'
                   % (x + cw * .16, base - bh, cw * .68, bh))
        out.append('<text class="v" x="%.1f" y="%.1f" text-anchor="middle">%g</text>'
                   % (x + cw / 2, base - bh - 6, v))
        if len(pairs) <= 30 or i % max(1, len(pairs) // 14) == 0:
            out.append('<text x="%.1f" y="%d" text-anchor="middle">%s</text>'
                       % (x + cw / 2, base + 16, E(k)))
    if mark:
        for label, idx in mark.items():
            x = pad + (idx + .5) * cw
            out.append('<line class="ax" x1="%.1f" y1="8" x2="%.1f" y2="%d" '
                       'stroke-dasharray="3 3"/>' % (x, x, base))
            out.append('<text class="t" x="%.1f" y="8" text-anchor="middle">%s</text>'
                       % (x, E(label)))
    out.append("</svg>")
    return _fig("".join(out), cap)


def paired(rows: list, cap: str, a_label: str, b_label: str, w: int = 760) -> str:
    """Two bars per row — the same measure inside the line and outside it."""
    if not rows:
        return ""
    top = max(max(a, b) for _, a, b in rows) or 1
    rowh, label_w = 42, 200
    h = rowh * len(rows) + 34
    bw = w - label_w - 70
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, E(cap[:120]))]
    out.append('<text class="t" x="%d" y="12">%s</text>' % (label_w, E(a_label)))
    out.append('<text class="t" x="%d" y="12" fill="#6a8fb5">%s</text>'
               % (label_w + 230, E(b_label)))
    for i, (k, a, b) in enumerate(rows):
        y = 24 + i * rowh
        out.append('<text x="%d" y="%d" text-anchor="end">%s</text>'
                   % (label_w - 10, y + 14, E(k)))
        for j, (v, cls) in enumerate(((a, "bar"), (b, "bar alt"))):
            wv = max(1.0, bw * v / top)
            out.append('<rect class="%s" x="%d" y="%d" width="%.1f" height="13" rx="2"/>'
                       % (cls, label_w, y + j * 16, wv))
            out.append('<text class="v" x="%.1f" y="%d">%g</text>' % (label_w + wv + 8, y + 11 + j * 16, v))
    out.append("</svg>")
    return _fig("".join(out), cap)


def dots(values: list, cap: str, w: int = 760, band: int = 5) -> str:
    """Every business as one dot, stacked into bands of years. The shape of the market's
    age, without a summary standing in for it."""
    if not values:
        return ""
    buckets = {}
    for v in values:
        buckets.setdefault(int(v // band) * band, []).append(v)
    hi = max(buckets) + band
    cols = int(hi / band)
    tall = max(len(v) for v in buckets.values())
    r, gap = 4.2, 2.2
    cw = (w - 60) / cols
    h = tall * (r * 2 + gap) + 62
    out = ['<svg viewBox="0 0 %d %.0f" role="img" aria-label="%s">' % (w, h, E(cap[:120]))]
    for c in range(cols):
        lo = c * band
        col = sorted(buckets.get(lo, []))
        x = 40 + c * cw + cw / 2
        for k in range(len(col)):
            y = h - 30 - k * (r * 2 + gap) - r
            shade = "#d8352a" if lo >= 40 else ("#e07a2c" if lo >= 20 else "#efc75c")
            out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" opacity=".92"/>'
                       % (x, y, r, shade))
        if c % 2 == 0:
            out.append('<text x="%.1f" y="%.0f" text-anchor="middle">%d</text>'
                       % (x, h - 24, lo))
    out.append('<text class="t" x="%.0f" y="%.0f" text-anchor="middle">'
               'years holding the same licence</text>' % (w / 2, h - 4))
    out.append("</svg>")
    return _fig("".join(out), cap)


def fence_plan(fence_geom: dict, buildings: list, cap: str, w: int = 760) -> str:
    """The district drawn from its own coordinates — the boundary, and the buildings
    standing inside it. Same polygon the map uses, and the same one every count is
    decided by."""
    g = fence_geom
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
    xs = [c[0] for p in polys for r in p for c in r]
    ys = [c[1] for p in polys for r in p for c in r]
    for b in buildings:
        xs += [c[0] for c in b["ring"]]
        ys += [c[1] for c in b["ring"]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    import math
    k = math.cos(math.radians((y0 + y1) / 2))
    pad = 14
    sw = (x1 - x0) * k
    sh = (y1 - y0)
    sc = (w - pad * 2) / sw
    h = sh * sc + pad * 2

    def px(c):
        return (pad + (c[0] - x0) * k * sc, pad + (y1 - c[1]) * sc)

    def path(ring):
        return "M" + "L".join("%.1f %.1f" % px(c) for c in ring) + "Z"

    out = ['<svg viewBox="0 0 %d %.0f" role="img" aria-label="%s">' % (w, h, E(cap[:120]))]
    for b in buildings:
        out.append('<path d="%s" fill="#3b2d25" stroke="#5c4838" stroke-width=".7"/>'
                   % path(b["ring"]))
    for p in polys:
        for i, ring in enumerate(p):
            out.append('<path d="%s" fill="none" stroke="#d8352a" stroke-width="2.4"/>'
                       % path(ring))
    for b in buildings:
        if b["area_m2"] < 420:
            continue
        x, y = px(b["pt"])
        out.append('<text class="t" x="%.1f" y="%.1f" text-anchor="middle" '
                   'font-size="10" stroke="#1a1410" stroke-width="2.6" '
                   'paint-order="stroke">%s</text>' % (x, y, E(b["name"])))
    out.append("</svg>")
    return _fig("".join(out), cap)
