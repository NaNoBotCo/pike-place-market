# -*- coding: utf-8 -*-
"""analyze.py — every number the site prints, computed here and nowhere else.

Nothing in the page templates may type a figure. They interpolate from
data/analysis.json, which this writes, so a number on the site is always the number in
the data on the day it was built.

  python3 tools/analyze.py
"""
from __future__ import annotations

import collections
import datetime as dt
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, HARVEST, centroid, dist_to_fence_m, fence, haversine,   # noqa: E402
                    jdump, jload, pt_in_ring, slugify, today)

TODAY = dt.date.today()

# NAICS two-digit sectors, named as the census names them. Used to group 153 trades
# into something a reader can hold in their head.
SECTOR = {
    "11": "Farming", "21": "Mining", "22": "Utilities", "23": "Construction",
    "31": "Making", "32": "Making", "33": "Making", "42": "Wholesale",
    "44": "Retail", "45": "Retail", "48": "Transport", "49": "Transport",
    "51": "Publishing and broadcast", "52": "Finance", "53": "Property and rental",
    "54": "Professional services", "55": "Company offices", "56": "Admin and support",
    "61": "Teaching", "62": "Health and care", "71": "Arts and recreation",
    "72": "Food and lodging", "81": "Other services", "92": "Public bodies",
}


def years(start: str) -> float:
    try:
        d = dt.date(int(start[0:4]), int(start[4:6]), int(start[6:8]))
    except Exception:                                              # noqa: BLE001
        return 0.0
    return (TODAY - d).days / 365.2425


