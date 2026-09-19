# -*- coding: utf-8 -*-
"""shell.py — the shell every page is poured into: head, chrome, footer, and the CSS.

Three things here are load-tested house style rather than taste:

  shot()   a picture that leads somewhere is built in four layers — background, scrim,
           spacer, text — and the whole box is the link. Never a bare <img> in an <a>.
  plate()  no word sits on a photograph. Type goes on one surface, dark enough that
           legibility does not depend on which frame is behind it.
  credit() a borrowed photograph carries its author and licence wherever it appears.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, jload   # noqa: E402

SITE = "https://nanobotco.github.io/pike-place-market/"
NAME = "Pike Place Market"
TAG = "the twelve acres, counted"

IMG = jload(DATA / "images" / "index.json") or {"images": {}}
IMAGES = IMG.get("images", {})


def E(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def rel(depth: int) -> str:
    return "../" * depth if depth else ""


# ---------------------------------------------------------------- pictures

def img_src(key: str, depth: int, thumb=False) -> str:
    im = IMAGES.get(key)
    if not im:
        return ""
    return "%simages/%s" % (rel(depth), im["thumb"] if thumb else im["file"])


def credit(key: str, short=True) -> str:
    im = IMAGES.get(key)
    if not im:
        return ""
    who = im.get("author") or "no author named on the file"
    lic = im.get("licence") or ""
    url = im.get("licence_url")
    lic_html = '<a href="%s" rel="license">%s</a>' % (E(url), E(lic)) if url else E(lic)
    date = (" · %s" % E(im["date"][:4])) if im.get("date") and im["date"][:4].isdigit() else ""
    return ('<a href="%s">%s</a> · %s · %s%s'
            % (E(im["page"]), E(who[:60]), lic_html, "Wikimedia Commons", date))


def shot(href: str, key: str, label: str, depth: int, kicker: str = "") -> str:
    """The four layers. The picture is the link; the name lies on the picture; the
    credit sits outside the anchor, because it carries a link of its own."""
    src = img_src(key, depth, thumb=True)
    k = '<span class="kk">%s</span>' % E(kicker) if kicker else ""
    return ('<figure class="thumb"><h3><a class="shot" href="%s">'
            '<span class="bg" style="background-image:url(%s)"></span>'
            '<span class="scrim"></span><span class="sp"></span>'
            '<span class="tx">%s%s</span></a></h3>'
            '<span class="cred">%s</span></figure>'
            % (E(href), E(src), k, E(label), credit(key)))


def bare_tile(href: str, label: str, kicker: str = "") -> str:
    k = '<span class="kk">%s</span>' % E(kicker) if kicker else ""
    return ('<figure class="thumb"><h3><a class="shot bare" href="%s">'
            '<span class="sp"></span><span class="tx">%s%s</span></a></h3></figure>'
            % (E(href), k, E(label)))


# ---------------------------------------------------------------- chrome

NAV = [("", "Front"), ("map/", "Map"), ("directory/", "Directory"),
       ("trades/", "Trades"), ("age/", "Age"), ("fence/", "The line"),
       ("daniel-fleming/", "Daniel Fleming"), ("sources/", "Sources")]


def head(title: str, desc: str, depth: int, canon: str, extra: str = "",
         cls: str = "") -> str:
    r = rel(depth)
    nav = "".join('<a href="%s%s"%s>%s</a>'
                  % (r, E(h), ' class="on"' if canon == h else "", E(t))
                  for h, t in NAV)
    return """<!doctype html>
<html lang="en" class="%s">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>%s</title>
<meta name="description" content="%s">
<link rel="canonical" href="%s%s">
<meta property="og:title" content="%s">
<meta property="og:description" content="%s">
<meta property="og:type" content="website">
<meta name="theme-color" content="#14100d">
<link rel="stylesheet" href="%ssite.css">
%s
<a class="skip" href="#main">Skip to the page</a>
<header class="top"><nav class="bar">%s</nav></header>
""" % (E(cls), E(title), E(desc), SITE, E(canon), E(title), E(desc), r, extra, nav)


def foot(depth: int, keys: list = None) -> str:
    r = rel(depth)
    creds = ""
    if keys:
        rows = "".join("<li>%s</li>" % credit(k) for k in keys if k in IMAGES)
        creds = ("<details class=\"pics\"><summary>Pictures on this page</summary>"
                 "<ul>%s</ul></details>" % rows)
    return """
<footer class="door">
 <div class="in"><div class="plate">
  <p class="sig"><b>%s</b> · %s</p>
  <nav class="fnav">%s</nav>
  <p class="src">Built from the City of Seattle's open data, OpenStreetMap under ODbL 1.0,
   the Market's own vendor roster, and freely licensed photographs from Wikimedia Commons.
   <a href="%ssources/">Every source, with the hour it was read</a>.</p>
  %s
  <p class="lic">Code MIT. Text and figures CC BY 4.0. The data keeps the licence it
   arrived with. <a href="https://github.com/NaNoBotCo/pike-place-market">Repository</a>.</p>
 </div></div>
