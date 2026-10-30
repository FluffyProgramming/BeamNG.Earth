"""Why chargers are skipped: per skipped site, the nearest public road's edge distance, inside a building, buildings
within 10 m. python ev_why.py <server dir>"""
import sys, os, math, collections
sys.path.insert(0, sys.argv[1])
import numpy as np, geodesy, mapdata, netfetch, overture, gasstations as gs, evchargers as ev, polygon
C = "G:/BeamNGEarthCache"
md = mapdata.MapData(C, netfetch.Fetcher(stats_dir=os.path.join(C, "netstats")), overture.RELEASE)
for name, lat, lon, R in [("Denver", 39.7392, -104.9903, 1500), ("LosAngeles", 34.0522, -118.2437, 1500), ("Sydney", -33.8688, 151.2093, 1500)]:
    f = geodesy.EnuFrame(lat, lon)
    keys = gs._cells_near(f, 0, 0, R + 200)
    pl = [md.cell(k, layers=("places",), kind="demand").layers.get("places") for k in keys]
    osm = [md.osm_fuel_cached(k) for k in keys]
    chs = [c for c in ev.merge(ev.charger_pins(f, pl), gs._osm_points(f, osm, amenity="charging_station")) if math.hypot(c.x, c.y) <= R]
    why = collections.Counter(); edge = []
    for ch in chs:
        if gs._charger_site(f, md, ch, []) is not None:
            continue
        r = ev.reach_of(ch)
        cds = [md.cell(k, layers=("buildings", "roads"), kind="demand") for k in gs._cells_near(f, ch.x, ch.y, r)]
        rls = [c.layers.get("roads") for c in cds]
        blds = gs.buildings_near(f, [c.layers.get("buildings") for c in cds], ch.x, ch.y, r)
        roads = gs.drive_lines(f, rls, ch.x, ch.y, r + 50)
        p = np.array([[ch.x, ch.y]])
        d = min((gs._seg_dist(p, l[:-1], l[1:])[0] - h for l, h in roads), default=99)
        inside = any(polygon.contains_points(b.ring, p).any() for b in blds)
        near_b = sum(1 for b in blds if gs._seg_dist(p, b.ring[:-1], b.ring[1:])[0] < 10)
        edge.append(d)
        print("   ", ch.name or "-", round(d, 1), "m from road edge, inside" if inside else "", near_b, "buildings within 10 m", flush=True)
        why["inside a building" if inside else "road edge < 3 m" if d < 3 else "road edge 3-9 m" if d < 9 else "other"] += 1
    print(name, len(chs), "skipped by reason:", dict(why), "| road-edge distance quartiles:", np.round(np.percentile(edge, [25, 50, 75]), 1) if edge else "-", flush=True)