def norm_name(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    s = re.sub(r"\b(inc|llc|ltd|co|corp|the|and|of|at|pike|place|market|seattle|"
               r"company|studio|shop|store|llp|pllc|dba)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- buildings

def buildings() -> list:
    """The named structures inside the fence, from OpenStreetMap, each with its outline,
    its floor count where OSM records one, and its area."""
    d = jload(HARVEST / "osm-shapes.json") or {"rows": []}
    out = []
    for s in d["rows"]:
        t = s["tags"]
        if not s["inside"] or "building" not in t or not s["closed"]:
            continue
        name = t.get("name")
        if not name:
            continue
        ring = s["line"]
        from common import ring_area_m2
        out.append({
            "id": slugify(name), "name": name, "osm": s["osm"],
            "kind": t.get("building"),
            "levels": int(t["building:levels"]) if (t.get("building:levels") or "").isdigit() else None,
            "start": t.get("start_date"), "wikidata": t.get("wikidata"),
            "addr": " ".join(x for x in (t.get("addr:housenumber"), t.get("addr:street")) if x),
            "area_m2": round(abs(ring_area_m2(ring)), 1),
            "pt": s["pt"], "ring": ring,
        })
    seen, uniq = {}, []
    for b in out:
        if b["id"] in seen:                # OSM holds the Main Arcade twice
            if b["area_m2"] > seen[b["id"]]["area_m2"]:
                seen[b["id"]].update(b)
            continue
        seen[b["id"]] = b
        uniq.append(b)
    uniq.sort(key=lambda b: -b["area_m2"])
    return uniq


BY_ID_NAME = {}

SUFFIX_CASE = {"ST": "St", "AVE": "Ave", "PL": "Pl", "ALLEY": "Alley", "WAY": "Way"}


def _title(street: str) -> str:
    out = []
    for w in (street or "").split():
        out.append(SUFFIX_CASE.get(w, w.title() if not w[:1].isdigit() else w.lower()))
    return " ".join(out)


def in_building(lon, lat, blds):
    """Inside a footprint, or — because a doorway point often sits a few metres off the
    outline the city drew — the nearest one within twenty-five metres, marked as such."""
    for b in blds:
        if pt_in_ring((lon, lat), b["ring"]):
            return b["id"], "within"
    near = min(blds, key=lambda b: haversine((lat, lon), (b["pt"][1], b["pt"][0])))
    d = haversine((lat, lon), (near["pt"][1], near["pt"][0]))
    if d < 25:
        return near["id"], "nearest"
    return None, None


# ---------------------------------------------------------------- the work

def main() -> None:
    fen = fence()
    fp = fen["properties"]
    blds = buildings()
    global BY_ID_NAME
    BY_ID_NAME = {b["id"]: b["name"] for b in blds}

    lic = (jload(HARVEST / "licences.json") or {"rows": []})["rows"]
    ins = [r for r in lic if r["inside"]]
    out = [r for r in lic if r["lon"] and not r["inside"]]
    near = [r for r in out if (r["edge_m"] or 9e9) <= 150]

    for r in ins:
        r["building"], r["building_how"] = in_building(r["lon"], r["lat"], blds)
        # Where a point falls inside a footprint, the building is the place. Where it
        # only sits NEAR one, the address is the place: 85 Pike St is the Market's own
        # street number and twenty tenants share it, so naming a building for them would
        # be a guess dressed as a fact.
        if r["building_how"] == "within":
            r["place"], r["place_kind"] = r["building"], "building"
        else:
            r["building"] = None
            r["place_kind"] = "address"
            r["place"] = slugify("%d-%s" % (int(r["number"]), r["street"])) if r["number"] else None
        r["years"] = round(years(r["start"] or ""), 2)
        r["sector"] = SECTOR.get((r["naics"] or "")[:2], "Not classified")
    for r in near:
        r["years"] = round(years(r["start"] or ""), 2)

    pda = (jload(HARVEST / "pda-vendors.json") or {"rows": []})["rows"]
    cats = (jload(HARVEST / "pda-categories.json") or {"rows": []})["rows"]

    # -------- the two rosters, matched by name
    by_norm = {}
    for r in ins:
        for nm in (r["trade"], r["legal"]):
            n = norm_name(nm)
            if len(n) > 3:
                by_norm.setdefault(n, r)
    matched = 0
    for v in pda:
        n = norm_name(v["name"])
        hit = by_norm.get(n)
        if not hit and len(n) > 5:
            hit = next((r for k, r in by_norm.items() if n in k or k in n), None)
        v["licence"] = hit["account"] if hit else None
        v["start"] = hit["start"] if hit else None
        v["building"] = hit.get("building") if hit else None
        if hit:
            matched += 1

    # -------- tenure
    def tenure(rows):
        ys = sorted(r["years"] for r in rows if r.get("years"))
        if not ys:
            return {}
        n = len(ys)
        return {"n": n, "median": round(ys[n // 2], 1),
                "mean": round(sum(ys) / n, 1),
                "over_20": sum(1 for y in ys if y >= 20),
                "over_40": sum(1 for y in ys if y >= 40),
                "under_5": sum(1 for y in ys if y < 5),
                "oldest": round(ys[-1], 1)}

    decade = collections.Counter()
    for r in ins:
        if r["start"] and len(r["start"]) >= 4:
            decade["%ds" % (int(r["start"][:4]) // 10 * 10)] += 1

    by_year = collections.Counter(int(r["start"][:4]) for r in ins
                                  if r["start"] and r["start"][:4].isdigit())

    # -------- trades
    sectors = collections.Counter(r["sector"] for r in ins)
    trades = collections.Counter(r["naics_text"] for r in ins if r["naics_text"])

    # -------- addresses and buildings
    addr = collections.Counter(("%d %s" % (int(r["number"]), r["street"])) for r in ins if r["number"])
    per_bld = collections.Counter(r["building"] for r in ins if r["building"])
    per_place = collections.Counter(r["place"] for r in ins if r["place"])
    place_name = {}
    for r in ins:
        if not r["place"]:
            continue
        place_name[r["place"]] = (BY_ID_NAME.get(r["place"], r["place"])
                                  if r["place_kind"] == "building"
                                  else "%d %s" % (int(r["number"]), _title(r["street"])))

    # -------- what each source counts
    osm = (jload(HARVEST / "osm-pois.json") or {"rows": []})["rows"]
    osm_in = [p for p in osm if p["inside"] and p["tags"].get("name")]
    osm_trade = [p for p in osm_in if any(k in p["tags"] for k in
                                          ("shop", "amenity", "craft", "office"))]

    # -------- the fence's own geometry
    acres = fp["area_acres"]
    counts = {}
    for name in ("addresses", "buildings", "parcels", "trees", "crosswalks",
                 "publicart", "landmarks", "streetpark", "garages"):
        d = jload(HARVEST / ("gis-%s.json" % name))
        counts[name] = {"in_fence": sum(1 for f in (d or {"rows": []})["rows"]
                                        if f["properties"].get("_inside")),
                        "in_box": len((d or {"rows": []})["rows"])} if d else None

    # -------- the Market's published hours, turned into something a clock can answer
    def parse_band(txt):
        """'11 a.m. - 4 p.m.' -> (11.0, 16.0). '7 a.m.' -> (7.0, None), because the
        Market publishes an opening hour for some things and no closing one."""
        t = (txt or "").replace("\u2013", "-").replace("\u2014", "-")
        times = re.findall(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m", t, re.I)
        out = []
        for h, m, ap in times[:2]:
            v = int(h) % 12 + (12 if ap.lower() == "p" else 0) + (int(m or 0) / 60.0)
            out.append(round(v, 3))
        if not out:
            return (None, None, [])
        days = []
        dm = re.search(r"\(([A-Za-z]{3})\s*-\s*([A-Za-z]{3})\)", t)
        if dm:
            names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            try:
                a, b = names.index(dm.group(1)[:3].title()), names.index(dm.group(2)[:3].title())
                days = [(a + i) % 7 for i in range((b - a) % 7 + 1)]
            except ValueError:
                days = []
        close = out[1] if len(out) > 1 else None
        if close is not None and close < out[0]:      # restaurants run to 2 a.m.
            close += 24
        return (out[0], close, days)

    # -------- what the Market says about itself
    visit = jload(HARVEST / "pda-visit.json") or {}
    m = re.search(r"([\d.]+)-acre", visit.get("self_description") or "")
    market_acres = float(m.group(1)) if m else None

    # -------- Daniel, three sources, two dates
    dan_lic = next((r for r in ins if "FLEMING" in (r["legal"] or "").upper()), None)
    dan_pda = next((v for v in pda if v["slug"] == "isellpictures-com"), None)

    an = {
        "built": today(),
        "fence": {
            "acres": acres, "m2": fp["area_m2"], "perimeter_m": fp["perimeter_m"],
            "vertices": fp["vertices"], "centroid": fp["centroid"], "bbox": fp["bbox"],
            "chapter": "Seattle Municipal Code chapter 25.24",
            "source": fp["source"], "fetched": fp["fetched"],
            "longest_m": round(max(fp["bbox"][2] - fp["bbox"][0],
                                   fp["bbox"][3] - fp["bbox"][1]) * 111320, 0),
        },
        "gis": counts,
        "licences": {
            "pulled": len(lic), "placed": sum(1 for r in lic if r["lon"]),
            "inside": len(ins), "outside_placed": len(out),
            "within_150m": len(near),
            "unplaced": sum(1 for r in lic if not r["lon"]),
            "nearest_matched": sum(1 for r in ins if r["placed"] == "nearest"),
            "per_acre": round(len(ins) / acres, 1),
            "in_a_named_building": sum(1 for r in ins if r["building"]),
            "building_within": sum(1 for r in ins if r.get("building_how") == "within"),
            "building_nearest": sum(1 for r in ins if r.get("building_how") == "nearest"),
            "tenure_in": tenure(ins), "tenure_near": tenure(near),
            "decades": dict(sorted(decade.items())),
            "by_year": dict(sorted(by_year.items())),
            "sectors": sectors.most_common(),
            "trades": trades.most_common(14),
            "addresses": addr.most_common(12),
            "oldest": [{"name": r["trade"] or r["legal"], "start": r["start"],
                        "years": r["years"], "trade": r["naics_text"],
                        "address": r["address"], "building": r["building"]}
                       for r in sorted(ins, key=lambda r: r["start"] or "9")[:16]],
            "newest": [{"name": r["trade"] or r["legal"], "start": r["start"],
                        "trade": r["naics_text"]}
                       for r in sorted(ins, key=lambda r: r["start"] or "0", reverse=True)[:8]],
        },
        "pda": {
            "vendors": len(pda), "categories": len(cats),
            "matched_to_licence": matched,
            "unmatched": len(pda) - matched,
            "top_categories": sorted(
                [{"name": c["name"], "count": c["count"], "parent": c["parent"],
                  "id": c["id"], "slug": c["slug"]} for c in cats],
                key=lambda c: -c["count"])[:30],
        },
        "osm": {
            "named_in_fence": len(osm_in), "trading_in_fence": len(osm_trade),
            "buildings": len(blds),
            "levels_known": sum(1 for b in blds if b["levels"]),
            "footways_m": round(sum(
                sum(haversine((s["line"][i][1], s["line"][i][0]),
                              (s["line"][i + 1][1], s["line"][i + 1][0]))
                    for i in range(len(s["line"]) - 1))
                for s in (jload(HARVEST / "osm-shapes.json") or {"rows": []})["rows"]
                if s["inside"] and s["tags"].get("highway") in
                ("footway", "steps", "pedestrian", "corridor", "path")), 0),
        },
        "buildings": [{k: v for k, v in b.items() if k != "ring"} for b in blds],
        "per_building": per_bld.most_common(),
        "per_place": [[k, v, place_name.get(k, k),
                       next(r["place_kind"] for r in ins if r["place"] == k)]
                      for k, v in per_place.most_common()],
        "counts": {
            "city_licences": len(ins),
            "market_roster": len(pda),
            "openstreetmap": len(osm_in),
            "market_self": visit.get("figures", []),
            "city_addresses": counts["addresses"]["in_fence"] if counts.get("addresses") else None,
        },
        "visit": visit,
        "hours": [dict(h, open=parse_band(h["when"])[0],
                       close=parse_band(h["when"])[1],
                       days=parse_band(h["when"])[2])
                  for h in visit.get("hours", [])],
        "acres": {
            "district": acres,
            "market_says": market_acres,
            "difference": round(acres - market_acres, 2) if market_acres else None,
        },
        "daniel": {
            "licence_name": dan_lic["legal"] if dan_lic else None,
            "trade_name": dan_lic["trade"] if dan_lic else None,
            "licence_start": dan_lic["start"] if dan_lic else None,
            "licence_years": dan_lic["years"] if dan_lic else None,
            "licence_address": dan_lic["address"] if dan_lic else None,
            "licence_trade": dan_lic["naics_text"] if dan_lic else None,
            "building": dan_lic.get("building") if dan_lic else None,
            "pda_name": dan_pda["name"] if dan_pda else None,
            "pda_blurb": dan_pda["blurb"] if dan_pda else None,
            "pda_link": dan_pda["link"] if dan_pda else None,
            "pda_cats": dan_pda["cats"] if dan_pda else [],
            "pda_says_since": 2007,
            "own_brief_2024": "eighteen years at the market, said in May 2024",
        },
    }

    jdump(DATA / "analysis.json", an)
    jdump(DATA / "buildings.json", {"count": len(blds), "rows": blds})
    jdump(DATA / "directory.json", {
        "built": today(),
        "licences": ins,
        "near_misses": sorted(near, key=lambda r: r["edge_m"])[:40],
        "vendors": pda,
        "categories": cats,
    })

    t = an["licences"]["tenure_in"]
    print("fence     %.2f acres · %d m around" % (acres, fp["perimeter_m"]))
    print("licences  %d inside · median %s years · %d past twenty · oldest %s"
          % (t["n"], t["median"], t["over_20"], t["oldest"]))
    print("rosters   %d on the Market's list · %d of them matched to a licence"
          % (len(pda), matched))
    print("osm       %d named points · %d named buildings · %.0f m of path"
          % (len(osm_in), len(blds), an["osm"]["footways_m"]))
    print("daniel    %s · licence %s · %s years"
          % (an["daniel"]["trade_name"], an["daniel"]["licence_start"],
             an["daniel"]["licence_years"]))


if __name__ == "__main__":
    main()