</footer>
""" % (E(NAME), E(TAG),
       "".join('<a href="%s%s">%s</a>' % (r, E(h), E(t)) for h, t in NAV),
       r, creds)


def plate(inner: str, cls: str = "") -> str:
    return '<div class="plate %s">%s</div>' % (E(cls), inner)


def backdrop(scenes: list, depth: int) -> str:
    """One fixed layer holding one frame per scene. It is never told about scroll
    position, so the photograph does not move; which frame is showing is all that
    changes, and it changes by fading."""
    out = ['<div class="backdrop" aria-hidden="true">']
    for i, (scene, key) in enumerate(scenes):
        src = img_src(key, depth)
        if not src:
            continue
        out.append('<picture class="bg%s" data-scene="%s"><img src="%s" alt="" %s '
                   'decoding="async"></picture>'
                   % (" on" if i == 0 else "", E(scene), E(src),
                      'fetchpriority="high"' if i == 0 else 'loading="lazy"'))
    out.append('<div class="scrim"></div></div>')
    return "".join(out)


def counters(rows: list) -> str:
    """A number, then what it counts, then where it goes."""
    li = []
    for big, title, note, href in rows:
        li.append('<li><a href="%s"><span class="big">%s</span>'
                  '<span class="lbl"><span class="t">%s</span><small>%s</small></span></a></li>'
                  % (E(href), E(big), E(title), note))
    return '<ul class="counters">%s</ul>' % "".join(li)


def table(headers: list, rows: list, cls: str = "") -> str:
    th = "".join("<th>%s</th>" % E(h) for h in headers)
    tr = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in r) for r in rows)
    return ('<div class="scroll"><table class="%s"><thead><tr>%s</tr></thead>'
            '<tbody>%s</tbody></table></div>' % (E(cls), th, tr))


def jsonld(obj: dict) -> str:
    return '<script type="application/ld+json">%s</script>' % json.dumps(obj, ensure_ascii=False)


# ---------------------------------------------------------------- the stylesheet

CSS = r"""
:root{
 --ink:#f7f1e6;--dim:#d8cebd;--red:#d8352a;--gold:#f0bf4c;--night:#14100d;
 --plate:rgba(17,13,10,.86);--hair:rgba(255,255,255,.15);
 --paper:rgba(24,19,15,.94);
 /* The type stack is system faces, so the page asks for no font files. */
 --dis:'Avenir Next Condensed','Helvetica Neue Condensed','Arial Narrow',
  'Helvetica Neue',system-ui,sans-serif;
 --tx:-apple-system,BlinkMacSystemFont,'Segoe UI','Helvetica Neue',system-ui,sans-serif;
 --mono:ui-monospace,'SF Mono',Menlo,monospace}
*{box-sizing:border-box}
html{scroll-behavior:smooth;background:var(--night);-webkit-text-size-adjust:100%}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
/* the ground colour lives on <html>; an opaque body would paint over the fixed
   backdrop, which sits in the root stacking context at a negative z-index */
