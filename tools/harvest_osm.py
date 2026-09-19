# -*- coding: utf-8 -*-
"""harvest_osm.py — everything OpenStreetMap holds inside the box, in one request.

Overpass times out on this box often enough that it is not worth depending on. The main
API's `map` call returns the whole bounding box as XML in about three seconds, and the
box is small, so that is what this uses. One fetch, cached to data/harvest/_raw/, and
every later run works offline against the cache unless `--refetch` is passed.

  python3 tools/harvest_osm.py            # from cache if present
  python3 tools/harvest_osm.py --refetch  # go back to the API

Licence: OpenStreetMap contributors, ODbL 1.0. Share-alike, so the attribution block on
the site names it and the harvest file carries it.
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BBOX, HARVEST, centroid, fence, get, pt_in_poly,   # noqa: E402
                    write_harvest)

API = "https://api.openstreetmap.org/api/0.6/map"
LIC = "OpenStreetMap contributors, ODbL 1.0"
RAW = HARVEST / "_raw" / "osm-map.xml"

# A tag is interesting when it names something a person can walk into, look at, sit on,
# or trip over. Everything else in the box is left where it is.
POI_KEYS = ("shop", "amenity", "tourism", "craft", "office", "leisure", "historic",
            "artwork_type", "vending", "cuisine", "healthcare", "man_made")
WAY_KEYS = ("highway", "building", "barrier", "waterway", "natural", "landuse",
            "man_made", "railway", "bridge")


def fetch(refetch: bool) -> bytes:
    if RAW.exists() and not refetch:
        return RAW.read_bytes()
    s, w, n, e = BBOX
    raw = get(API, {"bbox": "%f,%f,%f,%f" % (w, s, e, n)}, timeout=180)
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_bytes(raw)
    return raw


def parse(raw: bytes):
    root = ET.fromstring(raw)
    nodes, ways, rels = {}, {}, {}
    for el in root:
        tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
        if el.tag == "node":
            nodes[el.get("id")] = {"id": el.get("id"),
                                   "lon": float(el.get("lon")), "lat": float(el.get("lat")),
                                   "tags": tags}
        elif el.tag == "way":
            ways[el.get("id")] = {"id": el.get("id"),
                                  "nd": [n.get("ref") for n in el.findall("nd")],
                                  "tags": tags}
        elif el.tag == "relation":
            rels[el.get("id")] = {"id": el.get("id"), "tags": tags,
                                  "members": [(m.get("type"), m.get("ref"), m.get("role"))
                                              for m in el.findall("member")]}
    return nodes, ways, rels


def line_of(way, nodes):
    out = []
    for ref in way["nd"]:
        nd = nodes.get(ref)
        if nd:
            out.append([round(nd["lon"], 7), round(nd["lat"], 7)])
    return out


def closed(line):
    return len(line) > 3 and line[0] == line[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true")
    a = ap.parse_args()

    raw = fetch(a.refetch)
    nodes, ways, rels = parse(raw)
    fen = fence()["geometry"]
    print("osm    %d nodes · %d ways · %d relations in the box" % (len(nodes), len(ways), len(rels)))

    pois, shapes = [], []

    for nd in nodes.values():
        t = nd["tags"]
        if not any(k in t for k in POI_KEYS) and "name" not in t:
            continue
        if not t:
            continue
        pois.append({"osm": "node/%s" % nd["id"], "lon": nd["lon"], "lat": nd["lat"],
                     "tags": t, "inside": pt_in_poly((nd["lon"], nd["lat"]), fen)})

    for w in ways.values():
        t = w["tags"]
        line = line_of(w, nodes)
        if len(line) < 2:
            continue
        keep = any(k in t for k in WAY_KEYS) or any(k in t for k in POI_KEYS)
        if not keep:
            continue
        shut = closed(line)
        pt = centroid([line], "Polygon") if shut else tuple(line[len(line) // 2])
        ins = pt_in_poly(pt, fen) or any(pt_in_poly(tuple(c), fen) for c in line)
        shapes.append({"osm": "way/%s" % w["id"], "closed": shut, "line": line,
                       "tags": t, "inside": ins,
                       "pt": [round(pt[0], 7), round(pt[1], 7)]})
        if shut and (any(k in t for k in POI_KEYS) or ("building" in t and "name" in t)):
            pois.append({"osm": "way/%s" % w["id"], "lon": pt[0], "lat": pt[1],
                         "tags": t, "inside": ins, "area": True})

    for r in rels.values():
        t = r["tags"]
        if t.get("type") not in ("multipolygon", "building") or "building" not in t:
            continue
        outers = [line_of(ways[ref], nodes) for typ, ref, role in r["members"]
                  if typ == "way" and role in ("outer", "") and ref in ways]
        outers = [o for o in outers if len(o) > 2]
        if not outers:
            continue
        big = max(outers, key=len)
        pt = centroid([big], "Polygon")
        ins = pt_in_poly(pt, fen) or any(pt_in_poly(tuple(c), fen) for c in big)
        shapes.append({"osm": "relation/%s" % r["id"], "closed": True, "line": big,
                       "tags": t, "inside": ins, "pt": [round(pt[0], 7), round(pt[1], 7)]})

    q = "GET %s?bbox=%s" % (API, BBOX)
    write_harvest("osm-pois.json", pois, "OpenStreetMap", LIC, API, q,
                  "named points and areas — a shop, a bench, a statue, a stall")
    write_harvest("osm-shapes.json", shapes, "OpenStreetMap", LIC, API, q,
                  "ways and multipolygons — buildings, streets, footways, steps, water")

    print("       %d points (%d inside) · %d shapes (%d inside)"
          % (len(pois), sum(1 for p in pois if p["inside"]),
             len(shapes), sum(1 for s in shapes if s["inside"])))
    b = [s for s in shapes if s["inside"] and "building" in s["tags"]]
    h = [s for s in shapes if s["inside"] and "highway" in s["tags"]]
    print("       inside: %d buildings · %d ways of street or path · %d named points"
          % (len(b), len(h), sum(1 for p in pois if p["inside"] and p["tags"].get("name"))))


if __name__ == "__main__":
    main()
