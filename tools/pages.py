# -*- coding: utf-8 -*-
"""pages.py — every page the site has, written from data/analysis.json and the directory.

No figure is typed into a sentence here. Where a number appears it is interpolated from
the analysis file, so the page and the data cannot drift apart.
"""
from __future__ import annotations

import collections
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import viz                                                       # noqa: E402
from common import DATA, DOCS, HARVEST, jload, slugify, today    # noqa: E402
from shell import (CSS, E, MAP_JS, NAME, SCENE_JS, SITE, backdrop,   # noqa: E402
                   counters, foot, head, jsonld, plate, shot, table)

A = jload(DATA / "analysis.json") or {}
D = jload(DATA / "directory.json") or {}
B = (jload(DATA / "buildings.json") or {"rows": []})["rows"]
BY_ID = {b["id"]: b for b in B}
PLACES = A.get("per_place", [])
PLACE_NAME = {k: nm for k, _v, nm, _t in PLACES}
PLACE_KIND = {k: t for k, _v, _nm, t in PLACES}
LIC = D.get("licences", [])
VEND = D.get("vendors", [])
NEAR = D.get("near_misses", [])
CATS = D.get("categories", [])
VISIT = A.get("visit", {})


def n(x) -> str:
    try:
        return "{:,}".format(int(x))
    except Exception:                                            # noqa: BLE001
        return str(x)


def write(path: str, html: str) -> Path:
    p = DOCS / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    return p


def vendor_slug(name: str, key: str = "") -> str:
    return slugify("%s %s" % (name, key))[:70]


def _slug_tables():
    """One slug per business, decided once. A vendor can be known by two names — the
    trade name on the licence and the name on the Market's roster — and building the
    slug from whichever name a page happens to hold gives two addresses for one shop."""
    by_account, by_vendor = {}, {}
    for r in LIC:
        by_account[r["account"]] = vendor_slug(r["trade"] or r["legal"], r["account"][-4:])
    for v in VEND:
        if v.get("licence") and v["licence"] in by_account:
            by_vendor[v["id"]] = by_account[v["licence"]]
        else:
            by_vendor[v["id"]] = vendor_slug(v["name"], str(v["id"]))
    return by_account, by_vendor


SLUG_ACCOUNT, SLUG_VENDOR = _slug_tables()


def _shares(t: dict, tn: dict) -> list:
    """Median in years, then the three counts as shares — comparing raw counts across
    groups of 153 and 46 would say more about the group sizes than about the market."""
    def pc(a, b):
        return round(100.0 * a / max(b, 1))
    return [("median years", t["median"], tn["median"]),
            ("past twenty, %", pc(t["over_20"], t["n"]), pc(tn["over_20"], tn["n"])),
            ("past forty, %", pc(t["over_40"], t["n"]), pc(tn["over_40"], tn["n"])),
            ("under five, %", pc(t["under_5"], t["n"]), pc(tn["under_5"], tn["n"]))]


def year(start) -> str:
    s = str(start or "")
    return s[:4] if len(s) >= 4 else ""


# ------------------------------------------------------------------ the front

SCENES = [("hero", "hero"), ("hour", "now"), ("here", "near"), ("who", "peppers"),
          ("age", "tenure"), ("daniel", "daniel"), ("doors", "directory"),
          ("door", "door")]


