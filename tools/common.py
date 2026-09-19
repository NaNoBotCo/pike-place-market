# -*- coding: utf-8 -*-
"""common.py — paths, JSON, and the geometry every other tool leans on.

The fence is the organising idea of this repository. A harvest file carries its source,
its licence and the hour it was fetched; a record carries the point it sits on; and
`inside()` decides whether that point is in the Pike Place Market Historical District.
Nothing else in the build gets to decide that.
"""
from __future__ import annotations

import json
import math
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
HARVEST = DATA / "harvest"
GEO = DATA / "geo"
NODES = DATA / "nodes"
IMAGES = DATA / "images"
SOURCES = DATA / "sources"
DOCS = ROOT / "docs"

UA = ("pike-place-build/0.1 (+https://nanobotco.github.io/pike-place-market/; "
      "nan@motdang.net) python-urllib")

# The bounding box every bulk fetch is clipped to. Deliberately larger than the fence,
# so that "just outside" is measurable rather than invisible.
BBOX = (47.6055, -122.3460, 47.6130, -122.3380)   # S, W, N, E


# ---------------------------------------------------------------- files

def jload(p: Path, default=None):
    p = Path(p)
    if not p.exists():
        return default
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def jdump(p: Path, obj) -> Path:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    return p


def stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def today() -> str:
    return time.strftime("%Y-%m-%d")


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return re.sub(r"-{2,}", "-", s) or "x"


# ---------------------------------------------------------------- network

def get(url: str, params: dict = None, tries: int = 4, pause: float = 1.2,
        data: dict = None, timeout: int = 120) -> bytes:
    """One GET (or POST, with data=) with retries. Every fetch in this repo goes here so
    the user agent and the back-off are the same everywhere."""
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode(data).encode() if data else None
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as fh:
                return fh.read()
        except Exception as exc:                                   # noqa: BLE001
            last = exc
            time.sleep(pause * (i + 1) ** 2)
    raise RuntimeError("fetch failed after %d tries: %s (%s)" % (tries, url[:120], last))


def getj(url: str, params: dict = None, **kw):
    return json.loads(get(url, params, **kw).decode("utf-8"))


# ---------------------------------------------------------------- geometry

R_EARTH_M = 6371008.8


def haversine(a: tuple, b: tuple) -> float:
    """Metres between two (lat, lon) points."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH_M * math.asin(min(1.0, math.sqrt(h)))


def ring_area_m2(ring: list) -> float:
    """Spherical excess of one [[lon, lat], ...] ring, in square metres. Signed."""
    if len(ring) < 4:
        return 0.0
    total = 0.0
    for i in range(len(ring) - 1):
        lon1, lat1 = math.radians(ring[i][0]), math.radians(ring[i][1])
        lon2, lat2 = math.radians(ring[i + 1][0]), math.radians(ring[i + 1][1])
        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    return total * R_EARTH_M * R_EARTH_M / 2.0


def ring_len_m(ring: list) -> float:
    return sum(haversine((ring[i][1], ring[i][0]), (ring[i + 1][1], ring[i + 1][0]))
               for i in range(len(ring) - 1))


def poly_area_m2(coords: list, kind: str = "Polygon") -> float:
    polys = [coords] if kind == "Polygon" else coords
    out = 0.0
    for p in polys:
        for i, ring in enumerate(p):
            a = abs(ring_area_m2(ring))
            out += a if i == 0 else -a
    return out


def poly_len_m(coords: list, kind: str = "Polygon") -> float:
    polys = [coords] if kind == "Polygon" else coords
    return sum(ring_len_m(r) for p in polys for r in p)


def pt_in_ring(pt: tuple, ring: list) -> bool:
    """Ray casting. pt is (lon, lat); ring is [[lon, lat], ...]."""
    x, y = pt
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y):
            xc = (xj - xi) * (y - yi) / ((yj - yi) or 1e-18) + xi
            if x < xc:
                inside = not inside
        j = i
    return inside


def pt_in_poly(pt: tuple, geom: dict) -> bool:
    """pt is (lon, lat). geom is a GeoJSON Polygon or MultiPolygon geometry."""
    kind = geom.get("type")
    polys = [geom["coordinates"]] if kind == "Polygon" else geom["coordinates"]
    for p in polys:
        if not p:
            continue
        if pt_in_ring(pt, p[0]) and not any(pt_in_ring(pt, h) for h in p[1:]):
            return True
    return False


def centroid(coords: list, kind: str = "Polygon") -> tuple:
    """Area-weighted centre of a polygon, as (lon, lat)."""
    polys = [coords] if kind == "Polygon" else coords
    sx = sy = sa = 0.0
    for p in polys:
        ring = p[0]
        a2 = 0.0
        cx = cy = 0.0
        for i in range(len(ring) - 1):
            x1, y1 = ring[i]
            x2, y2 = ring[i + 1]
            cr = x1 * y2 - x2 * y1
            a2 += cr
            cx += (x1 + x2) * cr
            cy += (y1 + y2) * cr
        if abs(a2) < 1e-16:
            continue
        sx += cx / (3 * a2) * abs(a2 / 2)
        sy += cy / (3 * a2) * abs(a2 / 2)
        sa += abs(a2 / 2)
    if sa == 0:
        return tuple(polys[0][0][0])
    return (sx / sa, sy / sa)


def bbox_of(geom: dict) -> tuple:
    """(minlon, minlat, maxlon, maxlat) of any GeoJSON geometry."""
    xs, ys = [], []

    def walk(c):
        if not c:
            return
        if isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for k in c:
                walk(k)

    walk(geom.get("coordinates"))
    return (min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------- the fence

_FENCE = None


def fence() -> dict:
    """The Pike Place Market Historical District, as one GeoJSON feature. Everything
    this site holds is decided against this polygon."""
    global _FENCE
    if _FENCE is None:
        f = jload(GEO / "fence.geojson")
        if not f:
            raise SystemExit("no fence on disk — run tools/harvest_gis.py --fence first")
        _FENCE = f
    return _FENCE


def inside(lon: float, lat: float) -> bool:
    return pt_in_poly((float(lon), float(lat)), fence()["geometry"])


def dist_to_fence_m(lon: float, lat: float) -> float:
    """Metres from a point to the fence boundary, negative when inside."""
    best = 1e12
    g = fence()["geometry"]
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
    for p in polys:
        for ring in p:
            for i in range(len(ring) - 1):
                best = min(best, _seg_dist(lon, lat, ring[i], ring[i + 1]))
    return -best if inside(lon, lat) else best


def _seg_dist(lon: float, lat: float, a: list, b: list) -> float:
    k = math.cos(math.radians(lat))
    px, py = lon * k, lat
    ax, ay = a[0] * k, a[1]
    bx, by = b[0] * k, b[1]
    dx, dy = bx - ax, by - ay
    t = 0.0 if (dx * dx + dy * dy) == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy) * math.pi / 180 * R_EARTH_M


# ---------------------------------------------------------------- harvest files

def write_harvest(name: str, rows, source: str, licence: str, url: str,
                  query: str = "", note: str = "") -> Path:
    """A harvest file is never a record. It carries where it came from, under what
    licence, at what hour, and the query that produced it, so that an absence reads as
    'not in this source on that date' rather than 'not there'."""
    return jdump(HARVEST / name, {
        "source": source, "licence": licence, "url": url,
        "query": query, "note": note,
        "fetched": stamp(), "count": len(rows), "rows": rows,
    })
