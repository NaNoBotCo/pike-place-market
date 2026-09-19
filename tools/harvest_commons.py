# -*- coding: utf-8 -*-
"""harvest_commons.py — freely licensed photographs of the market, licence attached.

Two verbs. `--find` lists candidates from Commons categories and searches into a triage
file, with each file's licence, author, size and the coordinate Commons holds for it —
nothing downloaded. `--get` downloads the ones named in data/images/picks.json at 1400 px
and writes a JSON sidecar beside each, plus a 520 px thumbnail.

The harvester takes CC0, public domain, CC BY, CC BY-SA and Free Art Licence files, and
lists anything else without taking it. Share-alike files are wanted here: the author and
the licence are written into the sidecar and printed beside the picture.

  python3 tools/harvest_commons.py --find
  python3 tools/harvest_commons.py --get
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import IMAGES, UA, inside, jdump, jload   # noqa: E402

API = "https://commons.wikimedia.org/w/api.php"
TRIAGE = IMAGES / "_triage.json"
PICKS = IMAGES / "picks.json"
FREE = re.compile(r"^(cc0|pd|public.?domain|cc.?by(.?sa)?([- ][1-4]\.[0-9])?|fal)", re.I)

CATEGORIES = [
    "Category:Pike Place Market",
    "Category:Pike Place Market Historic District",
    "Category:Pike Place Fish Market",
    "Category:Pike Place Market signs",
    "Category:Post Alley",
    "Category:Rachel the Pig",
    "Category:Interior of Pike Place Market",
    "Category:Historical images of Pike Place Market",
]
SEARCHES = [
    "Pike Place Market", "Pike Place Market arcade", "Pike Place Market stall",
    "Pike Place Market flowers", "Pike Place Market produce", "Seattle Pike Place neon",
]


def api(params: dict) -> dict:
    params = dict(params, format="json", formatversion=2)
    data = urllib.parse.urlencode(params).encode()
    for i in range(4):
        try:
            req = urllib.request.Request(API, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as exc:                                  # noqa: BLE001
            err = exc
            time.sleep(2 + 2 * i)
    raise RuntimeError("Commons API failed: %s" % err)


def filepath(title: str, width: int) -> str:
    """Commons now refuses arbitrary thumbnail widths on the upload host. Special:FilePath
    takes any width and redirects to the nearest rendition it will serve."""
    return ("https://commons.wikimedia.org/wiki/Special:FilePath/%s?width=%d"
            % (urllib.parse.quote(re.sub(r"^File:", "", title).replace(" ", "_")), width))


def strip(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def info(titles: list) -> list:
    out = []
    for i in range(0, len(titles), 20):
        d = api({"action": "query", "prop": "imageinfo|coordinates",
                 "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 1400,
                 "titles": "|".join(titles[i:i + 20])})
        for p in (d.get("query") or {}).get("pages", []):
            ii = (p.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata") or {}
            co = (p.get("coordinates") or [{}])[0]
            lic = strip(em.get("LicenseShortName", {}).get("value", ""))
            out.append({
                "title": p.get("title"),
                "page": "https://commons.wikimedia.org/wiki/%s"
                        % urllib.parse.quote((p.get("title") or "").replace(" ", "_")),
                "url": filepath(p.get("title") or "", 1400),
                "url_thumb": filepath(p.get("title") or "", 520),
                "commons_url": ii.get("url"),
                "width": ii.get("width"), "height": ii.get("height"),
                "mime": ii.get("mime"),
                "licence": lic,
                "licence_url": strip(em.get("LicenseUrl", {}).get("value", "")),
                "author": strip(em.get("Artist", {}).get("value", ""))[:180],
                "date": strip(em.get("DateTimeOriginal", {}).get("value", ""))[:32],
                "desc": strip(em.get("ImageDescription", {}).get("value", ""))[:300],
                "lat": co.get("lat"), "lon": co.get("lon"),
                "free": bool(FREE.match((lic or "").strip().lower().replace(" ", "-"))),
            })
        time.sleep(0.4)
    return out


def find() -> None:
    titles = set()
    for cat in CATEGORIES:
        cont = {}
        while True:
            d = api(dict({"action": "query", "list": "categorymembers", "cmtitle": cat,
                          "cmtype": "file", "cmlimit": 500}, **cont))
            for m in (d.get("query") or {}).get("categorymembers", []):
                titles.add(m["title"])
            if "continue" not in d:
                break
            cont = d["continue"]
            time.sleep(0.4)
    for s in SEARCHES:
        d = api({"action": "query", "list": "search", "srsearch": "%s filetype:bitmap" % s,
                 "srnamespace": 6, "srlimit": 60})
        for m in (d.get("query") or {}).get("search", []):
            titles.add(m["title"])
        time.sleep(0.4)

    rows = info(sorted(titles))
    for r in rows:
        r["in_fence"] = bool(r["lat"] and inside(r["lon"], r["lat"]))
    rows.sort(key=lambda r: (not r["free"], not r["in_fence"], -(r["width"] or 0)))
    jdump(TRIAGE, {"count": len(rows), "free": sum(1 for r in rows if r["free"]),
                   "in_fence": sum(1 for r in rows if r["in_fence"]), "rows": rows})
    print("commons %d files · %d freely licensed · %d with a coordinate inside the fence"
          % (len(rows), sum(1 for r in rows if r["free"]), sum(1 for r in rows if r["in_fence"])))


def get() -> None:
    picks = jload(PICKS) or {}
    triage = {r["title"]: r for r in (jload(TRIAGE) or {}).get("rows", [])}
    out = {}
    for key, title in picks.items():
        r = triage.get(title)
        if not r:
            print("  %-22s NOT IN TRIAGE %s" % (key, title))
            continue
        if not r["free"]:
            print("  %-22s SKIPPED, licence %s" % (key, r["licence"]))
            continue
        dest = IMAGES / ("%s.jpg" % key)
        thumb = IMAGES / ("%s.thumb.jpg" % key)
        for path, url in ((dest, filepath(title, 1600)), (thumb, filepath(title, 560))):
            if path.exists() and path.stat().st_size > 4000:
                continue
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as fh:
                path.write_bytes(fh.read())
            time.sleep(0.4)
        side = dict(r, key=key, file=dest.name, thumb=thumb.name)
        jdump(IMAGES / ("%s.json" % key), side)
        out[key] = side
        print("  %-22s %s" % (key, r["licence"]))
    jdump(IMAGES / "index.json", {"count": len(out), "images": out})
    print("images  %d on disk" % len(out))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--find", action="store_true")
    ap.add_argument("--get", action="store_true")
    a = ap.parse_args()
    if a.find:
        find()
    if a.get:
        get()
    if not (a.find or a.get):
        ap.print_help()


if __name__ == "__main__":
    main()