def home() -> str:
    f, L, C = A["fence"], A["licences"], A["counts"]
    t = L["tenure_in"]
    tn = L["tenure_near"]
    ac = A["acres"]
    d = A["daniel"]

    hero = plate("""
<span class="wordmark">Pike Place Market · Seattle · Historical District</span>
<h1>Twelve acres,<br>counted</h1>
<p class="lede">Every business inside the line the city drew around Pike Place Market,
 the date each one started trading, and what the separate records of this place
 disagree about.</p>
<p class="nowline"><span class="lamp"><i id="lamp"></i><span id="clock">—</span></span>
 <span><b class="num">%s</b> acres</span>
 <span><b class="num">%s</b> with a licence</span>
 <span><b class="num">%s</b> on the Market's roster</span></p>
<p><a class="btn solid" href="map/">Open the map</a>
 <a class="btn" href="directory/">The directory</a></p>
""" % (ac["district"], n(C["city_licences"]), n(C["market_roster"])), "hero")

    hour = plate("""
<h2 class="kick">At this hour</h2>
<p class="lede">The Market publishes an hour for each part of itself, and the parts keep
 different hours. Read against the clock in Seattle, where it is <span id="clock2"
 class="num">—</span>.</p>
<ul class="hours" id="hours">%s</ul>
<p class="small">Quoted from the Market's visitor page, read %s. It trades seven days a
 week and closes on <b>%s</b>. Individual shops set their own hours; this is the
 Market's own band for each part, not a promise about any one stall.</p>
""" % ("".join(
        '<li data-o="%s" data-c="%s" data-d="%s"><i></i>'
        '<span class="w">%s</span><span class="t num">%s</span></li>'
        % ("" if h["open"] is None else h["open"],
           "" if h["close"] is None else h["close"],
           ",".join(str(x) for x in h["days"]),
           E(h["what"]), E(h["when"]))
        for h in A.get("hours", [])),
       E(VISIT.get("fetched", "")[:10]), E(VISIT.get("closed_days", ""))))

    here = plate("""
<h2 class="kick">Are you inside it?</h2>
<p class="lede">The district is a %s-cornered polygon with an area of %s acres and
 %s metres of edge. Standing anywhere near Pike Place, a step either way changes the
 answer.</p>
<p><button class="btn" id="locate">Ask my device</button></p>
<p class="where" id="whereami"></p>
<div id="nearlist"></div>
<p class="small">The device's position is compared in the browser against the
 boundary file on this page. <a href="fence/">How the line is drawn</a>.</p>
""" % (f["vertices"], ac["district"], n(int(f["perimeter_m"]))))

    who = plate("""
<h2 class="kick">Five counts of one place</h2>
%s
<p class="small">The Market's own figures are quoted from its visitor page, read %s.
 The licence count is what the city's file holds at an address the boundary contains.
 <a href="sources/">Each source, with the hour it was read</a>.</p>
""" % (counters([
        (n(C["city_licences"]), "hold a city business licence inside the line",
         "the only dated, address-level record of who trades here", "directory/"),
        (n(C["market_roster"]), "are on the Market's own vendor roster",
         "including the daystall craftspeople and farmers, who hold no separate city "
         "licence; %s of them print an address and reach the map" % n(A["pda"]["on_the_map"]),
         "directory/#roster"),
        (n(C["openstreetmap"]), "are named in OpenStreetMap",
         "a volunteer survey of the same twelve acres, and a third answer", "map/"),
        (n(C["city_addresses"]), "addresses inside the boundary",
         "from the city's Master Address File", "fence/"),
        ("%s" % ac["district"], "acres, as the city draws the district",
         "the Market's own page calls itself a %s Market — a difference of %s acres"
         % (E(VISIT.get("self_description", "")), ac["difference"]), "fence/"),
    ]), E(VISIT.get("fetched", "")[:10])))

    age = plate("""
<h2 class="kick">How long they stay</h2>
<p class="lede">Median time inside the line, on the same licence: <b class="num">%s
 years</b>. In the hundred and fifty metres outside it: <b class="num">%s years</b>.</p>
%s
<p>%s of the %s businesses inside the boundary have held the same licence for more than
 forty years. Among the %s licensed businesses within 150 m of the line and outside it,
 %s have.</p>
<p><a class="btn" href="age/">The whole distribution</a></p>
""" % (t["median"], tn["median"],
       viz.paired(_shares(t, tn),
                  "Inside the historical district (%s licences) against licensed "
                  "businesses within 150 m of it and outside (%s). The three shares are "
                  "percentages of each group, because the groups are different sizes. "
                  "Active licences only: a business that closed is in neither column."
                  % (n(t["n"]), n(tn["n"])),
                  "inside the line", "outside, within 150 m"),
       n(t["over_40"]), n(t["n"]), n(tn["n"]), tn["over_40"]))

    dan = plate("""
<h2 class="kick">One stall, in three records</h2>
<h3 style="margin-top:0">%s</h3>
<blockquote class="lede">%s</blockquote>
<p class="small">The Market's own description, quoted as published.</p>
<p>The city licensed <b>%s</b> to <b>%s</b> on <b>%s</b> — %s years ago. The Market's
 own roster says the business has sold here since %s. In May 2024 he put it at
 eighteen years. Three sources, two dates, one stall.</p>
<p><a class="btn solid" href="daniel-fleming/">His page</a>
 <a class="btn" href="https://isellpictures.com/">isellpictures.com</a></p>
""" % (E(d["pda_name"] or "Isellpictures.com"), E(d["pda_blurb"] or ""),
       E(d["trade_name"]), E(d["licence_name"]),
       E(_pretty(d["licence_start"])), int(d["licence_years"]), d["pda_says_since"]))

    doors = plate("""
<h2 class="kick">Every door</h2>
<ul class="tiles four">%s</ul>
""" % "".join("<li>%s</li>" % x for x in [
        shot("map/", "signage", "The map", 0, "%s points on one polygon" % n(L["inside"])),
        shot("directory/", "flowerrow", "The directory", 0,
             "%s places, %s trades" % (len(A["per_place"]), len(L["sectors"]))),
        shot("age/", "vendors1907" if "vendors1907" in _imgkeys() else "stalls1968",
             "Age", 0, "1965 to this year"),
        shot("fence/", "postalley", "The line", 0,
             "%s acres, %s corners" % (ac["district"], f["vertices"])),
        shot("trades/", "fish", "Trades", 0, "what the codes say"),
        shot("daniel-fleming/", "daniel", "Daniel Fleming", 0, "%s years" % int(d["licence_years"] or 0)),
        shot("sources/", "advert1909", "Sources", 0, "every fetch, dated"),
        shot("api/", "interior1968", "The data", 0, "GeoJSON and JSON"),
    ]), "wide")

    body = """
<main id="main">
<section class="s" data-scene="hero"><div class="in">%s</div>
 <a class="down" href="#here" aria-label="Down">&#8595;</a></section>
<section class="s" data-scene="hour"><div class="in">%s</div></section>
<section class="s" id="here" data-scene="here"><div class="in">%s</div></section>
<section class="s" data-scene="who"><div class="in">%s</div></section>
<section class="s" data-scene="age"><div class="in">%s</div></section>
<section class="s" data-scene="daniel"><div class="in">%s</div></section>
<section class="s flow" data-scene="doors"><div class="in">%s</div></section>
</main>
""" % (hero, hour, here, who, age, dan, doors)

    ld = jsonld({
        "@context": "https://schema.org", "@type": "WebSite", "name": NAME,
        "url": SITE, "description": "A geofenced directory and GIS map of the Pike Place "
        "Market Historical District, Seattle.",
        "publisher": {"@type": "Organization", "name": "NaNoBotCo"},
    })
    return (head("Pike Place Market — twelve acres, counted",
                 "Every licensed business inside the Pike Place Market Historical "
                 "District, when each started, and a map drawn from open data.",
                 0, "", ld)
            + backdrop(SCENES, 0) + body
            + '<footer class="door" data-scene="door">' + foot(0)[foot(0).index(">") + 1:]
            + "<script>%s</script><script>%s</script>" % (HOME_JS, SCENE_JS))


def _imgkeys():
    from shell import IMAGES
    return IMAGES


def _pretty(yyyymmdd) -> str:
    s = str(yyyymmdd or "")
    if len(s) != 8:
        return s
    try:
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:])).strftime("%-d %B %Y")
    except Exception:                                            # noqa: BLE001
        return s


