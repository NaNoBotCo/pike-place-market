# -*- coding: utf-8 -*-
"""mapdata.py — the GeoJSON the map draws, and nothing beyond the fence.

The ground under the map is drawn from the same OpenStreetMap extract the rest of the
site uses, clipped to the bounding box, and every layer ships as a file beside the page.
The box is why the map cannot pan away from the market: the files hold nothing further
out.

Writes docs/data/*.geojson.

  python3 tools/mapdata.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, DOCS, HARVEST, fence, jdump, jload   # noqa: E402

OUT = DOCS / "data"

# what to draw under everything else, in the order it paints
GROUND = [
    ("water", lambda t: t.get("natural") == "water" or t.get("waterway") or
     t.get("landuse") == "reservoir"),
    ("green", lambda t: t.get("leisure") in ("park", "garden", "pitch") or
     t.get("landuse") in ("grass", "forest") or t.get("natural") == "wood"),
    ("pier", lambda t: t.get("man_made") == "pier"),
    ("rail", lambda t: t.get("railway") in ("tram", "rail", "light_rail")),
    ("road", lambda t: t.get("highway") in
     ("primary", "secondary", "tertiary", "residential", "unclassified",
      "living_street", "service", "trunk", "motorway")),
    ("foot", lambda t: t.get("highway") in ("footway", "pedestrian", "path", "corridor")),
    ("steps", lambda t: t.get("highway") == "steps"),
]


def fc(feats: list, **extra) -> dict:
    d = {"type": "FeatureCollection", "features": feats}
    d.update(extra)
    return d


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fen = fence()
    shapes = (jload(HARVEST / "osm-shapes.json") or {"rows": []})["rows"]
    pois = (jload(HARVEST / "osm-pois.json") or {"rows": []})["rows"]
    direc = jload(DATA / "directory.json") or {}
    blds = (jload(DATA / "buildings.json") or {"rows": []})["rows"]

    jdump(OUT / "fence.geojson", fc([fen]))

    # ---- the ground
    ground = []
    for kind, test in GROUND:
        for s in shapes:
            if not test(s["tags"]):
                continue
            geom = ({"type": "Polygon", "coordinates": [s["line"]]} if s["closed"]
                    else {"type": "LineString", "coordinates": s["line"]})
            ground.append({"type": "Feature", "geometry": geom,
                           "properties": {"kind": kind, "name": s["tags"].get("name"),
                                          "inside": s["inside"],
                                          "level": s["tags"].get("level"),
                                          "osm": s["osm"]}})
    jdump(OUT / "ground.geojson", fc(ground, note="OpenStreetMap, ODbL 1.0"))

    # ---- buildings, named ones carrying their floor count
    named = {b["osm"]: b for b in blds}
    bfeat = []
    for s in shapes:
        t = s["tags"]
        if "building" not in t or not s["closed"]:
            continue
        b = named.get(s["osm"])
        bfeat.append({"type": "Feature",
                      "geometry": {"type": "Polygon", "coordinates": [s["line"]]},
                      "properties": {
                          "name": t.get("name"), "id": b["id"] if b else None,
                          "levels": (b or {}).get("levels"),
                          "kind": t.get("building"), "inside": s["inside"],
                          "area_m2": (b or {}).get("area_m2"),
                          "osm": s["osm"]}})
    jdump(OUT / "buildings.geojson", fc(bfeat, note="OpenStreetMap, ODbL 1.0"))

    # ---- the directory as points
    vend = []
    for r in direc.get("licences", []):
        vend.append({"type": "Feature",
                     "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                     "properties": {
                         "name": r["trade"] or r["legal"], "legal": r["legal"],
                         "trade": r["naics_text"], "sector": r["sector"],
                         "naics": r["naics"], "start": r["start"],
                         "years": r["years"], "address": r["address"],
                         "unit": r["unit"], "building": r["building"],
                         "place": r.get("place"), "place_kind": r.get("place_kind"),
                         "placed": r["placed"], "source": "licence"}})
    jdump(OUT / "vendors.geojson", fc(vend, note="City of Seattle business licences, placed on the city's Master Address File"))

    near = []
    for r in direc.get("near_misses", []):
        near.append({"type": "Feature",
                     "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                     "properties": {"name": r["trade"] or r["legal"],
                                    "trade": r["naics_text"], "start": r["start"],
                                    "years": r.get("years"), "edge_m": r["edge_m"],
                                    "address": r["address"], "source": "near"}})
    jdump(OUT / "near.geojson", fc(near, note="licensed businesses within 150 m of the line, and outside it"))

    # ---- what OpenStreetMap knows that the licence file does not
    osmf = []
    for p in pois:
        t = p["tags"]
        if not p["inside"] or not t.get("name"):
            continue
        kind = (t.get("shop") or t.get("amenity") or t.get("craft") or t.get("tourism")
                or t.get("historic") or t.get("office") or t.get("leisure") or "")
        osmf.append({"type": "Feature",
                     "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
                     "properties": {"name": t.get("name"), "kind": kind,
                                    "level": t.get("level"), "osm": p["osm"],
                                    "website": t.get("website"),
                                    "hours": t.get("opening_hours"),
                                    "source": "osm"}})
    jdump(OUT / "osm.geojson", fc(osmf, note="OpenStreetMap, ODbL 1.0"))

    # ---- the city's own furniture
    extras = []
    for name, label in (("publicart", "public art"), ("trees", "tree"),
                        ("crosswalks", "crossing"), ("garages", "parking"),
                        ("streetpark", "kerb space")):
        d = jload(HARVEST / ("gis-%s.json" % name))
        if not d:
            continue
        for f in d["rows"]:
            p = f["properties"]
            if not p.get("_inside") or not p.get("_pt"):
                continue
            title = (p.get("ARTWORK_TITLE") or p.get("TITLE") or p.get("COMMON_NAME")
                     or p.get("SCIENTIFIC_NAME") or p.get("NAME") or p.get("FACILITY")
                     or label)
            extras.append({"type": "Feature",
                           "geometry": {"type": "Point", "coordinates": p["_pt"]},
                           "properties": {"kind": label, "name": str(title)[:90]}})
    jdump(OUT / "extras.geojson", fc(extras, note="City of Seattle open data"))

    print("map    fence + %d ground · %d buildings · %d in the directory · %d near misses"
          % (len(ground), len(bfeat), len(vend), len(near)))
    print("       %d named in OpenStreetMap · %d pieces of city furniture"
          % (len(osmf), len(extras)))


if __name__ == "__main__":
    main()
