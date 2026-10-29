import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import geodesy  # noqa: E402
import mapcells  # noqa: E402
import roads  # noqa: E402


class OsmFuelTilesTest(unittest.TestCase):
    """(the OSM test, 2026-10-28) a cell's OpenStreetMap fuel stations fetched after its road tiles were sent: those
    tiles (the ones whose stations reach the cell) are built again; the others stay."""

    def test_tiles_of_cell(self):
        import earthd
        frame = geodesy.EnuFrame(40.44, -80.0)
        key = next(iter(mapcells.cells_for_bbox(40.44, -80.0, 40.4401, -79.9999)))
        near = earthd.osm_fuel_tiles(frame, key, {(0, 0), (-1, -1), (40, 40)})
        self.assertIn((0, 0), near)
        self.assertNotIn((40, 40), near, "10 km off")

    def test_tracker_again(self):
        t = roads.Tracker()
        t.sent = {(0, 0), (1, 0), (5, 5)}
        t.again({(0, 0), (9, 9)})
        self.assertEqual(t.sent, {(1, 0), (5, 5)}, "built again at the next pose (no roads_drop: the mod replaces it)")


if __name__ == "__main__":
    unittest.main()