HOME_JS = r"""
(function(){
/* The clock is Seattle's, wherever the reader is. The lamp is the Market's own
   published band for when most of it is trading, quoted on the visitor page. */
var band=[10,17];
var DAY={Mon:0,Tue:1,Wed:2,Thu:3,Fri:4,Sat:5,Sun:6};
function tick(){
 var d=new Date(),f=new Intl.DateTimeFormat('en-GB',{timeZone:'America/Los_Angeles',
  hour:'2-digit',minute:'2-digit',weekday:'short',hour12:false});
 var p={};f.formatToParts(d).forEach(function(x){p[x.type]=x.value});
 var h=+p.hour+ (+p.minute)/60, wd=DAY[p.weekday];
 var el=document.getElementById('clock'),lamp=document.getElementById('lamp');
 if(el)el.textContent=p.weekday+' '+p.hour+':'+p.minute+' in Seattle';
 var el2=document.getElementById('clock2');
 if(el2)el2.textContent=p.hour+':'+p.minute+', '+p.weekday;
 if(lamp)lamp.className=(h>=band[0]&&h<band[1])?'open':'shut';
 /* Each row carries the Market's own published band. A row with no closing hour
    published cannot be called shut, so it is left unlit rather than guessed at. */
 [].forEach.call(document.querySelectorAll('#hours li'),function(li){
  var o=li.dataset.o===''?null:+li.dataset.o,
      c=li.dataset.c===''?null:+li.dataset.c,
      days=li.dataset.d?li.dataset.d.split(',').map(Number):null;
  li.classList.remove('on','off');
  if(days&&days.length&&days.indexOf(wd)<0){li.classList.add('off');return}
  if(o===null)return;
  var now=h<6?h+24:h;                       /* a 2 a.m. close belongs to last night */
  if(c===null){li.classList.add(now>=o?'on':'off');return}
  li.classList.add(now>=o&&now<c?'on':'off');
 });
}
tick();setInterval(tick,20000);

var btn=document.getElementById('locate');
if(btn)btn.addEventListener('click',function(){
 var out=document.getElementById('whereami');
 if(!navigator.geolocation){out.textContent='This browser offers no position.';return}
 out.textContent='asking the device…';
 navigator.geolocation.getCurrentPosition(function(pos){
  var lon=pos.coords.longitude,lat=pos.coords.latitude;
  Promise.all([fetch('data/fence.geojson').then(function(r){return r.json()}),
               fetch('data/vendors.geojson').then(function(r){return r.json()})])
  .then(function(d){
   var g=d[0].features[0].geometry,ins=ptIn([lon,lat],g),m=Math.round(distTo([lon,lat],g));
   out.textContent=ins?('inside the district, '+m+' m from the nearest edge')
     :(m<4000?(m+' m outside the district'):'well outside the district');
   var rows=d[1].features.map(function(f){
    return {n:f.properties.name,t:f.properties.trade,y:f.properties.years,
            d:hav(lat,lon,f.geometry.coordinates[1],f.geometry.coordinates[0])}})
    .sort(function(a,b){return a.d-b.d}).slice(0,8);
   document.getElementById('nearlist').innerHTML='<ul class="rows">'+rows.map(function(r){
    return '<li><span class="nm">'+esc(r.n)+'<span class="meta">'+esc(r.t||'')+'</span></span>'+
     '<span class="yr">'+Math.round(r.d)+' m</span></li>'}).join('')+'</ul>';
  });
 },function(){out.textContent='the device declined'},{enableHighAccuracy:true,timeout:9000});
});
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
 return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function hav(la1,lo1,la2,lo2){var R=6371008.8,p=Math.PI/180;
 var a=Math.sin((la2-la1)*p/2),b=Math.sin((lo2-lo1)*p/2);
 var h=a*a+Math.cos(la1*p)*Math.cos(la2*p)*b*b;return 2*R*Math.asin(Math.sqrt(h))}
function ptIn(pt,g){var ps=g.type==='Polygon'?[g.coordinates]:g.coordinates;
 for(var i=0;i<ps.length;i++)if(ring(pt,ps[i][0]))return true;return false}
function ring(pt,r){var x=pt[0],y=pt[1],o=false;
 for(var i=0,j=r.length-1;i<r.length;j=i++){var xi=r[i][0],yi=r[i][1],xj=r[j][0],yj=r[j][1];
  if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/((yj-yi)||1e-18)+xi)o=!o}return o}
function distTo(pt,g){var ps=g.type==='Polygon'?[g.coordinates]:g.coordinates,best=1e12;
 var k=Math.cos(pt[1]*Math.PI/180);
 ps.forEach(function(p){p.forEach(function(r){for(var i=0;i<r.length-1;i++){
  var a=r[i],b=r[i+1],px=pt[0]*k,py=pt[1],ax=a[0]*k,ay=a[1],bx=b[0]*k,by=b[1];
  var dx=bx-ax,dy=by-ay,L=dx*dx+dy*dy;
  var t=L?Math.max(0,Math.min(1,((px-ax)*dx+(py-ay)*dy)/L)):0;
  best=Math.min(best,Math.hypot(px-(ax+t*dx),py-(ay+t*dy))*Math.PI/180*6371008.8)}})});
 return best}
})();
"""


# ------------------------------------------------------------------ the map

def map_page() -> str:
    f = A["fence"]
    sectors = sorted({r["sector"] for r in LIC})
    opts = "".join('<option value="%s">%s</option>' % (E(s), E(s)) for s in sectors)
    js = (MAP_JS.replace("DATAPREFIX", "../data/")
          .replace("CENTERLON", str(f["centroid"][0]))
          .replace("CENTERLAT", str(f["centroid"][1])))
    body = """
<main id="main"><div class="in"><div class="paper">
<h1>The map</h1>
<p class="lede">Every layer is a GeoJSON file in this repository, drawn in the
 browser. The dark ground is the world; the clear shape cut out of it is the district,
 and the map is bounded to it.</p>
<div class="ctl">
 <input type="search" id="q" placeholder="Find a business" aria-label="Find a business">
 <label>Trade <select id="sector"><option value="">all</option>%s</select></label>
 <button data-layer="roster-dot" aria-pressed="false">The Market's roster</button>
 <button data-layer="near-dot" aria-pressed="false">Just outside</button>
 <button data-layer="osm-dot" aria-pressed="false">OpenStreetMap</button>
 <button data-layer="extra-dot" aria-pressed="false">Art, trees, crossings</button>
 <button data-layer="blds-3d" aria-pressed="false">Floors</button>
 <button id="locate">Where am I</button>
</div>
<div class="ctl"><label>Older than <input type="range" id="age" min="0" max="60" step="5"
 value="0"> <span id="agev" class="num">any age</span></label></div>
<div id="map"></div>
<div id="plan" hidden>%s</div>
<p class="where" id="whereami"></p>
<div class="legend">
 <span><i style="background:#f3e7c6"></i>new</span>
 <span><i style="background:#efc75c"></i>ten years</span>
 <span><i style="background:#e07a2c"></i>twenty-five</span>
 <span><i style="background:#d8352a"></i>forty-five and over</span>
 <span><i style="background:#5fb3a1"></i>on the roster, no city licence</span>
 <span><i style="background:#8f7bb5"></i>on the roster and licensed</span>
 <span><i style="background:#6a8fb5"></i>licensed, outside the line</span>
 <span><i style="background:#f0bf4c"></i>named in OpenStreetMap</span>
</div>
<p class="small">The Market's roster layer holds the %s of its %s vendors whose own page
 prints a street number, placed the same way — which is how the daystall craftspeople and
 farmers, who hold no city licence, reach the map at all.</p>
<p class="small">Dots are licensed businesses, placed on the city's Master Address File
 and coloured by how long the licence has run. %s of the %s sit on an exact address
 match; %s were placed on the nearest number on the same street, within six doors.
 Building outlines and paths are OpenStreetMap, ODbL 1.0. The boundary is the city's
 zoning overlay layer.</p>
</div></div></main>
""" % (opts,
       n(A["pda"]["on_the_map"]), n(A["pda"]["vendors"]),
       viz.fence_plan(jload(DATA / "geo" / "fence.geojson")["geometry"], B,
                      "The district and its buildings, drawn flat — what a device "
                      "without WebGL gets instead of the map above."),
       n(A["licences"]["inside"] - A["licences"]["nearest_matched"]),
       n(A["licences"]["inside"]), A["licences"]["nearest_matched"])
    extra = ('<link rel="stylesheet" href="../vendor/maplibre-gl.css">'
             '<script src="../vendor/maplibre-gl.js"></script>')
    return (head("The map — Pike Place Market",
                 "An interactive map of every licensed business inside the Pike Place "
                 "Market Historical District, drawn from open data with no tile server.",
                 1, "map/", extra)
            + body + foot(1) + "<script>%s</script>" % js)


