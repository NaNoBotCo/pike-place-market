# -*- coding: utf-8 -*-
"""test_site.py — the gates. Run after a build; a red one keeps the site on this disk.

  python3 tests/test_site.py
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from common import DATA, DOCS, fence, pt_in_poly, poly_area_m2   # noqa: E402

A = json.loads((DATA / "analysis.json").read_text())
D = json.loads((DATA / "directory.json").read_text())
PAGES = sorted(DOCS.rglob("*.html"))


class Fence(unittest.TestCase):
    def test_area_matches_the_published_figure(self):
        g = fence()["geometry"]
        acres = poly_area_m2(g["coordinates"], g["type"]) / 4046.8564224
        self.assertAlmostEqual(acres, A["acres"]["district"], places=2)

    def test_every_inside_licence_is_inside(self):
        g = fence()["geometry"]
        for r in D["licences"]:
            self.assertTrue(pt_in_poly((r["lon"], r["lat"]), g),
                            "%s is in the directory but outside the polygon" % r["trade"])

    def test_no_near_miss_is_inside(self):
        g = fence()["geometry"]
        for r in D["near_misses"]:
            self.assertFalse(pt_in_poly((r["lon"], r["lat"]), g), r["trade"])

    def test_near_misses_are_within_the_stated_distance(self):
        for r in D["near_misses"]:
            self.assertLessEqual(r["edge_m"], 150.0, r["trade"])


class Places(unittest.TestCase):
    def test_a_building_place_means_the_point_is_inside_the_outline(self):
        for r in D["licences"]:
            if r["place_kind"] == "building":
                self.assertEqual(r["building_how"], "within", r["trade"])

    def test_an_address_place_names_no_building(self):
        for r in D["licences"]:
            if r["place_kind"] == "address":
                self.assertIsNone(r["building"], r["trade"])

    def test_every_licence_lands_somewhere(self):
        self.assertEqual(sum(v for _k, v, _n, _t in A["per_place"]),
                         A["licences"]["inside"])


class Numbers(unittest.TestCase):
    def test_tenure_counts_do_not_exceed_the_group(self):
        for key in ("tenure_in", "tenure_near"):
            t = A["licences"][key]
            self.assertLessEqual(t["over_40"], t["over_20"])
            self.assertLessEqual(t["over_20"], t["n"])

    def test_the_decades_sum_to_the_count(self):
        self.assertEqual(sum(A["licences"]["decades"].values()), A["licences"]["inside"])

    def test_the_acreage_difference_is_arithmetic(self):
        ac = A["acres"]
        self.assertAlmostEqual(ac["district"] - ac["market_says"], ac["difference"], places=2)

    def test_the_figures_on_the_front_page_are_the_figures_in_the_data(self):
        html = (DOCS / "index.html").read_text()
        self.assertIn(str(A["acres"]["district"]), html)
        self.assertIn(str(A["licences"]["inside"]), html)
        self.assertIn("{:,}".format(A["pda"]["vendors"]), html)


class Links(unittest.TestCase):
    def test_every_internal_link_resolves(self):
        bad = []
        for p in PAGES:
            base = p.parent
            # an href built inside a popup template is a string, not a link
            body = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", p.read_text())
            for href in re.findall(r'href="([^"#?]+)"', body):
                if href.startswith(("http", "mailto:", "//", "/")):
                    continue
                t = (base / href).resolve()
                if t.is_dir():
                    t = t / "index.html"
                if t.suffix == "":
                    t = t / "index.html"
                if not t.exists():
                    bad.append("%s -> %s" % (p.relative_to(DOCS), href))
        self.assertEqual(bad[:12], [], "%d dead links" % len(bad))

    def test_every_page_is_in_the_sitemap(self):
        sm = (DOCS / "sitemap.xml").read_text()
        for p in PAGES:
            rel = p.relative_to(DOCS).as_posix()
            if rel == "404.html":
                continue
            self.assertIn(rel.replace("index.html", ""), sm, rel)


class Pictures(unittest.TestCase):
    def test_every_picture_shipped_carries_a_licence_and_a_source(self):
        idx = json.loads((DATA / "images" / "index.json").read_text())["images"]
        for key, im in idx.items():
            self.assertTrue(im.get("licence"), key)
            self.assertTrue(im.get("page"), key)
            self.assertTrue(im["free"], "%s is not a free licence" % key)

    def test_a_picture_with_no_author_says_so_rather_than_going_blank(self):
        """One of the 1907 photographs reaches Commons with an empty Artist field. The
        credit prints that the file names nobody, instead of an empty byline."""
        sys.path.insert(0, str(ROOT / "tools"))
        import shell
        for key, im in shell.IMAGES.items():
            line = shell.credit(key)
            self.assertIn("commons.wikimedia.org", line, key)
            if not im.get("author"):
                self.assertIn("no author named", line, key)

    def test_a_picture_on_a_page_is_named_beside_it(self):
        html = (DOCS / "directory" / "index.html").read_text()
        for m in re.findall(r'class="bg" style="background-image:url\(([^)]+)\)', html):
            self.assertIn("commons.wikimedia.org", html)


class Contrast(unittest.TestCase):
    """No word sits on a photograph. The plate carries the contrast, so legibility can
    be computed from the stylesheet rather than trusted to whichever frame the page
    drew."""

    @staticmethod
    def _lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def _lum(self, rgb):
        r, g, b = (self._lin(x) for x in rgb)
        return .2126 * r + .7152 * g + .0722 * b

    def _ratio(self, a, b):
        la, lb = self._lum(a), self._lum(b)
        hi, lo = max(la, lb), min(la, lb)
        return (hi + .05) / (lo + .05)

    def test_ink_on_the_plate_over_a_white_photograph(self):
        css = (DOCS / "site.css").read_text()
        plate = re.search(r"--plate:rgba\((\d+),(\d+),(\d+),\.(\d+)\)", css)
        ink = re.search(r"--ink:#([0-9a-f]{6})", css)
        dim = re.search(r"--dim:#([0-9a-f]{6})", css)
        self.assertTrue(plate and ink and dim)
        pr, pg, pb = (int(plate.group(i)) for i in (1, 2, 3))
        alpha = float("0." + plate.group(4))
        worst = tuple(round(p * alpha + 255 * (1 - alpha)) for p in (pr, pg, pb))
        for name, m in (("ink", ink), ("dim", dim)):
            hexs = m.group(1)
            rgb = tuple(int(hexs[i:i + 2], 16) for i in (0, 2, 4))
            r = self._ratio(rgb, worst)
            self.assertGreaterEqual(round(r, 1), 7.0,
                                    "%s on the plate over white is %.1f:1" % (name, r))


class Style(unittest.TestCase):
    def test_the_style_checker_passes(self):
        """Over the code and the pages this site writes. The vendor and category pages
        are excluded because their bodies are the Market's own descriptions, quoted as
        published — a vendor calling its own food authentic is the vendor talking."""
        import subprocess
        check = Path.home() / ".claude" / "bin" / "stylecheck.py"
        if not check.exists():
            self.skipTest("no checker on this machine")
        mine = [p for p in PAGES
                if not p.relative_to(DOCS).as_posix().startswith(("vendor/", "category/"))]
        targets = [str(ROOT / "tools")] + [str(p) for p in mine]
        r = subprocess.run([sys.executable, str(check)] + targets,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
