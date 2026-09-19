# -*- coding: utf-8 -*-
"""build.py — write the whole site into docs/.

  python3 tools/build.py

Order matters: the analysis file and the map bundle are rebuilt first, so a page can
never be written from yesterday's numbers.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DOCS, IMAGES, ROOT, today   # noqa: E402

TOOLS = Path(__file__).resolve().parent


def run(script: str, *args) -> None:
    r = subprocess.run([sys.executable, str(TOOLS / script)] + list(args))
    if r.returncode:
        raise SystemExit("%s failed" % script)


def main() -> None:
    t0 = time.time()
    run("analyze.py")
    run("mapdata.py")

    # imports must come after analyze.py, which writes what they read
    import pages                                                 # noqa: E402
    from shell import CSS, NAV, SITE                             # noqa: E402

    (DOCS / "site.css").write_text(CSS, encoding="utf-8")

    # pictures and the map library travel with the site
    dst = DOCS / "images"
    dst.mkdir(parents=True, exist_ok=True)
    for p in IMAGES.glob("*.jpg"):
        shutil.copy2(p, dst / p.name)
    vend = DOCS / "vendor"
    vend.mkdir(parents=True, exist_ok=True)
    for p in (ROOT / "vendor").glob("maplibre*"):
        shutil.copy2(p, vend / p.name)

    pages.write("index.html", pages.home())
    pages.write("map/index.html", pages.map_page())
    pages.write("directory/index.html", pages.directory())
    pages.write("trades/index.html", pages.trades())
    pages.write("age/index.html", pages.age_page())
    pages.write("fence/index.html", pages.fence_page())
    pages.write("daniel-fleming/index.html", pages.daniel_page())
    pages.write("sources/index.html", pages.sources())
    pages.write("api/index.html", pages.api_page())

    nb = pages.place_pages()
    nt = pages.trade_pages()
    nc = pages.category_pages()
    nv = pages.vendor_pages()

    # ---- the files a crawler reads
    urls = sorted(p.relative_to(DOCS).as_posix().replace("index.html", "")
                  for p in DOCS.rglob("index.html"))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append("<url><loc>%s%s</loc><lastmod>%s</lastmod></url>" % (SITE, u, today()))
    sm.append("</urlset>")
    (DOCS / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")

    (DOCS / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n" % SITE, encoding="utf-8")

    (DOCS / "llms.txt").write_text("""# Pike Place Market — the twelve acres, counted

A directory and GIS map of the Pike Place Market Historical District, Seattle, built
from open data and bounded by the district's own polygon.

The boundary is Seattle Land Use Code chapter 25.24, overlay code PP, taken from the
city's zoning overlay layer. Everything on this site is that polygon answering yes or
no to a point.

- %sdirectory/ — businesses grouped by the building they stand in
- %smap/ — every point, drawn from this site's own GeoJSON, no tile server
- %sage/ — how long licences have run, inside the line and just outside it
- %sfence/ — how the boundary is drawn and what falls inside it
- %ssources/ — every dataset, its licence and the hour it was read
- %sapi/ — the GeoJSON and JSON files

Data: City of Seattle open data; OpenStreetMap contributors (ODbL 1.0); the Pike Place
Market PDA's own vendor roster; Wikimedia Commons for photographs. Code MIT, text and
figures CC BY 4.0.
""" % ((SITE,) * 6), encoding="utf-8")

    (DOCS / "404.html").write_text(
        pages.head("Not here — Pike Place Market", "No page at that address.", 0, "")
        + '<main id="main"><div class="in"><div class="paper"><h1>Not here</h1>'
          '<p class="lede">Nothing at that address. The <a href="/pike-place-market/'
          'directory/">directory</a> and the <a href="/pike-place-market/map/">map</a> '
          'both hold every business on this site.</p></div></div></main>'
        + pages.foot(0), encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    html = len(list(DOCS.rglob("*.html")))
    mb = sum(p.stat().st_size for p in DOCS.rglob("*") if p.is_file()) / 1e6
    print("build  %d pages — %d places · %d trades · %d categories · %d vendors"
          % (html, nb, nt, nc, nv))
    print("       %.1f MB in docs/ · %.1f s" % (mb, time.time() - t0))


if __name__ == "__main__":
    main()