# ------------------------------------------------------------------ directory

def directory() -> str:
    lic_by_place = collections.defaultdict(list)
    for r in LIC:
        lic_by_place[r["place"]].append(r)

    def row(pid, cnt, name, kind):
        b = BY_ID.get(pid) if kind == "building" else None
        extra = ""
        if b and b["levels"]:
            extra = ' <span class="c">%s floors</span>' % b["levels"]
        elif kind == "address":
            extra = ' <span class="c">one street number</span>'
        return ('<li><a href="%s/"><b>%s</b></a> <span class="c">(%d)</span>%s</li>'
                % (pid, E(name), cnt, extra))

    blds = [p for p in PLACES if p[3] == "building"]
    addrs = [p for p in PLACES if p[3] == "address"]
    yahoo_b = "".join(row(*p) for p in blds)
    yahoo_a = "".join(row(*p) for p in addrs)

    tiles = "".join("<li>%s</li>" % shot("%s/" % pid, _bld_img(pid), name, 1,
                                         "%d businesses" % cnt)
                    for pid, cnt, name, kind in blds[:8])

    body = """
<main id="main"><div class="in"><div class="paper">
<h1>The directory</h1>
<p class="lede">%s licensed businesses, grouped by where they stand, because that is how
 the market is walked. %s of them sit inside a building outline the city and
 OpenStreetMap both hold; the rest share a street number with their neighbours and are
 grouped under it.</p>

<h2>Buildings</h2>
<ul class="yahoo">%s</ul>
<ul class="tiles four">%s</ul>

<h2>Shared street numbers</h2>
<p>A licence carries an address, not a coordinate, and the Market's own street numbers
 are shared: %s businesses are registered at %s alone. Where the address point does not
 fall inside a building outline, the address is as precise as the record gets, and the
 site says so rather than picking a building.</p>
<ul class="yahoo">%s</ul>

<h2 id="roster">The Market's own roster</h2>
<p>The Preservation and Development Authority lists %s current vendors, in %s
 categories. %s of those names match a city business licence at a market address. The
 other %s are the daystall system: craftspeople and farmers who rent a table by the day
 under the Market's own rules and appear in no city licence file. A name absent from the
 licence data is a statement about the licence data.</p>
<p>%s of the %s vendor pages print a street number of their own, and %s of those fall
 inside the boundary — which is how the unlicensed side of the market reaches
 <a href="../map/">the map</a>. %s carry a link to a site of their own.</p>
%s
<h2>Every category</h2>
<ul class="yahoo">%s</ul>
</div></div></main>
""" % (n(A["licences"]["inside"]), n(A["licences"]["building_within"]),
       yahoo_b, tiles,
       n(addrs[0][1]) if addrs else "0", E(addrs[0][2]) if addrs else "",
       yahoo_a,
       n(A["pda"]["vendors"]), n(A["pda"]["categories"]),
       n(A["pda"]["matched_to_licence"]), n(A["pda"]["unmatched"]),
       n(A["pda"]["with_address"]), n(A["pda"]["vendors"]), n(A["pda"]["on_the_map"]),
       n(A["pda"]["with_own_link"]),
       viz.bars([(c["name"], c["count"]) for c in A["pda"]["top_categories"][:18]],
                "Vendors per category on the Market's own roster. A vendor carries "
                "several categories at once, so the columns sum to more than %s."
                % n(A["pda"]["vendors"])),
       _cat_tree())
    return (head("Directory — Pike Place Market",
                 "Every licensed business in the Pike Place Market Historical District, "
                 "grouped by building and street number, with the Market's own roster.",
                 1, "directory/") + body + foot(1))


def _cat_tree() -> str:
    by_id = {c["id"]: c for c in CATS}
    tops = [c for c in CATS if not c["parent"] and c["count"]]
    tops.sort(key=lambda c: -c["count"])
    out = []
    for c in tops:
        kids = sorted([k for k in CATS if k["parent"] == c["id"] and k["count"]],
                      key=lambda k: -k["count"])[:6]
        sub = ", ".join('<a href="../category/%s/">%s</a> <span class="c">(%d)</span>'
                        % (E(k["slug"]), E(k["name"]), k["count"]) for k in kids)
        out.append('<li><a href="../category/%s/"><b>%s</b></a> <span class="c">(%d)</span>'
                   '%s</li>' % (E(c["slug"]), E(c["name"]), c["count"],
                                "<br><small>%s</small>" % sub if sub else ""))
    return "".join(out)


BLD_IMG = {
    "main-arcade": "sosio", "leland-hotel": "flowers", "corner-market": "neon",
    "sanitary-public-market": "arcade", "pike-virginia-building": "postalley",
    "inn-at-the-market-building": "peppers", "stewart-house": "produce",
    "triangle-building": "mosaic", "alaska-trade-building": "signage",
    "market-heritage-center": "economy1968", "first-pine-building": "busker",
    "landes-block": "shopping1970s", "north-arcade": "flowerrow",
    "champion-building": "rehab1977", "fairmount-apartments": "stalls1968",
}


