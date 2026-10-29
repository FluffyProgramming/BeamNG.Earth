"""OpenStreetMap's fuel stations (amenity=fuel) per map cell, from OSM US's Layercake POIs file: the stations Overture's
places do not list (142 of the 600 OSM fuel stations in the 54 test places, 2026-10-28), and a second source for those
it does (the user, 2026-10-28: "lets test OSM if it is too laggy we will revert").
Read as osmtags.py reads the highways file: the pinned version (ETag), the footer once per version, the row groups whose
bbox statistics touch the cell, and only the columns used, through rangeread's block cache; in two steps (the small
columns to find the cell's fuel rows, then names, brand, building and geometry of the row groups that have any).
Unreachable: no OSM stations (the caller goes on with Overture's).
"""
import logging
import struct

import numpy as np

import osmtags
import rangeread

log = logging.getLogger("earthd.osmfuel")

URL = "https://data.openstreetmap.us/layercake/pois.parquet"
PATH = "osm/pois.parquet"
FIND = ("id", "bbox", "amenity")                        # step 1: the cell's fuel rows
DETAIL = ("brand", "name", "building", "geometry")      # step 2: of the row groups that have any


class OsmFuel(osmtags.OsmTags):
    """The amenity=fuel features per map cell, from the pinned Layercake POIs version."""

    DIR = "osmfuel"

    def __init__(self, raw_dir, fetcher, url=URL):
        super().__init__(raw_dir, fetcher, url)

    def cell(self, bounds, kind="demand"):
        """[{"id", "brand", "name", "building", "point": (lon, lat) | None, "ring": (k, 2) lon/lat | None}] of the fuel
        stations whose bbox touches bounds (lon0, lat0, lon1, lat1). A version that changed under the reads is dropped
        and the cell asked once more on the new one."""
        for attempt in (0, 1):
            etag, remote = self.version(kind)
            try:
                return self._fuel(remote, bounds, kind)
            except rangeread.Changed:
                if attempt:
                    raise
                log.info("osmfuel: %s changed (was %s), taking the new version", self.url, etag)
                self._forget()
        return []

    def _fuel(self, remote, bounds, kind):
        lon0, lat0, lon1, lat1 = bounds
        rd = self._reader
        files = {PATH: remote}
        con, proto, errors = rd._connect(files, kind)
        try:
            uri = f"'{proto}://{PATH}'"
            groups = self._groups(con, uri, remote, kind)
            cand = self._candidates(groups, bounds)
            if not cand:
                return []
            rd._fetch(files, {PATH: [r for rg in cand for c in FIND for r in groups[rg]["cols"].get(c, [])]}, kind)
            only = " OR ".join(f"file_row_number BETWEEN {groups[rg]['first']} AND "
                               f"{groups[rg]['first'] + groups[rg]['n'] - 1}" for rg in cand)
            box = (f"bbox.xmin <= {lon1!r} AND bbox.xmax >= {lon0!r} AND bbox.ymin <= {lat1!r} "
                   f"AND bbox.ymax >= {lat0!r}")
            hits = [int(r[0]) for r in con.execute(f"""SELECT file_row_number FROM read_parquet({uri},
                file_row_number = true) WHERE ({only}) AND {box} AND amenity = 'fuel'""").fetchall()]
            if not hits:
                return []
            hit = sorted({rg for r in hits for rg in cand
                          if groups[rg]["first"] <= r < groups[rg]["first"] + groups[rg]["n"]})
            rd._fetch(files, {PATH: [r for rg in hit for c in DETAIL for r in groups[rg]["cols"].get(c, [])]}, kind)
            try:                # (the geometry as its WKB bytes: no spatial extension needed)
                con.execute("SET enable_geoparquet_conversion = false")
            except Exception:
                pass
            rows = con.execute(f"""SELECT id, brand, name, building, geometry FROM read_parquet({uri},
                file_row_number = true) WHERE file_row_number IN ({', '.join(map(str, hits))})""").fetchall()
        except Exception:
            for e in errors:
                if isinstance(e, rangeread.Changed):
                    raise e
            raise
        finally:
            con.close()
        out = []
        for fid, brand, name, building, geom in rows:
            shape = _wkb(bytes(geom)) if geom is not None else None
            if shape is None:
                continue
            if isinstance(name, (list, tuple)):
                name = name[0] if name else None
            out.append({"id": int(fid), "brand": brand or "", "name": name or "", "building": building or "",
                        "point": shape if isinstance(shape, tuple) else None,
                        "ring": shape if isinstance(shape, np.ndarray) else None})
        return out


def _wkb(b):
    """A WKB Point as (lon, lat), a Polygon or MultiPolygon as its (first) outer ring (k, 2); else None."""
    try:
        end = "<" if b[0] == 1 else ">"
        kind = struct.unpack(end + "I", b[1:5])[0] % 1000
        if kind == 1:
            x, y = struct.unpack(end + "dd", b[5:21])
            return (x, y)
        if kind == 3:
            return _ring(b, 5, end)
        if kind == 6:
            return _wkb(b[9:])                          # (its first polygon)
    except (struct.error, IndexError):
        pass
    return None


def _ring(b, o, end):
    nrings = struct.unpack(end + "I", b[o:o + 4])[0]
    if nrings < 1:
        return None
    n = struct.unpack(end + "I", b[o + 4:o + 8])[0]
    return np.frombuffer(b, dtype=np.dtype(end + "f8"), count=2 * n, offset=o + 8).reshape(n, 2).copy()
