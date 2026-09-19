# -*- coding: utf-8 -*-
"""harvest_gis.py — the City of Seattle's own layers, clipped to the market.

The first verb is the one that matters. `--fence` fetches a single polygon: the Pike
Place Market Historical District as the Land Use Code draws it (SMC Chapter 25.24),
overlay code PP in the city's zoning overlay layer. Every later decision in this
repository is that polygon answering yes or no.

  python3 tools/harvest_gis.py --fence
  python3 tools/harvest_gis.py --layers
  python3 tools/harvest_gis.py --all

Source: City of Seattle Open Data (data-seattlecitygis.opendata.arcgis.com), ArcGIS
FeatureServer endpoints, public domain / open. Attribution goes on the page.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BBOX, GEO, bbox_of, centroid, getj, jdump, poly_area_m2,   # noqa: E402
                    poly_len_m, pt_in_poly, stamp, write_harvest)

HOST = "https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services"
LIC = "City of Seattle Open Data — open / public domain"
PORTAL = "https://data-seattlecitygis.opendata.arcgis.com/"

# name -> (service, layer id, fields we keep, what it is for)
LAYERS = {
    "buildings": ("Building_Outlines_2023", 0, "*",
                  "every roofed structure the city mapped in 2023"),
    "addresses": ("Active_Addresses_(MAF)NEW", 0, "*",
                  "the Master Address File — what turns a licence's street address into a point"),
    "landmarks": ("Landmarks", 0, "*", "individually designated city landmarks"),
    "publicart": ("Public_Art", 0, "*", "the city's public art inventory"),
    "parcels": ("Parcel_Boundary", 0, "*", "tax parcels under the market"),
    "trees": ("Combined_Tree_Point", 0, "*", "street and park trees"),
    "crosswalks": ("Marked_Crosswalks_(Active)", 0, "*", "marked crossings"),
    "garages": ("Public_Garages_and_Parking_Lots", 1, "*", "where a car can be left"),
    "streetpark": ("Parking_Features", 2, "*", "every metered and signed kerb space"),
    "zoning": ("Current_Land_Use_Zoning_Detail_2", 0, "*", "what the code allows on each block"),
}

FENCE_SERVICE = "Zoning_Overlays-Historic-Special_Review_Districts"
FENCE_LAYER = 23
FENCE_WHERE = "OVERLAY='PP'"


def q(service: str, layer: int, **kw) -> dict:
    url = "%s/%s/FeatureServer/%d/query" % (HOST, service.replace(" ", "%20"), layer)
    params = {"f": "geojson", "outSR": 4326, "where": "1=1", "outFields": "*",
              "returnGeometry": "true", "resultRecordCount": 2000}
    params.update(kw)
    return getj(url, params, timeout=180)


def envelope() -> dict:
    s, w, n, e = BBOX
    return {"geometry": "%f,%f,%f,%f" % (w, s, e, n),
            "geometryType": "esriGeometryEnvelope", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects"}


def fetch_fence() -> None:
    fc = q(FENCE_SERVICE, FENCE_LAYER, where=FENCE_WHERE)
    feats = fc.get("features") or []
    if not feats:
        raise SystemExit("the PP overlay returned nothing — the layer may have moved")
    f = feats[0]
    g = f["geometry"]
    area = poly_area_m2(g["coordinates"], g["type"])
    per = poly_len_m(g["coordinates"], g["type"])
    cen = centroid(g["coordinates"], g["type"])
    f["properties"].update({
        "fetched": stamp(),
        "source": "City of Seattle zoning overlays, layer %d, %s" % (FENCE_LAYER, FENCE_WHERE),
        "licence": LIC, "portal": PORTAL,
        "area_m2": round(area, 1), "area_acres": round(area / 4046.8564224, 3),
        "perimeter_m": round(per, 1),
        "centroid": [round(cen[0], 6), round(cen[1], 6)],
        "bbox": [round(v, 6) for v in bbox_of(g)],
        "rings": len(g["coordinates"]) if g["type"] == "Polygon" else sum(len(p) for p in g["coordinates"]),
        "vertices": _verts(g),
    })
    jdump(GEO / "fence.geojson", f)
    print("fence  %.3f acres · %.0f m around · %d vertices"
          % (f["properties"]["area_acres"], per, f["properties"]["vertices"]))


def _verts(g: dict) -> int:
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
    return sum(len(r) for p in polys for r in p)


def fetch_layers(only=None) -> None:
    from common import fence
    fen = fence()["geometry"]
    for name, (svc, lyr, flds, note) in LAYERS.items():
        if only and name not in only:
            continue
        try:
            fc = q(svc, lyr, outFields=flds, **envelope())
        except Exception as exc:                                   # noqa: BLE001
            print("%-11s FAILED %s" % (name, exc))
            continue
        feats = fc.get("features") or []
        for ft in feats:
            gg = ft.get("geometry") or {}
            pt = _rep_point(gg)
            ft["properties"]["_pt"] = [round(pt[0], 6), round(pt[1], 6)] if pt else None
            ft["properties"]["_inside"] = _touches(gg, pt, fen)
        n_in = sum(1 for f in feats if f["properties"]["_inside"])
        write_harvest("gis-%s.json" % name, feats,
                      source="City of Seattle Open Data — %s" % svc,
                      licence=LIC,
                      url="%s/%s/FeatureServer/%d" % (HOST, svc, lyr),
                      query="envelope %s" % (BBOX,), note=note)
        print("%-11s %5d in the box · %4d inside the fence" % (name, len(feats), n_in))


def _touches(g: dict, pt, fen) -> bool:
    """A point is in or out. An outline counts as inside when its centre or any of its
    corners is, so a building that straddles the line is not dropped by a millimetre."""
    if pt and pt_in_poly(pt, fen):
        return True
    for c in _verts_of(g):
        if pt_in_poly(c, fen):
            return True
    return False


def _verts_of(g: dict):
    out = []

    def walk(c):
        if not c:
            return
        if isinstance(c[0], (int, float)):
            out.append((c[0], c[1]))
        else:
            for k in c:
                walk(k)

    walk((g or {}).get("coordinates"))
    return out


def _rep_point(g: dict):
    if not g:
        return None
    t = g.get("type")
    if t == "Point":
        return tuple(g["coordinates"][:2])
    if t in ("Polygon", "MultiPolygon"):
        try:
            return centroid(g["coordinates"], t)
        except Exception:                                          # noqa: BLE001
            return None
    if t in ("LineString", "MultiLineString"):
        cs = g["coordinates"] if t == "LineString" else g["coordinates"][0]
        return tuple(cs[len(cs) // 2][:2])
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fence", action="store_true")
    ap.add_argument("--layers", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.fence or a.all:
        fetch_fence()
    if a.layers or a.all or a.only:
        fetch_layers([s for s in a.only.split(",") if s] or None)
    if not (a.fence or a.layers or a.all or a.only):
        ap.print_help()


if __name__ == "__main__":
    main()