def _bld_img(bid: str) -> str:
    return BLD_IMG.get(bid, "interior1968")


def place_pages() -> int:
    by_place = collections.defaultdict(list)
    for r in LIC:
        by_place[r["place"]].append(r)
    made = 0
    for pid, cnt, name, kind in PLACES:
        rows = sorted(by_place[pid], key=lambda r: (r["start"] or "9"))
        b = BY_ID.get(pid) if kind == "building" else None
        lines = "".join(
            '<li><span class="nm"><a href="../../vendor/%s/">%s</a>'
            '<span class="meta">%s · %s%s</span></span>'
            '<span class="yr">%s</span></li>'
            % (SLUG_ACCOUNT[r["account"]],
               E(r["trade"] or r["legal"]), E(r["naics_text"] or ""), E(r["address"]),
               " · unit %s" % E(r["unit"]) if r["unit"] else "", year(r["start"]))
            for r in rows)
        sect = collections.Counter(r["sector"] for r in rows)
        if b:
            where = ("<p>OpenStreetMap records <b>%s</b> floors. " % b["levels"]) if b["levels"] else "<p>"
            where += ("The footprint measures <b class=\"num\">%s</b> m&sup2;, from "
                      "<a href=\"https://www.openstreetmap.org/%s\">%s</a>.%s</p>"
                      % (n(int(b["area_m2"])), E(b["osm"]), E(b["osm"]),
                         " Addressed %s." % E(b["addr"]) if b["addr"] else ""))
            lead = "%s licensed businesses stand inside this outline." % n(len(rows))
        else:
            where = ("<p class=\"small\">These licences share one street number. The "
                     "address point the city holds for it does not fall inside any "
                     "building outline, so this page groups by the number rather than "
                     "naming a building for them.</p>")
            lead = "%s licensed businesses are registered at this number." % n(len(rows))
        body = """
<main id="main"><div class="in"><div class="paper">
<h1>%s</h1>
<p class="lede">%s The oldest licence here started in %s.</p>
%s
<h2>Who is here</h2>
<ul class="rows">%s</ul>
%s
<p><a class="btn" href="../">Back to the directory</a>
 <a class="btn" href="../../map/">On the map</a></p>
</div></div></main>
""" % (E(name), lead, year(rows[0]["start"]), where, lines,
       viz.bars(sect.most_common(), "Trades at %s, by the sector of each licence's "
                "NAICS code." % name) if len(sect) > 1 else "")
        write("directory/%s/index.html" % pid,
              head("%s — Pike Place Market" % name,
                   "%s licensed businesses at %s, Pike Place Market Historical District."
                   % (len(rows), name), 2, "directory/") + body + foot(2))
        made += 1
    return made


# ------------------------------------------------------------------ vendors

def vendor_pages() -> int:
    made = 0
    by_lic = {}
    for r in LIC:
        by_lic[r["account"]] = r

    matched = {v["licence"] for v in VEND if v.get("licence")}
    for r in LIC:
        v = next((x for x in VEND if x.get("licence") == r["account"]), None)
        made += _one_vendor(r["trade"] or r["legal"], r, v)
    for v in VEND:
        if v.get("licence"):
            continue
        made += _one_vendor(v["name"], None, v)
    return made


def _one_vendor(name: str, r: dict, v: dict) -> int:
    slug = SLUG_ACCOUNT[r["account"]] if r else SLUG_VENDOR[v["id"]]
    bits = []
    if r:
        b = BY_ID.get(r["place"]) if r["place_kind"] == "building" else None
        bits.append("<p class=\"lede\">Licensed to <b>%s</b> on <b>%s</b> — %s years "
                    "ago — as <b>%s</b>.</p>"
                    % (E(r["legal"]), _pretty(r["start"]), r["years"],
                       E(r["naics_text"] or "an unclassified trade")))
        bits.append("<p>%s%s. %s</p>"
                    % (E(r["address"]), " unit %s" % E(r["unit"]) if r["unit"] else "",
                       "In <a href=\"../../directory/%s/\">%s</a>." % (b["id"], E(b["name"]))
                       if b else
                       ("Grouped under <a href=\"../../directory/%s/\">%s</a>, a street "
                        "number several businesses share." % (r["place"], E(PLACE_NAME.get(r["place"], "")))
                        if r["place"] else "Not placed inside any outline.")))
        bits.append('<p><span class="pill">NAICS %s</span>'
                    '<span class="pill">%s</span>'
                    '<span class="pill %s">%s</span></p>'
                    % (E(r["naics"]), E(r["sector"]),
                       "gold" if r["years"] >= 40 else "",
                       "%s years" % int(r["years"])))
    if v:
        if v.get("blurb"):
            bits.append('<blockquote>%s</blockquote>'
                        '<p class="small">The Market\'s own description, quoted as '
                        'published.</p>' % E(v["blurb"]))
        if v.get("cats"):
            bits.append('<p>%s</p>' % "".join(
                '<span class="pill">%s</span>' % E(c) for c in v["cats"]))
        if v.get("address") and not r:
            bits.append('<p>%s%s</p>'
                        % (E(v["address"]),
                           ", inside the district" if v.get("inside") else ""))
        pg = v.get("_page") or {}
        links = [u for u in (pg.get("sites") or []) if u.startswith("http")]
        row = ['<a href="%s">The Market\'s page</a>' % E(v["link"])]
        row += ['<a href="%s" rel="nofollow">%s</a>' % (E(u), E(re.sub(r"^https?://(www\.)?", "", u)[:40]))
                for u in links[:3]]
        bits.append("<p>%s</p>" % " · ".join(row))
    if r and not v:
        bits.append('<p class="small">Not on the Market\'s published vendor roster on '
                    'the day it was read.</p>')
    if v and not r:
        bits.append('<p class="small">No city business licence matched this name at a '
                    'market address. Daystall craftspeople and farmers trade under the '
                    "Market's own permits, which the city's licence file does not carry.</p>")

    desc = ("%s at Pike Place Market%s" %
            (name, (", licensed since %s" % year(r["start"])) if r else ""))
    ld = {"@context": "https://schema.org", "@type": "LocalBusiness", "name": name,
          "address": {"@type": "PostalAddress", "addressLocality": "Seattle",
                      "addressRegion": "WA", "postalCode": "98101",
                      "streetAddress": (r["address"] if r else "Pike Place Market")}}
    if r:
        ld["geo"] = {"@type": "GeoCoordinates", "latitude": r["lat"], "longitude": r["lon"]}
    body = """
<main id="main"><div class="in"><div class="paper">
<h1>%s</h1>
%s
<p><a class="btn" href="../../map/">Find it on the map</a>
 <a class="btn" href="../../directory/">The directory</a></p>
</div></div></main>
""" % (E(name), "".join(bits))
    write("vendor/%s/index.html" % slug,
          head("%s — Pike Place Market" % name, desc, 2, "directory/", jsonld(ld))
          + body + foot(2))
    return 1


