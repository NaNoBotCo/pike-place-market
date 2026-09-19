# -*- coding: utf-8 -*-
"""harvest_pda.py — the Market's own roster of who trades there.

The Preservation and Development Authority runs the market and publishes a vendor
directory on a WordPress site whose REST API is open. Its robots.txt allows everything
and asks for ten seconds between requests, so:

  --rest    ten requests, the whole roster: name, description, categories, tags, link
  --pages   one request per vendor, ten seconds apart, for the street address the REST
            API does not expose. Cached per vendor, so a stopped run resumes.

What the roster is and is not: it is the market's own list of current vendors, which
covers daystall craftspeople and farmers who hold no city business licence of their own
and therefore appear nowhere in the licence file. It carries no coordinates. Matching it
to the licence file is done later, in analyze.py, by name.

  python3 tools/harvest_pda.py --rest
  python3 tools/harvest_pda.py --pages          # about eighty minutes
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HARVEST, get, getj, jdump, jload, stamp, write_harvest   # noqa: E402

SITE = "https://www.pikeplacemarket.org"
API = SITE + "/wp-json/wp/v2"
CACHE = HARVEST / "_raw" / "pda"
DELAY = 10          # their robots.txt asks for ten seconds; this is that
SRC = "Pike Place Market PDA — pikeplacemarket.org, WordPress REST API and vendor pages"
LIC = ("text and images belong to the Market and its vendors; held here as facts about "
       "who trades where, quoted short, with a link back to the page each came from")


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def paged(kind: str, fields: str) -> list:
    out, page = [], 1
    while True:
        rows = getj("%s/%s" % (API, kind),
                    {"per_page": 100, "page": page, "_fields": fields}, timeout=120)
        out.extend(rows)
        if len(rows) < 100:
            break
        page += 1
        time.sleep(1.0)
    return out


def rest() -> None:
    cats = paged("vendor_categories", "id,name,slug,count,parent")
    tags = paged("vendor_tags", "id,name,slug,count")
    vends = paged("vendor", "id,slug,link,title,vendor_categories,vendor_tags,"
                            "yoast_head_json,modified")

    cat_by = {c["id"]: c for c in cats}
    rows = []
    for v in vends:
        y = v.get("yoast_head_json") or {}
        img = (y.get("og_image") or [{}])[0]
        rows.append({
            "id": v["id"], "slug": v["slug"], "link": v["link"],
            "name": clean((v.get("title") or {}).get("rendered")),
            "blurb": clean(y.get("description")),
            "cats": [clean(cat_by[c]["name"]) for c in v.get("vendor_categories", []) if c in cat_by],
            "cat_ids": v.get("vendor_categories", []),
            "tags": v.get("vendor_tags", []),
            "photo": img.get("url"),
            "modified": v.get("modified"),
        })

    jdump(HARVEST / "pda-categories.json",
          {"source": SRC, "licence": LIC, "url": API + "/vendor_categories",
           "fetched": stamp(), "count": len(cats),
           "rows": [{"id": c["id"], "name": clean(c["name"]), "slug": c["slug"],
                     "count": c["count"], "parent": c["parent"]} for c in cats]})
    jdump(HARVEST / "pda-tags.json",
          {"source": SRC, "licence": LIC, "url": API + "/vendor_tags",
           "fetched": stamp(), "count": len(tags),
           "rows": [{"id": t["id"], "name": clean(t["name"]), "slug": t["slug"],
                     "count": t["count"]} for t in tags]})
    write_harvest("pda-vendors.json", rows, SRC, LIC, API + "/vendor",
                  "per_page=100, all pages", "the Market's own current vendor roster")
    print("pda    %d vendors · %d categories · %d tags" % (len(rows), len(cats), len(tags)))


ADDR = re.compile(r"((?:\d[\dA-Za-z\-/ ]{0,12})?\s*"
                  r"(?:Pike Pl(?:ace)?|Pike St(?:reet)?|Post Alley|Western Ave(?:nue)?|"
                  r"1st Ave(?:nue)?|First Ave(?:nue)?|Stewart St|Virginia St|Pine St)"
                  r"[^<>|]{0,40}?)\s*(?:Seattle|,|<)", re.I)


def one_page(slug: str, link: str) -> dict:
    f = CACHE / ("%s.html" % slug)
    if not f.exists():
        raw = get(link, timeout=90)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(raw)
        time.sleep(DELAY)
    h = f.read_text(encoding="utf-8", errors="replace")
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    m = re.search(r"(?is)<article.*?</article>", h) or re.search(r"(?is)<main.*?</main>", h)
    body = m.group(0) if m else h
    txt = clean(body)
    # the vendor's own links, before the site furniture starts
    cut = txt.find("Search for:")
    txt = txt[:cut] if cut > 0 else txt
    # the address sits immediately before the page's "( Map It )" link
    where = ""
    mm = re.search(r"([^|]{0,120}?)\(\s*Map It\s*\)", txt)
    if mm:
        where = clean(mm.group(1))
    addr = ADDR.search(where or txt)
    sites = [u for u in re.findall(r'href="(https?://[^"]+)"', body)
             if "pikeplacemarket.org" not in u
             and not re.search(r"(gmpg\.org|fonts\.googleapis|fonts\.gstatic|gravatar|w\.org|schema\.org|wp\.me)", u)
             and not re.search(r"(facebook|instagram|twitter|x\.com|tiktok|youtube|pinterest|linkedin|yelp)\.", u)]
    social = [u for u in re.findall(r'href="(https?://[^"]+)"', body)
              if re.search(r"(facebook|instagram|twitter|x\.com|tiktok|youtube)\.", u)]
    return {"address": clean(addr.group(1)) if addr else "",
            "where": where,
            "text": txt[:1400],
            "sites": sorted(set(sites))[:4],
            "social": sorted(set(social))[:4]}


def pages(limit: int) -> None:
    d = jload(HARVEST / "pda-vendors.json")
    if not d:
        raise SystemExit("run --rest first")
    rows = d["rows"]
    done = 0
    for i, v in enumerate(rows):
        if v.get("_page"):
            continue
        try:
            v["_page"] = one_page(v["slug"], v["link"])
        except Exception as exc:                                    # noqa: BLE001
            v["_page"] = {"error": str(exc)[:120]}
        done += 1
        if done % 10 == 0:
            jdump(HARVEST / "pda-vendors.json", d)
            print("  %d/%d  %s" % (i + 1, len(rows), v["name"][:40]), flush=True)
        if limit and done >= limit:
            break
    jdump(HARVEST / "pda-vendors.json", d)
    got = sum(1 for v in rows if (v.get("_page") or {}).get("address"))
    print("pages  %d fetched · %d carry a street address" % (done, got))


VISIT = SITE + "/plan-your-visit/"

# The visitor page's own labels, with the one that reads as a fragment out of context
# given the heading it sits under.
HOUR_KEYS = ["Breakfast", "Fresh Produce | & | Seafood", "Crafts Market", "Farm Tables",
             "Artisanal Food Program", "Open daily", "Restrooms", "Restaurants",
             "Secret Garden"]
RELABEL = {"Open daily": "Merchant buildings"}


def visit() -> None:
    """The Market's own published hours, and the Market's own count of itself. Both are
    quoted, dated and linked; neither is recomputed here, because they are claims by the
    body that runs the place rather than measurements."""
    import html as _h
    raw = get(VISIT, timeout=120)
    h = raw.decode("utf-8", "replace")
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    t = _h.unescape(re.sub(r"(?s)<[^>]+>", " | ", h))
    t = re.sub(r"(\s*\|\s*)+", " | ", t)

    hours = []
    for k in HOUR_KEYS:
        m = re.search(re.escape(k) + r"\s*\|?\s*:?\s*\|?\s*([^|]{2,60})", t)
        if m:
            label = k.replace(" | ", " ")
            hours.append({"what": RELABEL.get(label, label),
                          "when": m.group(1).strip(" :|")})

    figs = []
    for m in re.finditer(r"(\d[\d,]*\+?)\s+([a-z][a-z ,\-]{4,60}?)(?=,| and |\.|\|)", t):
        n, what = m.group(1), m.group(2).strip()
        if any(w in what for w in ("shops", "craftspeople", "farmers", "buskers",
                                   "residents", "level", "acre")):
            figs.append({"count": n, "what": what})

    band = re.search(r"most of Pike Place Market is active from (.{3,64}?)(?= with| \|)", t)
    shut = re.search(r"open 7 days a week, closed only on ([^.]{3,60})\.", t)
    size = re.search(r"Our ([\d\-]+-level, [\d.]+-acre) Market", t)

    jdump(HARVEST / "pda-visit.json", {
        "source": "Pike Place Market PDA — Plan Your Visit",
        "url": VISIT, "fetched": stamp(),
        "licence": LIC,
        "active_band": band.group(1).strip() if band else "",
        "closed_days": shut.group(1).strip() if shut else "",
        "self_description": size.group(1) if size else "",
        "count": len(hours) + len(figs),
        "hours": hours, "figures": figs,
    })
    print("visit  %d hour lines · %d figures the Market gives for itself"
          % (len(hours), len(figs)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--visit", action="store_true")
    ap.add_argument("--rest", action="store_true")
    ap.add_argument("--pages", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.visit:
        visit()
    if a.rest:
        rest()
    if a.pages:
        pages(a.limit)
    if not (a.rest or a.pages or a.visit):
        ap.print_help()


if __name__ == "__main__":
    main()
