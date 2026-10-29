import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import mapcells  # noqa: E402
import mapdata  # noqa: E402


class FakeOsm:
    """osmfuel.OsmFuel's cell(), counting its calls."""

    def __init__(self, rows):
        self.rows, self.calls = rows, 0

    def cell(self, bounds, kind="demand"):
        self.calls += 1
        return self.rows


class OsmFuelCacheTest(unittest.TestCase):
    """(the OSM test, 2026-10-28: "lets test OSM if it is too laggy we will revert") MapData keeps each cell's
    OpenStreetMap fuel stations on disk: the road tiles' workers only read it (osm_fuel_cached, None when not fetched
    yet: never waited for), the server fetches it in the background (osm_fuel_fetch)."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.md = mapdata.MapData(self.dir, fetcher=object())
        self.key = next(iter(mapcells.cells_for_bbox(40.44, -80.0, 40.441, -79.999)))
        self.rows = [{"id": 7, "brand": "Shell", "name": "Shell", "building": "roof", "bbox": (-80.0, 40.44, -79.9999, 40.4401)}]

    def test_fetch_then_cached(self):
        self.md.osmfuel = FakeOsm(self.rows)
        self.assertIsNone(self.md.osm_fuel_cached(self.key), "not fetched yet")
        self.assertEqual(self.md.osm_fuel_fetch(self.key), self.rows)
        got = self.md.osm_fuel_cached(self.key)
        self.assertEqual(got, self.rows)
        self.assertIsInstance(got[0]["bbox"], tuple)
        # another process (a road tile's worker) reads the same file
        other = mapdata.MapData(self.dir, fetcher=object())
        self.assertEqual(other.osm_fuel_cached(self.key), self.rows)
        # a cell with none is kept too (not asked again)
        empty = next(iter(mapcells.cells_for_bbox(41.0, -80.0, 41.001, -79.999)))
        self.md.osmfuel = FakeOsm([])
        self.assertEqual(self.md.osm_fuel_fetch(empty), [])
        self.assertEqual(self.md.osm_fuel_cached(empty), [])

    def test_off(self):
        self.md.osmfuel = FakeOsm(self.rows)
        self.md.osm_fuel_fetch(self.key)
        old = mapdata.OSM_FUEL
        mapdata.OSM_FUEL = False
        try:
            self.assertIsNone(self.md.osm_fuel_cached(self.key), "BNGE_OSM_FUEL=0: as without OSM")
            self.assertEqual(self.md.osm_fuel_fetch(self.key), [])
        finally:
            mapdata.OSM_FUEL = old


if __name__ == "__main__":
    unittest.main()