def category_pages() -> int:
    made = 0
    by_cat = collections.defaultdict(list)
    for v in VEND:
        for c in v.get("cats", []):
            by_cat[c].append(v)
    for c in CATS:
        rows = by_cat.get(c["name"]) or []
        if not rows:
            continue
        rows.sort(key=lambda v: v["name"])
        lis = "".join(
            '<li><span class="nm"><a href="../../vendor/%s/">%s</a>'
            '<span class="meta">%s</span></span><span class="yr">%s</span></li>'
            % (SLUG_VENDOR[v["id"]],
               E(v["name"]), E((v.get("blurb") or "")[:130]),
               year(v.get("start")) if v.get("start") else "")
            for v in rows)
        body = """
<main id="main"><div class="in"><div class="paper">
<h1>%s</h1>
<p class="lede">%s vendors on the Market's roster carry this category. %s of them also
 hold a city business licence at a market address.</p>
<ul class="rows">%s</ul>
<p><a class="btn" href="../../directory/">Every category</a></p>
</div></div></main>
""" % (E(c["name"]), n(len(rows)), n(sum(1 for v in rows if v.get("licence"))), lis)
        write("category/%s/index.html" % c["slug"],
              head("%s — Pike Place Market" % c["name"],
                   "%s Pike Place Market vendors in %s." % (len(rows), c["name"]),
                   2, "directory/") + body + foot(2))
        made += 1
    return made


# ------------------------------------------------------------------ trades

def trades() -> str:
    L = A["licences"]
    per_sector = collections.defaultdict(list)
    for r in LIC:
        per_sector[r["sector"]].append(r)
    lis = "".join('<li><a href="%s/"><b>%s</b></a> <span class="c">(%d)</span></li>'
                  % (slugify(s), E(s), len(v))
                  for s, v in sorted(per_sector.items(), key=lambda kv: -len(kv[1])))
    body = """
<main id="main"><div class="in"><div class="paper">
<h1>Trades</h1>
<p class="lede">Each licence carries a NAICS code — the census classification the city
 records when a business registers. It is what the business said it does, once, on the
 day it registered, and nothing updates it.</p>
%s
<ul class="yahoo">%s</ul>
<h2>The codes themselves</h2>
%s
</div></div></main>
""" % (viz.bars(L["sectors"], "Licensed businesses inside the district by NAICS sector."),
       lis,
       table(["Trade, as the code names it", "Count"],
             [[E(k), '<span class="num">%d</span>' % v] for k, v in L["trades"]], "n"))
    return (head("Trades — Pike Place Market",
                 "What the businesses inside the Pike Place Market Historical District "
                 "are registered as doing, by NAICS code.", 1, "trades/") + body + foot(1))


def trade_pages() -> int:
    per = collections.defaultdict(list)
    for r in LIC:
        per[r["sector"]].append(r)
    for s, rows in per.items():
        rows.sort(key=lambda r: r["start"] or "9")
        lis = "".join(
            '<li><span class="nm"><a href="../../vendor/%s/">%s</a>'
            '<span class="meta">%s · %s</span></span><span class="yr">%s</span></li>'
            % (SLUG_ACCOUNT[r["account"]],
               E(r["trade"] or r["legal"]), E(r["naics_text"] or ""), E(r["address"]),
               year(r["start"]))
            for r in rows)
        kinds = collections.Counter(r["naics_text"] for r in rows)
        body = """
<main id="main"><div class="in"><div class="paper">
<h1>%s</h1>
<p class="lede">%s licensed businesses inside the district. The oldest started in %s.</p>
<ul class="rows">%s</ul>
%s
<p><a class="btn" href="../">Every trade</a></p>
</div></div></main>
""" % (E(s), n(len(rows)), year(rows[0]["start"]), lis,
       viz.bars(kinds.most_common(12), "The codes inside %s." % s) if len(kinds) > 1 else "")
        write("trades/%s/index.html" % slugify(s),
              head("%s — Pike Place Market" % s,
                   "%s businesses registered under %s inside the Pike Place Market "
                   "Historical District." % (len(rows), s), 2, "trades/") + body + foot(2))
    return len(per)


# ------------------------------------------------------------------ age

def age_page() -> str:
    L = A["licences"]
    t, tn = L["tenure_in"], L["tenure_near"]
    ys = sorted((r["years"] for r in LIC), reverse=True)
    oldest = "".join(
        '<li><span class="nm"><a href="../vendor/%s/">%s</a>'
        '<span class="meta">%s · %s</span></span><span class="yr">%s</span></li>'
        % (_oldest_slug(o["name"]), E(o["name"]),
           E(o["trade"] or ""), E(o["address"]), year(o["start"]))
        for o in L["oldest"])
    years = sorted(L["by_year"].items())
    body = """
<main id="main"><div class="in"><div class="paper">
<h1>Age</h1>
<p class="lede">The city's licence file carries a start date. Inside the district the
 median business has held the same licence for <b class="num">%s years</b>; %s of %s
 are past twenty, %s are past forty, and %s started in the last five.</p>

%s

<h2>Inside the line, and just outside it</h2>
<p>The same measure for the %s licensed businesses within a hundred and fifty metres of
 the boundary and outside it: a median of <b class="num">%s years</b>, %s past twenty,
 %s past forty.</p>
%s
<p class="small">Both columns count active licences only. A business that closed leaves
 the file, so neither column is a survival rate — it is the age of what is standing.</p>

<h2>When they started</h2>
%s
%s

<h2>The oldest sixteen</h2>
<ul class="rows">%s</ul>
</div></div></main>
""" % (t["median"], n(t["over_20"]), n(t["n"]), t["over_40"], t["under_5"],
       viz.dots(ys, "One dot per licensed business inside the district, stacked by "
                    "five-year band of how long the licence has run."),
       n(tn["n"]), tn["median"], tn["over_20"], tn["over_40"],
       viz.paired(_shares(t, tn),
                  "Inside the historical district (%s licences) against licensed "
                  "businesses within 150 m of it and outside (%s); the three shares are "
                  "percentages of each group." % (n(t["n"]), n(tn["n"])),
                  "inside", "outside, within 150 m"),
       viz.columns([(k, v) for k, v in sorted(L["decades"].items())],
                   "Licences still active, by the decade they started."),
       viz.columns([(str(y), c) for y, c in years],
                   "Licences still active, by the year they started. The shape is the "
                   "product of two things at once — how many opened, and how many of "
                   "those are still trading."),
       oldest)
    return (head("Age — Pike Place Market",
                 "How long businesses inside the Pike Place Market Historical District "
                 "have held the same licence, against the blocks just outside it.",
                 1, "age/") + body + foot(1))