body{margin:0;background:transparent;color:var(--ink);font-family:var(--tx);
 line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
a:hover{text-decoration:underline;text-underline-offset:.22em}
:focus-visible{outline:3px solid var(--gold);outline-offset:3px;border-radius:5px}
.skip{position:absolute;left:-999px}.skip:focus{left:10px;top:10px;z-index:99;background:#fff;color:#000;padding:10px 16px}
img{max-width:100%}

/* ---- the bar ---- */
.top{position:sticky;top:0;z-index:6;background:rgba(14,11,9,.88);
 backdrop-filter:blur(14px);border-bottom:1px solid var(--hair)}
.bar{max-width:1240px;margin:0 auto;display:flex;gap:2px;overflow-x:auto;
 padding:0 clamp(8px,2vw,20px);scrollbar-width:none}
.bar::-webkit-scrollbar{display:none}
.bar a{font-family:var(--dis);font-size:14px;letter-spacing:.12em;text-transform:uppercase;
 padding:16px 14px;white-space:nowrap;color:var(--dim);border-bottom:3px solid transparent}
.bar a:hover{color:var(--ink);text-decoration:none}
.bar a.on{color:var(--ink);border-bottom-color:var(--red)}

/* ---- scenes, and words that never sit on a photograph ---- */
.backdrop{position:fixed;inset:0;z-index:-2;overflow:hidden;pointer-events:none}
.backdrop .bg{position:absolute;inset:0;margin:0;opacity:0;transition:opacity .8s ease}
.backdrop .bg.on{opacity:1}
.backdrop .bg img{width:100%;height:100%;object-fit:cover;display:block;
 filter:brightness(.86) saturate(1.05)}
.backdrop .scrim{position:absolute;inset:0;background:
 radial-gradient(130% 100% at 50% 45%,rgba(20,16,13,0) 36%,rgba(20,16,13,.5) 100%),
 linear-gradient(180deg,rgba(20,16,13,.4) 0,rgba(20,16,13,0) 24%,rgba(20,16,13,0) 70%,rgba(20,16,13,.78) 100%)}
.s{position:relative;min-height:100svh;display:grid;align-items:center}
.s.flow{min-height:0}
.in{width:min(1240px,100%);margin:0 auto;
 padding:clamp(72px,12vh,140px) clamp(16px,5vw,60px) clamp(64px,11vh,120px)}
.plate{max-width:880px;margin:0 auto;background:var(--plate);
 backdrop-filter:blur(15px) saturate(1.15);border:1px solid var(--hair);
 border-radius:24px;padding:clamp(22px,3.2vw,44px);box-shadow:0 30px 80px rgba(0,0,0,.5)}
.plate.wide{max-width:1240px}
h1,h2,h3{font-family:var(--dis);font-weight:600;line-height:1.05}
h1{font-size:clamp(34px,6.4vw,68px);margin:0 0 .4em;letter-spacing:-.01em}
h2.kick{font-size:clamp(12px,1.3vw,15px);letter-spacing:.26em;text-transform:uppercase;
 color:var(--dim);margin:0 0 clamp(16px,2.4vw,26px);font-weight:600}
h2{font-size:clamp(24px,3.4vw,40px);margin:1.6em 0 .5em}
h3{font-size:clamp(18px,2.2vw,24px);margin:1.4em 0 .4em}
p{margin:0 0 1em;max-width:68ch}
.lede{font-size:clamp(18px,2.1vw,23px);color:var(--ink)}
blockquote{margin:0 0 .5em;padding-left:clamp(14px,1.8vw,22px);
 border-left:3px solid var(--red);color:var(--ink)}
blockquote+.small{margin-top:-.2em}
small,.small{font-size:clamp(13px,1.2vw,15px);color:var(--dim)}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}

/* ---- the hero ---- */
.plate.hero{display:grid;gap:clamp(16px,2.4vw,26px);justify-items:center;text-align:center;
 max-width:min(860px,100%)}
.plate.hero h1{margin:0}
.wordmark{font-size:clamp(11px,1vw,14px);letter-spacing:.44em;color:var(--dim);
 text-transform:uppercase;font-family:var(--dis)}
.nowline{display:flex;flex-wrap:wrap;justify-content:center;gap:10px clamp(14px,2.4vw,26px);
 font-family:var(--mono);font-size:clamp(14px,1.5vw,18px);margin:0}
.nowline b{font-size:1.5em;font-weight:700}
.nowline .lamp{display:inline-flex;align-items:center;gap:8px}
.nowline i{width:11px;height:11px;border-radius:50%;background:var(--dim);display:block}
.nowline i.open{background:#4ec46a;box-shadow:0 0 12px #4ec46a}
.nowline i.shut{background:var(--red)}
.btn{display:inline-flex;align-items:center;gap:9px;min-height:48px;padding:12px 24px;
 border:1px solid var(--hair);border-radius:999px;background:rgba(255,255,255,.08);
 font-family:var(--dis);letter-spacing:.1em;text-transform:uppercase;font-size:14px}
.btn:hover{background:var(--red);border-color:var(--red);text-decoration:none}
.btn.solid{background:var(--red);border-color:var(--red)}
.down{position:absolute;left:50%;bottom:max(16px,env(safe-area-inset-bottom));
 transform:translateX(-50%);width:46px;height:46px;display:grid;place-items:center;
 border-radius:50%;background:rgba(17,13,10,.8);border:1px solid var(--hair);
 font-size:24px;animation:bob 2.6s ease-in-out infinite}
@keyframes bob{50%{transform:translate(-50%,7px)}}
@media (prefers-reduced-motion:reduce){.down{animation:none}}

/* ---- rows ---- */
.counters{list-style:none;margin:0;padding:0;display:grid}
.counters li{border-top:1px solid var(--hair)}
.counters li:first-child{border-top:0}
.counters li a{display:grid;grid-template-columns:auto minmax(0,1fr);gap:clamp(14px,2vw,24px);
 align-items:center;padding:clamp(14px,1.9vw,20px) 4px;min-height:62px}
.counters li a:hover{text-decoration:none}
.counters li a:hover .t{text-decoration:underline;text-underline-offset:.22em}
.counters .big{font-family:var(--mono);font-size:clamp(26px,3.3vw,40px);font-weight:700;
 line-height:1;min-width:3ch;text-align:center;color:var(--gold)}
.counters .lbl{display:grid;gap:4px;min-width:0}
.counters .t{font-size:clamp(16px,1.7vw,19px);font-weight:600}
.counters small{color:var(--dim)}

/* ---- the hours ---- */
.hours{list-style:none;margin:0;padding:0;display:grid}
.hours li{border-top:1px solid var(--hair);display:grid;
 grid-template-columns:auto minmax(0,1fr) auto;gap:14px;align-items:center;
 padding:clamp(11px,1.5vw,15px) 2px;min-height:52px}
.hours li:first-child{border-top:0}
.hours i{width:12px;height:12px;border-radius:50%;background:var(--dim);display:block}
.hours li.on i{background:#4ec46a;box-shadow:0 0 12px rgba(78,196,106,.8)}
.hours li.off i{background:#6a5a4c}
.hours li.off{opacity:.62}
.hours .w{font-size:clamp(15px,1.6vw,18px);font-weight:600}
.hours .t{color:var(--dim);font-size:clamp(13px,1.3vw,15px);text-align:right}

/* ---- the four-layer picture link ---- */
.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:clamp(10px,1.5vw,18px);
 list-style:none;margin:0;padding:0}
@media (min-width:720px){.tiles{grid-template-columns:repeat(3,1fr)}
 .tiles.four{grid-template-columns:repeat(4,1fr)}}
@media (min-width:1100px){.tiles.four{grid-template-columns:repeat(4,1fr)}}
.thumb{margin:0;position:relative}
.thumb h3{margin:0;font-size:inherit;font-weight:inherit;font-family:inherit;line-height:inherit}
.shot{position:relative;display:block;border-radius:18px;overflow:hidden;isolation:isolate;
 background:#231b16;transition:transform .35s cubic-bezier(.2,.9,.3,1.2)}
.shot .bg{position:absolute;inset:0;background-size:cover;background-position:center;
 z-index:-2;transition:transform .6s ease}
.shot .scrim{position:absolute;inset:0;z-index:-1;background:
 linear-gradient(180deg,rgba(10,8,6,.1) 0,rgba(10,8,6,.22) 46%,rgba(10,8,6,.88) 100%)}
.shot .sp{display:block;padding-top:72%}
.shot.bare{border:1px solid var(--hair);background:
 linear-gradient(155deg,#2c231c,#191310)}
.shot .tx{position:absolute;left:0;right:0;bottom:0;padding:clamp(12px,1.5vw,18px);
 font-family:var(--dis);font-size:clamp(15px,1.7vw,20px);color:#fff;
 text-shadow:0 2px 16px rgba(0,0,0,.7);display:grid;gap:4px}
.shot .kk{font-size:.62em;letter-spacing:.2em;text-transform:uppercase;color:var(--gold)}
@media (prefers-reduced-motion:no-preference){
 .shot:hover{transform:translateY(-4px)}
 .shot:hover .bg{transform:scale(1.06)}}
.shot:hover{text-decoration:none}
.cred{display:block;font-size:11px;color:var(--dim);padding:6px 2px 0;line-height:1.35}
.cred a{color:var(--dim);text-decoration:underline;text-underline-offset:.18em}

/* ---- long text pages ---- */
.paper{background:var(--paper);border:1px solid var(--hair);border-radius:24px;
 padding:clamp(22px,3.4vw,52px);max-width:1240px;margin:0 auto;
 /* a gradient fill anchored to the window, so the box scrolls through its own colour */
 background-image:linear-gradient(165deg,rgba(216,53,42,.10),rgba(20,16,13,0) 60%);
 background-attachment:fixed}
@media (pointer:coarse),(prefers-reduced-motion:reduce){.paper{background-attachment:scroll}}
.paper h2:first-child{margin-top:0}
.two{display:grid;gap:clamp(18px,3vw,40px)}
@media (min-width:900px){.two{grid-template-columns:1.4fr 1fr;align-items:start}}

/* ---- tables ---- */
.scroll{overflow-x:auto;margin:1.4em 0;border:1px solid var(--hair);border-radius:14px}
table{border-collapse:collapse;width:100%;font-size:clamp(13px,1.35vw,15px)}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--hair);vertical-align:top}
th{font-family:var(--dis);font-size:12px;letter-spacing:.14em;text-transform:uppercase;
 color:var(--dim);position:sticky;top:0;background:#1a1410}
tbody tr:hover{background:rgba(255,255,255,.04)}
td.n,th.n{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}

/* ---- directory ---- */
.yahoo{list-style:none;margin:0 0 2em;padding:0;columns:1;column-gap:clamp(20px,3vw,44px)}
@media (min-width:560px){.yahoo{columns:2}}
@media (min-width:900px){.yahoo{columns:3}}
.yahoo li{break-inside:avoid;padding:5px 0;font-size:clamp(15px,1.5vw,17px)}
.yahoo b{font-weight:600}
.yahoo .c{font-family:var(--mono);color:var(--dim);font-size:.86em}
.rows{list-style:none;margin:0;padding:0}
.rows li{border-top:1px solid var(--hair);padding:12px 2px;display:grid;
 grid-template-columns:minmax(0,1fr) auto;gap:8px 16px;align-items:baseline}
.rows li:first-child{border-top:0}
.rows .nm{font-size:clamp(16px,1.6vw,18px);font-weight:600}
.rows .meta{color:var(--dim);font-size:13px;display:block}
.rows .yr{font-family:var(--mono);color:var(--gold);white-space:nowrap}
.pill{display:inline-block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
 border:1px solid var(--hair);border-radius:999px;padding:2px 9px;color:var(--dim);
 margin-right:5px;font-family:var(--dis)}
.pill.red{border-color:var(--red);color:#ffb9b4}
.pill.gold{border-color:var(--gold);color:var(--gold)}

/* ---- the map ---- */
#map{height:min(78svh,820px);border-radius:20px;overflow:hidden;border:1px solid var(--hair);
 background:#0f0c0a}
.maplibregl-popup-content{background:#1b1512;color:var(--ink);border-radius:14px;
 padding:14px 16px;font-family:var(--tx);border:1px solid var(--hair);max-width:300px}
.maplibregl-popup-content h4{margin:0 0 6px;font-family:var(--dis);font-size:16px}
.maplibregl-popup-tip{border-top-color:#1b1512!important;border-bottom-color:#1b1512!important}
.maplibregl-popup-close-button{color:var(--dim);font-size:20px}
.ctl{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
.ctl button,.ctl label{font-family:var(--dis);font-size:13px;letter-spacing:.1em;
 text-transform:uppercase;border:1px solid var(--hair);background:rgba(255,255,255,.06);
 color:var(--ink);border-radius:999px;padding:9px 16px;min-height:42px;cursor:pointer;
 display:inline-flex;align-items:center;gap:8px}
.ctl button[aria-pressed=true]{background:var(--red);border-color:var(--red)}
.ctl input[type=search]{font:inherit;background:rgba(255,255,255,.06);color:var(--ink);
 border:1px solid var(--hair);border-radius:999px;padding:11px 18px;min-height:42px;min-width:220px}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0 0;font-size:13px;color:var(--dim)}
.legend span{display:inline-flex;align-items:center;gap:7px}
.legend i{width:13px;height:13px;border-radius:50%;display:block}
.bmark{font-family:var(--dis);font-size:12px;letter-spacing:.08em;text-transform:uppercase;
 color:#e8dcc8;text-shadow:0 1px 8px #000,0 0 3px #000;pointer-events:none;white-space:nowrap}
.where{font-family:var(--mono);font-size:14px;color:var(--gold);margin:12px 0 0;min-height:1.5em}

/* ---- charts ---- */
.chart{margin:1.6em 0;background:rgba(255,255,255,.035);border:1px solid var(--hair);
 border-radius:18px;padding:clamp(14px,2vw,24px)}
.chart svg{width:100%;height:auto;display:block;overflow:visible}
.chart figcaption{font-size:13px;color:var(--dim);margin-top:12px;max-width:74ch}
.chart .bar{fill:var(--red)}
.chart .bar.alt{fill:#6a8fb5}
.chart .ax{stroke:rgba(255,255,255,.2);stroke-width:1}
.chart text{fill:var(--dim);font-family:var(--mono);font-size:11px}
.chart text.v{fill:var(--ink)}
.chart text.t{fill:var(--ink);font-family:var(--dis);font-size:13px}

/* ---- footer ---- */
.door{background:var(--night);border-top:1px solid var(--hair);margin-top:clamp(40px,8vh,90px)}
.door .in{padding-top:clamp(40px,7vh,80px);padding-bottom:clamp(40px,7vh,80px)}
.door .plate{max-width:1240px}
.sig{font-family:var(--dis);font-size:19px;letter-spacing:.04em}
.fnav{display:flex;flex-wrap:wrap;gap:6px 20px;margin:0 0 18px;font-size:15px}
.src,.lic{font-size:14px;color:var(--dim);max-width:78ch}
.pics{margin:14px 0}
.pics summary{cursor:pointer;font-size:14px;color:var(--dim);min-height:40px;
 display:inline-flex;align-items:center}
.pics ul{margin:10px 0 0;padding-left:20px;font-size:12px;color:var(--dim);
 columns:2;column-gap:30px}
.pics li{break-inside:avoid;margin-bottom:5px}
@media print{.top,.backdrop,.down{display:none}body{color:#000}}
"""

MAP_JS = r"""
/* Every layer is a GeoJSON file served beside this page. The fence is drawn as a hole
   cut in a dark mask, so what is outside the district looks outside. */
(function(){
var D='DATAPREFIX';
var FENCE=[[-122.3452,47.6062],[-122.3392,47.6118]];
var map=new maplibregl.Map({
 container:'map',style:{version:8,sources:{},layers:[
  {id:'bg',type:'background',paint:{'background-color':'#0f0c0a'}}]},
 center:[CENTERLON,CENTERLAT],zoom:16.2,minZoom:14.6,maxZoom:20,pitch:0,bearing:-16,
 maxBounds:[[-122.3520,47.6020],[-122.3330,47.6160]],
 attributionControl:false});
map.addControl(new maplibregl.NavigationControl({showCompass:true}),'top-right');
map.addControl(new maplibregl.AttributionControl({compact:true,
 customAttribution:'Geometry © OpenStreetMap contributors (ODbL) · boundary and furniture: City of Seattle open data'}));
map.addControl(new maplibregl.ScaleControl({maxWidth:120,unit:'metric'}));
/* A device without WebGL gets the drawn plan that is already on the page, rather than
   a black rectangle. */
map.on('error',function(e){
 var m=String((e&&e.error&&e.error.message)||'');
 if(/webgl|context/i.test(m)){
  var f=document.getElementById('plan');
  if(f){f.hidden=false;document.getElementById('map').hidden=true}
 }
});

function j(n){return fetch(D+n).then(function(r){return r.json()})}

map.on('load',function(){
 Promise.all(['ground.geojson','buildings.geojson','fence.geojson','vendors.geojson',
  'near.geojson','osm.geojson','extras.geojson'].map(j)).then(function(d){
  var ground=d[0],blds=d[1],fence=d[2],vend=d[3],near=d[4],osm=d[5],extra=d[6];
  map.addSource('ground',{type:'geojson',data:ground});
  map.addSource('blds',{type:'geojson',data:blds});
  map.addSource('fence',{type:'geojson',data:fence});
  map.addSource('mask',{type:'geojson',data:maskOf(fence)});
  map.addSource('vend',{type:'geojson',data:vend});
  map.addSource('near',{type:'geojson',data:near});
  map.addSource('osm',{type:'geojson',data:osm});
  map.addSource('extra',{type:'geojson',data:extra});

  map.addLayer({id:'water',type:'fill',source:'ground',filter:['==',['get','kind'],'water'],
   paint:{'fill-color':'#16303f'}});
  map.addLayer({id:'green',type:'fill',source:'ground',filter:['==',['get','kind'],'green'],
   paint:{'fill-color':'#1d2a1c'}});
  map.addLayer({id:'roads',type:'line',source:'ground',filter:['==',['get','kind'],'road'],
   paint:{'line-color':'#2b241e','line-width':['interpolate',['linear'],['zoom'],14,2,19,16]}});
  map.addLayer({id:'pier',type:'fill',source:'ground',filter:['==',['get','kind'],'pier'],
   paint:{'fill-color':'#241c17'}});
  map.addLayer({id:'blds-all',type:'fill',source:'blds',
   paint:{'fill-color':['case',['get','inside'],'#3a2c24','#221b17'],
          'fill-outline-color':'#4a3a30'}});
  map.addLayer({id:'blds-3d',type:'fill-extrusion',source:'blds',
   filter:['all',['get','inside'],['has','levels']],layout:{visibility:'none'},
   paint:{'fill-extrusion-color':'#5a4436','fill-extrusion-opacity':.85,
    'fill-extrusion-height':['*',['get','levels'],3.6]}});
  map.addLayer({id:'foot',type:'line',source:'ground',filter:['==',['get','kind'],'foot'],
   paint:{'line-color':'#57463a','line-width':['interpolate',['linear'],['zoom'],15,.6,19,3.4]}});
  map.addLayer({id:'steps',type:'line',source:'ground',filter:['==',['get','kind'],'steps'],
   paint:{'line-color':'#8a6a4e','line-width':2,'line-dasharray':[1.6,1.2]}});
  map.addLayer({id:'mask',type:'fill',source:'mask',
   paint:{'fill-color':'#0d0a08','fill-opacity':.62}});
  map.addLayer({id:'fence-line',type:'line',source:'fence',
   paint:{'line-color':'#d8352a','line-width':3,'line-opacity':.95}});
  map.addLayer({id:'near-dot',type:'circle',source:'near',layout:{visibility:'none'},
   paint:{'circle-radius':4,'circle-color':'#6a8fb5','circle-stroke-width':1,
    'circle-stroke-color':'#0f0c0a'}});
  map.addLayer({id:'extra-dot',type:'circle',source:'extra',layout:{visibility:'none'},
   paint:{'circle-radius':3.5,'circle-color':'#7a9c6a','circle-opacity':.9}});
  map.addLayer({id:'osm-dot',type:'circle',source:'osm',layout:{visibility:'none'},
   paint:{'circle-radius':4,'circle-color':'#f0bf4c','circle-opacity':.85}});
  map.addLayer({id:'vend-dot',type:'circle',source:'vend',
   paint:{'circle-radius':['interpolate',['linear'],['zoom'],15,3.4,19,9],
    'circle-color':['interpolate',['linear'],['get','years'],0,'#f3e7c6',10,'#efc75c',
      25,'#e07a2c',45,'#d8352a'],
    'circle-stroke-width':1.2,'circle-stroke-color':'#120e0b'}});
  /* MapLibre needs a glyph server to draw text in a symbol layer, and this map has no
     server of any kind. Building names are HTML markers instead; everything else opens
     in a popup on a tap. */
  var marks=blds.features.filter(function(f){return f.properties.inside&&f.properties.name})
   .map(function(f){
    var el=document.createElement('span');el.className='bmark';el.textContent=f.properties.name;
    new maplibregl.Marker({element:el}).setLngLat(centreOf(f.geometry)).addTo(map);
    return {el:el,area:f.properties.area_m2||0};
   });
  /* Twenty-two names in twelve acres collide at low zoom. The small footprints drop
     out first and come back as the reader goes in. */
  function thin(){
   var z=map.getZoom(),floor=z>=17.4?0:(z>=16.6?600:1600);
   marks.forEach(function(m){m.el.style.display=m.area>=floor?'':'none'});
  }
  map.on('zoom',thin);thin();

  /* the district fills the frame, whatever the window is */
  var bb=fence.features[0].properties.bbox;
  map.fitBounds([[bb[0],bb[1]],[bb[2],bb[3]]],{padding:46,duration:0});
  map.setMaxBounds([[bb[0]-.004,bb[1]-.004],[bb[2]+.004,bb[3]+.004]]);
  wire(vend,near,osm);
 });
});

function centreOf(g){
 var r=(g.type==='Polygon'?g.coordinates:g.coordinates[0])[0],x=0,y=0;
 for(var i=0;i<r.length-1;i++){x+=r[i][0];y+=r[i][1]}
 return [x/(r.length-1),y/(r.length-1)];
}

/* the world, with the district cut out of it */
function maskOf(fence){
 var outer=[[-122.40,47.58],[-122.30,47.58],[-122.30,47.64],[-122.40,47.64],[-122.40,47.58]];
 var g=fence.features[0].geometry;
 var holes=(g.type==='Polygon'?[g.coordinates]:g.coordinates).map(function(p){return p[0]});
 return {type:'FeatureCollection',features:[{type:'Feature',properties:{},
  geometry:{type:'Polygon',coordinates:[outer].concat(holes)}}]};
}

function pop(e,html){
 new maplibregl.Popup({closeButton:true,maxWidth:'320px'})
  .setLngLat(e.features[0].geometry.coordinates.slice()).setHTML(html).addTo(map);
}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
 return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}

function wire(vend,near,osm){
 map.on('click','vend-dot',function(e){
  var p=e.features[0].properties;
  pop(e,'<h4>'+esc(p.name)+'</h4><p>'+esc(p.trade||'')+'</p><p class="small">'+
   esc(p.address)+(p.unit?' &middot; unit '+esc(p.unit):'')+'<br>licence since '+
   esc(String(p.start).slice(0,4))+' &middot; '+esc(p.years)+' years'+
   (p.building?'<br>'+esc(p.building.replace(/-/g,' ')):'')+'</p>');
 });
 map.on('click','near-dot',function(e){
  var p=e.features[0].properties;
  pop(e,'<h4>'+esc(p.name)+'</h4><p>'+esc(p.trade||'')+'</p><p class="small">'+
   esc(p.address)+'<br>'+esc(p.edge_m)+' m outside the line</p>');
 });
 map.on('click','osm-dot',function(e){
  var p=e.features[0].properties;
  pop(e,'<h4>'+esc(p.name)+'</h4><p class="small">'+esc(p.kind||'')+
   (p.level?' &middot; level '+esc(p.level):'')+'<br>from OpenStreetMap, '+esc(p.osm)+'</p>');
 });
 map.on('click','extra-dot',function(e){
  var p=e.features[0].properties;
  pop(e,'<h4>'+esc(p.name)+'</h4><p class="small">'+esc(p.kind)+'</p>');
 });
 ['vend-dot','near-dot','osm-dot','extra-dot'].forEach(function(l){
  map.on('mouseenter',l,function(){map.getCanvas().style.cursor='pointer'});
  map.on('mouseleave',l,function(){map.getCanvas().style.cursor=''});
 });

 document.querySelectorAll('[data-layer]').forEach(function(b){
  b.addEventListener('click',function(){
   var on=b.getAttribute('aria-pressed')==='true';
   b.setAttribute('aria-pressed',on?'false':'true');
   b.dataset.layer.split(',').forEach(function(id){
    map.setLayoutProperty(id,'visibility',on?'none':'visible')});
  });
 });

 var sel=document.getElementById('sector');
 if(sel)sel.addEventListener('change',function(){
  map.setFilter('vend-dot',sel.value?['==',['get','sector'],sel.value]:null);
 });
 var age=document.getElementById('age');
 if(age)age.addEventListener('input',function(){
  var v=+age.value;
  document.getElementById('agev').textContent=v?v+' years or more':'any age';
  map.setFilter('vend-dot',v?['>=',['get','years'],v]:null);
 });
 var q=document.getElementById('q');
 if(q)q.addEventListener('input',function(){
  var t=q.value.trim().toLowerCase();
  if(!t){map.setFilter('vend-dot',null);map.setFilter('osm-dot',null);return}
  map.setFilter('vend-dot',['in',t,['downcase',['concat',['get','name'],' ',
   ['coalesce',['get','trade'],'']]]]);
 });

 var btn=document.getElementById('locate');
 if(btn)btn.addEventListener('click',function(){
  var out=document.getElementById('whereami');
  if(!navigator.geolocation){out.textContent='This browser offers no position.';return}
  out.textContent='asking the device…';
  navigator.geolocation.getCurrentPosition(function(p){
   var lon=p.coords.longitude,lat=p.coords.latitude;
   fetch(D+'fence.geojson').then(function(r){return r.json()}).then(function(f){
    var g=f.features[0].geometry,inside=ptIn([lon,lat],g);
    var d=Math.round(distTo([lon,lat],g));
    out.textContent=inside?('inside the district — '+d+' m from the line')
      :(d<3000?(d+' m outside the district'):'well outside the district');
    new maplibregl.Marker({color:inside?'#4ec46a':'#d8352a'}).setLngLat([lon,lat]).addTo(map);
    map.easeTo({center:inside?[lon,lat]:[CENTERLON,CENTERLAT],zoom:inside?18:16.4});
   });
  },function(){out.textContent='the device declined'},{enableHighAccuracy:true,timeout:9000});
 });
}

function ptIn(pt,g){
 var polys=g.type==='Polygon'?[g.coordinates]:g.coordinates;
 for(var i=0;i<polys.length;i++){if(ring(pt,polys[i][0]))return true}
 return false;
}
function ring(pt,r){
 var x=pt[0],y=pt[1],inside=false;
 for(var i=0,j=r.length-1;i<r.length;j=i++){
  var xi=r[i][0],yi=r[i][1],xj=r[j][0],yj=r[j][1];
  if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/((yj-yi)||1e-18)+xi)inside=!inside;
 }
 return inside;
}
function distTo(pt,g){
 var polys=g.type==='Polygon'?[g.coordinates]:g.coordinates,best=1e12;
 var k=Math.cos(pt[1]*Math.PI/180);
 polys.forEach(function(p){p.forEach(function(r){
  for(var i=0;i<r.length-1;i++)best=Math.min(best,seg(pt,r[i],r[i+1],k))})});
 return best;
}
function seg(p,a,b,k){
 var px=p[0]*k,py=p[1],ax=a[0]*k,ay=a[1],bx=b[0]*k,by=b[1];
 var dx=bx-ax,dy=by-ay,L=dx*dx+dy*dy;
 var t=L?Math.max(0,Math.min(1,((px-ax)*dx+(py-ay)*dy)/L)):0;
 var cx=ax+t*dx,cy=ay+t*dy;
 return Math.hypot(px-cx,py-cy)*Math.PI/180*6371008.8;
}
})();
"""

SCENE_JS = r"""
/* Which frame is showing is decided by whichever scene holds most of the screen.
   An IntersectionObserver, not a scroll listener: a scroll listener is throttled to
   nothing when the tab is in the background. The backdrop's own frames carry
   data-scene too, so the observer is given the sections only. */
(function(){
var bgs=document.querySelectorAll('.backdrop .bg');
if(!bgs.length)return;
var seen={},shown=null;
function show(s){
 if(s===shown)return;shown=s;
 bgs.forEach(function(b){b.classList.toggle('on',b.dataset.scene===s)});
}
var io=new IntersectionObserver(function(es){
 es.forEach(function(e){if(e.target.dataset.scene)seen[e.target.dataset.scene]=e.intersectionRatio});
 var best=null,v=0;
 for(var k in seen){if(seen[k]>v){v=seen[k];best=k}}
 if(best&&v>0.12)show(best);
},{threshold:[0,.12,.25,.5,.75,1]});
document.querySelectorAll('main>[data-scene],footer[data-scene]').forEach(function(el){io.observe(el)});
})();
"""
