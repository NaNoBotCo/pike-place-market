# Pike Place Market — the twelve acres, counted

A directory and GIS map of the **Pike Place Market Historical District**, Seattle, built
from open data and bounded by the district's own polygon.

**Live:** https://nanobotco.github.io/pike-place-market/

## The fence

Seattle's Land Use Code draws the district in [chapter
25.24](https://library.municode.com/wa/seattle/codes/municipal_code), and the city
publishes it as overlay code `PP` in its zoning overlay layer: a polygon with **30
corners, 12.83 acres and 1,101 metres of edge**. Every count on this site is that polygon
answering yes or no to a point. `tools/common.py` holds the ray-casting test and every
other tool calls it; nothing else gets to decide.

## Five counts of one place

| Who is counting | What they count | Figure |
|---|---|---|
| City of Seattle | active business licences at an address inside the polygon | **153** |
| Pike Place Market PDA | vendors on its own roster | **473** |
| OpenStreetMap | named points inside the polygon | **170** |
| City of Seattle | addresses in the Master Address File inside the polygon | **215** |
| The Market, about itself | "220+ shops, 180+ craftspeople, 70+ farmers, 60+ buskers" | **530+** |

None of them is wrong. The licence file misses every daystall craftsperson and farmer,
because they trade under the Market's own permits rather than a city licence of their
own — **383 of the 473 on the roster match no licence at a market address**. OpenStreetMap
is a volunteer survey and holds what somebody happened to map. And the Market describes
itself as a **10-level, 9-acre** operation, which is 3.83 acres smaller than the historic
district it sits inside: the difference is privately owned buildings on First Avenue,
Post Alley and Western Avenue that answer to the district's rules without being the
Market.

## What the licence dates show

The licence file carries a start date, which makes it the only dated, address-level
record of who trades here. Inside the line:

- **median tenure 24.7 years**, against **18.7 years** for licensed businesses within
  150 m of the boundary and outside it
- **68%** past twenty years inside, **46%** outside
- **22%** past forty years inside, **4%** outside
- oldest inside: **The Art Stall Gallery, 1965**, then the Athenian Inn (1966) and Pure
  Food Fish Market (1968)

Active licences only, both columns: a business that closed leaves the file, so this is
the age of what is standing rather than a survival rate.

## The map

`docs/map/` runs MapLibre GL JS against GeoJSON files in this repository — the ground,
the building outlines, the district and the points are all files beside the page, and
the district is drawn as a hole cut in a dark mask. Filters for trade, licence age and
name; a layer each for the near misses just outside the line, what OpenStreetMap names,
and the city's public art, trees, crossings and kerb space; and a **where am I** button
that compares the device's position against the boundary in the browser.

## Build

```
python3 tools/harvest_gis.py --all        # the fence, then the city's layers
python3 tools/harvest_osm.py --refetch    # one call to the OSM map API, cached
python3 tools/harvest_licences.py         # licences, placed, then fenced
python3 tools/harvest_pda.py --rest --visit
python3 tools/harvest_pda.py --pages      # ~80 min at the ten seconds its robots asks
python3 tools/harvest_commons.py --find   # then edit data/images/picks.json
python3 tools/harvest_commons.py --get
python3 tools/shrink.py
python3 tools/build.py                    # writes docs/
python3 tests/test_site.py                # 18 gates
python3 tools/serve.py 8821               # look at it
```

`tools/analyze.py` writes `data/analysis.json`, and no page template types a figure: a
number on the site is the number in that file on the day it was built.

## Things that cost a rebuild

- **Overpass will not serve this box.** 504s and timeouts across mirrors. The main OSM
  API's `map` call returns the whole bounding box as XML in three seconds; use it.
- **Commons refuses arbitrary thumbnail widths now.** `Special:FilePath/<file>?width=N`
  takes any width and redirects to a rendition it will serve.
- **A shared street number is not a building.** Twenty tenants are registered at 85 Pike
  St and the address file holds one point for it. Assigning them all to the nearest
  outline put a daystall photographer inside the Leland Hotel. Where the point falls
  inside an outline the building is the place; otherwise the address is, and the page
  says so.
- **Comparing raw counts across groups of 153 and 46** says more about the group sizes
  than about the market. The inside-outside chart shows shares.
- **The licence file spells one street three ways** — `PINE ST ST`, `1ST AVE AV`, `1506
  PIKE PLACE MARKET`. Seventeen rows need a named reading, listed in
  `tools/harvest_licences.py` so the reading can be argued with.
- **MapLibre needs a visible tab.** Its style loads on a `requestAnimationFrame`, which
  never fires in a hidden or backgrounded tab, so the map stays blank there with no error.
  Verify it over CDP in a foreground page.
- **`site` is a standard library module.** A `tools/site.py` is already in `sys.modules`
  at startup and will not shadow it. This one is `tools/shell.py`.

## Licences

Code MIT (`LICENSE-MIT`). Prose and derived figures CC BY 4.0 (`LICENSE`). OpenStreetMap
geometry stays ODbL 1.0 with its share-alike terms. Photographs keep the licence named
beside them. Full breakdown in `NOTICE.txt`.