def _oldest_slug(name: str) -> str:
    r = next((x for x in LIC if (x["trade"] or x["legal"]) == name), None)
    return SLUG_ACCOUNT[r["account"]] if r else ""


# ------------------------------------------------------------------ the fence

def fence_page() -> str:
    f, ac = A["fence"], A["acres"]
    g = jload(DATA / "geo" / "fence.geojson")["geometry"]
    counts = A["gis"]
    rows = [[E(k), '<span class="num">%s</span>' % n(v["in_fence"]),
             '<span class="num">%s</span>' % n(v["in_box"])]
            for k, v in counts.items() if v]
    body = """
<main id="main"><div class="in"><div class="paper">
<h1>The line</h1>
<p class="lede">The Pike Place Market Historical District is a polygon with %s corners,
 %s acres of area and %s metres of edge, drawn by %s and published by the city as
 overlay code PP in its zoning overlay layer. Every count on this site is that polygon
 answering yes or no.</p>

%s

<h2>Nine acres or thirteen</h2>
<p>The Market's own visitor page describes a <b>%s Market</b>. The city's district
 measures <b class="num">%s</b> acres. The difference, <b class="num">%s</b> acres, is
 the part of the district the Preservation and Development Authority does not run:
 privately owned buildings on First Avenue, Post Alley and Western Avenue that sit
 inside the historic boundary and answer to its rules without being the Market.</p>
<p>A reader asking "how big is Pike Place Market" gets a different number depending on
 which body is answering, and both are right about their own question.</p>

<h2>What the boundary contains</h2>
%s
<p class="small">The box is a rectangle larger than the district, from %s to %s in
 latitude and %s to %s in longitude. A thing counted "in the box" and not "in the fence"
 is a near miss, and the near misses are what make an edge visible.</p>

<h2>How a point is decided</h2>
<p>A business licence carries a street address and no coordinate. The address is
 normalised, matched against the city's Master Address File, and the resulting point is
 tested against the polygon by ray casting. %s of %s inside the line matched an exact
 house number; %s matched the nearest number on the same street, within six doors, and
 are marked as such wherever they appear. %s licences on the market's streets could not
 be placed at all and are counted nowhere.</p>
</div></div></main>
""" % (f["vertices"], ac["district"], n(int(f["perimeter_m"])), E(f["chapter"]),
       viz.fence_plan(g, B, "The district as the city draws it, with every building "
                            "outline OpenStreetMap holds inside it."),
       E(VISIT.get("self_description", "")), ac["district"], ac["difference"],
       table(["Layer", "Inside the line", "In the surrounding box"], rows, "n"),
       f["bbox"][1], f["bbox"][3], f["bbox"][0], f["bbox"][2],
       n(A["licences"]["inside"] - A["licences"]["nearest_matched"]),
       n(A["licences"]["inside"]), A["licences"]["nearest_matched"],
       n(A["licences"]["unplaced"]))
    return (head("The line — Pike Place Market Historical District",
                 "The boundary this site is built on: %s acres, %s corners, and what "
                 "falls inside it." % (ac["district"], f["vertices"]),
                 1, "fence/") + body + foot(1))


# ------------------------------------------------------------------ Daniel

