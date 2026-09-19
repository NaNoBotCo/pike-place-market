# -*- coding: utf-8 -*-
"""harvest_licences.py — who holds an active Seattle business licence inside the fence.

The city publishes every active business licence tax certificate with a trade name, a
street address, a NAICS trade code and the date the licence started. That last field is
the one this site is built on: it dates a business to the day, back to 1965, and it is
the only open, dated, address-level record of who trades at Pike Place.

Three steps, in this order, because the order is the point:

  1  pull every active licence on a street the fence touches
  2  put each one on a point, using the city's own Master Address File
  3  ask the fence

A licence that cannot be placed is kept and marked, never dropped. A licence placed
outside the fence is kept and marked too — the market's edge is only visible if the
near misses are.

  python3 tools/harvest_licences.py

Source: data.seattle.gov resource wnbq-64tb (Socrata SODA 2.1), open data, no key.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (HARVEST, dist_to_fence_m, fence, getj, jload,   # noqa: E402
                    pt_in_poly, write_harvest)

RES = "https://data.seattle.gov/resource/wnbq-64tb.json"
LIC = "City of Seattle Open Data — open, no licence asserted"

# Every street the district's boundary touches, as the licence file spells them.
STREETS = ["PIKE PL", "POST AL", "PIKE ST", "WESTERN AVE", "1ST AVE",
           "VIRGINIA ST", "STEWART ST", "PINE ST", "FIRST AVE", "POST ALLEY"]

SUFFIX = {"AL": "ALLEY", "ALY": "ALLEY", "AVE": "AVE", "AV": "AVE", "PL": "PL",
          "PLACE": "PL", "ST": "ST", "STREET": "ST", "WAY": "WAY"}
ORDINAL = {"FIRST": "1ST", "SECOND": "2ND", "THIRD": "3RD"}

# Seventeen rows in the licence file spell a street in a way no rule reaches: a doubled
# suffix, a hotel name where the street should be, a floor number left in. Each one is a
# reading of a specific string, listed so the reading can be argued with.
FIXUPS = {
    "PIKE PLACE MARKET": "PIKE PL",     # '1506 PIKE PLACE MARKET' — Oriental Mart, 1506 Pike Pl
    "PIKE PL 12": "PIKE PL",            # '1916 PIKE PL 12 #70' — a floor, not a street
    "PIKE PLACE ST": "PIKE ST",         # '85 PIKE PLACE ST' — 85 Pike St is the Economy Market
    "PIKE STREET HOMEWOOD SUITES": "PIKE ST",
    "PIKE ST W": "PIKE ST",             # '520 PIKE ST W' — downtown, and the fence says so
}


def norm_street(s: str) -> str:
    """Two files spell the same street three ways. This makes them one string."""
    s = re.sub(r"[^A-Z0-9 /]", " ", (s or "").upper())
    s = re.sub(r"\s+", " ", s).strip()
    parts = [ORDINAL.get(p, p) for p in s.split(" ")]
    if parts and parts[-1] in SUFFIX:
        parts[-1] = SUFFIX[parts[-1]]
    # 'PINE ST ST', '1ST AVE AV' — the file doubles the suffix on 11 rows
    while len(parts) > 2 and parts[-1] == parts[-2]:
        parts.pop()
    if len(parts) > 2 and parts[-2] in SUFFIX and SUFFIX[parts[-2]] == parts[-1]:
        parts.pop(-2)
    out = " ".join(parts)
    return FIXUPS.get(out, out)


def split_addr(a: str):
    """'1520 1/2 PIKE PL # 3' -> (1520.5, 'PIKE PL', '3'). Returns (None, ...) when the
    string has no house number, which happens and is not an error."""
    a = (a or "").upper().strip()
    unit = ""
    m = re.search(r"(?:#|\bSTE\b|\bSUITE\b|\bUNIT\b|\bAPT\b|\bRM\b)\s*([A-Z0-9-]+)", a)
    if m:
        unit = m.group(1)
        a = a[:m.start()].strip()
    a = re.sub(r"\s+(?:#|STE|SUITE|UNIT|APT|RM)\.?$", "", a).strip()
    m = re.match(r"^(\d+)\s*([A-Z])?\s*(?:(\d)\s*/\s*(\d))?\s+(.*)$", a)
    if not m:
        return (None, norm_street(a), unit, "")
    num = float(m.group(1))
    letter = m.group(2) or ""
    if m.group(3):
        num += float(m.group(3)) / float(m.group(4))
    return (num, norm_street(m.group(5)), unit, letter)


def maf_index() -> dict:
    """street -> [(number, letter, lon, lat, raw)], from the city's address file."""
    d = jload(HARVEST / "gis-addresses.json")
    if not d:
        raise SystemExit("no address harvest — run tools/harvest_gis.py --layers first")
    idx = {}
    for row in d["rows"]:
        p = row["properties"]
        pt = p.get("_pt")
        if not pt:
            continue
        num, street, _unit, letter = split_addr(p.get("MAF_ADDRESS") or "")
        if num is None:
            continue
        idx.setdefault(street, []).append((num, letter, pt[0], pt[1], p.get("MAF_ADDRESS")))
    for v in idx.values():
        v.sort()
    return idx