def daniel_page() -> str:
    d = A["daniel"]
    dr = next((r for r in LIC if "FLEMING" in (r["legal"] or "").upper()), {})
    b = BY_ID.get(dr.get("place")) if dr.get("place_kind") == "building" else None
    cats = "".join('<span class="pill">%s</span>' % E(c) for c in d["pda_cats"])
    v = next((x for x in VEND if x["slug"] == "isellpictures-com"), {})
    pg = v.get("_page") or {}
    sites = [u for u in (pg.get("sites") or []) if "isellpictures" in u.lower()]
    pic = shot("../map/", "daniel", "The scenes he sells", 1, "on the map")
    body = """
<main id="main"><div class="in"><div class="paper">
<h1>Daniel T. Fleming</h1>
<div class="two"><div>
<blockquote class="lede">%s</blockquote>
<p class="small">The Market's own description of the business, quoted as published.</p>
</div><div>%s</div></div>

<h2>What the records say</h2>
<p>The City of Seattle licensed <b>%s</b> to <b>%s</b> on <b>%s</b>, at %s. That licence
 has run <b class="num">%s years</b>, which makes his the <b>%s-oldest</b> of the %s
 licences trading inside the district today.</p>
<p>The Market's own roster says the business has sold here <b>since %s</b>. Asked in
 May 2024, he said eighteen years, which points back to %s. Three records, two dates,
 one stall — and the licence is the one with a day on it.</p>
%s

<h2>Where he stands</h2>
<p>%s Category on the Market's roster:</p>
<p>%s</p>
<p class="small">The Crafts Market is the daystall system: a table rented by the day,
 assigned by seniority, under the Market's own rules rather than a shop lease. %s of the
 %s vendors on the Market's roster hold no separate city licence at a market address;
 his is one of the %s that do.</p>

<p><a class="btn solid" href="%s">isellpictures.com</a>
 <a class="btn" href="%s">His page on the Market's site</a>
 <a class="btn" href="../map/">Find the stall</a></p>
</div></div></main>
""" % (E(d["pda_blurb"] or ""), pic,
       E(d["trade_name"]), E(d["licence_name"]), _pretty(d["licence_start"]),
       E(d["licence_address"]), d["licence_years"],
       _rank_phrase(d["licence_years"]), n(A["licences"]["inside"]),
       d["pda_says_since"], int(str(d["licence_start"])[:4]),
       viz.columns([(str(y), c) for y, c in sorted(A["licences"]["by_year"].items())],
                   "Every active licence inside the district by its start year. His is "
                   "in %s." % str(d["licence_start"])[:4],
                   mark={"2006": _year_index(int(str(d["licence_start"])[:4]))}),
       ("Inside <a href=\"../directory/%s/\">%s</a>." % (b["id"], E(b["name"])) if b
        else ("Registered at <a href=\"../directory/%s/\">%s</a>, the street number "
              "%s licensed businesses share — the Market's own front door, and as "
              "precise as the city's record gets for a daystall."
              % (dr.get("place"), E(PLACE_NAME.get(dr.get("place"), "")),
                 n(dict((k, v) for k, v, _nm, _t in PLACES).get(dr.get("place"), 0))))),
       cats,
       n(A["pda"]["unmatched"]), n(A["pda"]["vendors"]), n(A["pda"]["matched_to_licence"]),
       E(sites[0] if sites else "https://isellpictures.com/"),
       E(d["pda_link"] or "https://www.pikeplacemarket.org/vendor/isellpictures-com/"))
    ld = jsonld({"@context": "https://schema.org", "@type": "LocalBusiness",
                 "name": "Isellpictures.com (Fodoughgrafiks)",
                 "founder": {"@type": "Person", "name": "Daniel T. Fleming"},
                 "url": "https://isellpictures.com/",
                 "address": {"@type": "PostalAddress", "streetAddress": d["licence_address"],
                             "addressLocality": "Seattle", "addressRegion": "WA",
                             "postalCode": "98101"}})
    return (head("Daniel T. Fleming — Pike Place Market",
                 "Fodoughgrafiks, isellpictures.com: photographer and digital artist at "
                 "Pike Place Market, licensed since %s." % year(d["licence_start"]),
                 1, "daniel-fleming/", ld) + body + foot(1))


def _rank_phrase(years) -> str:
    ys = sorted((r["years"] for r in LIC), reverse=True)
    rank = sum(1 for y in ys if y > (years or 0)) + 1
    return "%d" % rank + _ordinal(rank)


def _ordinal(k: int) -> str:
    return "th" if 10 < k % 100 < 14 else {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")


def _year_index(y: int) -> int:
    ks = sorted(int(k) for k in A["licences"]["by_year"])
    return ks.index(y) if y in ks else 0


# ------------------------------------------------------------------ sources

def sources() -> str:
    rows = []
    for p in sorted(HARVEST.glob("*.json")):
        d = jload(p) or {}
        rows.append([E(p.name),
                     E(d.get("source", "")),
                     E(d.get("licence", ""))[:110],
                     '<span class="num">%s</span>' % n(d.get("count", len(d.get("rows", [])))),
                     E((d.get("fetched") or "")[:16].replace("T", " "))])
    body = """
<main id="main"><div class="in"><div class="paper">
<h1>Sources</h1>
<p class="lede">Every file this site is built from, what it came from, under what
 licence, and the hour it was read. A harvest file is never a record: it keeps its own
 provenance, so an absence reads as "not in that source on that date".</p>
%s
<h2>The four bodies that describe this place</h2>
<ul>
 <li><b>The City of Seattle</b> draws the historical district boundary (Land Use Code
  chapter 25.24, overlay PP) and publishes the business licence file, the Master Address
  File, building outlines, public art, trees and kerb space as open data.</li>
 <li><b>The Pike Place Market Preservation and Development Authority</b> runs the Market
  and publishes its own vendor roster, its categories and its hours. Its robots.txt
  permits this and asks ten seconds between requests, which is what the crawler waits.</li>
 <li><b>OpenStreetMap contributors</b> mapped the buildings, the arcades, the stairs and
  a few hundred of the shops. ODbL 1.0, share-alike, attributed on every map.</li>
 <li><b>Wikimedia Commons</b> holds the photographs. The harvester takes CC0, public
  domain, CC BY, CC BY-SA and Free Art Licence files and lists the rest without taking
  them; a picture's author and licence print beside it.</li>
</ul>
<h2>What the Market publishes about its hours</h2>
<p>Quoted from its visitor page, read %s. Most of the Market is active from
 <b>%s</b>; it trades seven days a week, closed on <b>%s</b>.</p>
%s
<p><a class="btn" href="../api/">The data files</a></p>
</div></div></main>
""" % (table(["File", "Source", "Licence", "Rows", "Read (UTC)"], rows, "n"),
       E(VISIT.get("fetched", "")[:10]), E(VISIT.get("active_band", "")),
       E(VISIT.get("closed_days", "")),
       table(["What", "When"],
             [[E(h["what"]), E(h["when"])] for h in VISIT.get("hours", [])]))
    return (head("Sources — Pike Place Market",
                 "Every dataset behind this site, its licence, and the hour it was read.",
                 1, "sources/") + body + foot(1))


def api_page() -> str:
    files = sorted((DOCS / "data").glob("*.geojson"))
    rows = [[('<a href="../data/%s">%s</a>' % (E(p.name), E(p.name))),
             '<span class="num">%s kB</span>' % n(p.stat().st_size // 1024)]
            for p in files]
    body = """
<main id="main"><div class="in"><div class="paper">
<h1>The data</h1>
<p class="lede">The files the pages are built from. Take them and filter them
 yourself.</p>
%s
<p>The fence is a single GeoJSON feature carrying its area, perimeter, corner count and
 the query that produced it. The vendor points carry the licence start date, the NAICS
 code and whether the address matched exactly or by nearest number.</p>
<p class="lic">Code MIT. Text and figures CC BY 4.0. OpenStreetMap geometry stays under
 ODbL 1.0 and its share-alike terms travel with it. The city's data carries no licence
 assertion. Photographs keep the licence named beside them.</p>
</div></div></main>
""" % table(["File", "Size"], rows, "n")
    return (head("The data — Pike Place Market",
                 "GeoJSON and JSON behind the Pike Place Market map and directory.",
                 1, "api/") + body + foot(1))