def place(num, street, letter, idx):
    """Exact house number first. Then the nearest number on the same street, within six,
    which is a doorway or two — flagged, so a reader can see it was inferred."""
    rows = idx.get(street)
    if not rows or num is None:
        return None, None, None
    exact = [r for r in rows if r[0] == num and (r[1] == letter or not letter)]
    if exact:
        r = exact[0]
        return (r[2], r[3]), "exact", r[4]
    near = min(rows, key=lambda r: abs(r[0] - num))
    if abs(near[0] - num) <= 6:
        return (near[2], near[3]), "nearest", near[4]
    return None, None, None


def pull() -> list:
    where = "zip='98101' AND (%s)" % " OR ".join(
        "upper(street_address) like '%%%s%%'" % s for s in STREETS)
    out, off = [], 0
    while True:
        page = getj(RES, {"$where": where, "$limit": 1000, "$offset": off,
                          "$order": "license_start_date"}, timeout=120)
        out.extend(page)
        if len(page) < 1000:
            break
        off += 1000
    return out


def main() -> None:
    fen = fence()["geometry"]
    idx = maf_index()
    rows = pull()
    print("licences  %d active on the market's streets" % len(rows))

    kept = []
    for r in rows:
        num, street, unit, letter = split_addr(r.get("street_address"))
        pt, how, matched = place(num, street, letter, idx)
        ins = bool(pt and pt_in_poly(pt, fen))
        kept.append({
            "account": r.get("city_account_number"),
            "legal": (r.get("business_legal_name") or "").strip(),
            "trade": (r.get("trade_name") or "").strip(),
            "address": (r.get("street_address") or "").strip(),
            "unit": unit,
            "street": street,
            "number": num,
            "naics": r.get("naics_code"),
            "naics_text": r.get("naics_description"),
            "ownership": r.get("ownership_type"),
            "start": r.get("license_start_date"),
            "lon": round(pt[0], 6) if pt else None,
            "lat": round(pt[1], 6) if pt else None,
            "placed": how,
            "maf": matched,
            "inside": ins,
            "edge_m": round(dist_to_fence_m(pt[0], pt[1]), 1) if pt else None,
        })

    write_harvest("licences.json", kept,
                  "City of Seattle — active business license tax certificates",
                  LIC, RES, "zip 98101, streets the district touches",
                  "placed against the city's Master Address File, then tested against the fence")

    ins = [k for k in kept if k["inside"]]
    print("          %d placed · %d unplaced · %d inside the fence"
          % (sum(1 for k in kept if k["lon"]), sum(1 for k in kept if not k["lon"]), len(ins)))
    print("          oldest inside: %s" % ", ".join(
        "%s (%s)" % (k["trade"] or k["legal"], k["start"][:4]) for k in ins[:5]))


if __name__ == "__main__":
    main()
