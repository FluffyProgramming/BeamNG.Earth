"""EV chargers in the 8 recon places (both sources): sites, big/small, laid out / skipped, beside a station, chargers
placed, layout ms per site. python ev_sample.py <server dir>"""
import sys, os, math, time, collections
sys.path.insert(0, sys.argv[1])
import numpy as np, geodesy, mapdata, netfetch, overture, gasstations as gs, evchargers as ev
C = "G:/BeamNGEarthCache"
md = mapdata.MapData(C, netfetch.Fetcher(stats_dir=os.path.join(C, "netstats")), overture.RELEASE)
AREAS = [("Denver", 39.7392, -104.9903, 1500), ("LosAngeles", 34.0522, -118.2437, 1500), ("Utrecht", 52.0907, 5.1214, 1500),
         ("Oslo", 59.9139, 10.7522, 1500), ("Berlin", 52.52, 13.405, 1500), ("Tokyo", 35.6812, 139.7671, 1500),
         ("SaoPaulo", -23.5505, -46.6333, 1500), ("Sydney", -33.8688, 151.2093, 1500)]
tot = collections.Counter()
for name, lat, lon, R in AREAS:
    f = geodesy.EnuFrame(lat, lon)
    keys = gs._cells_near(f, 0, 0, R + 200)
    pl = [md.cell(k, layers=("places",), kind="demand").layers.get("places") for k in keys]
    osm = []
    for k in keys:
        rows = md.osm_fuel_cached(k)
        if rows is None:
            rows = md.osm_fuel_fetch(k, kind="demand")
        osm.append(rows)
    stations = gs.with_osm(gs.merge(gs.pins(f, pl)), gs._osm_points(f, osm))
    sites = []
    for s in stations:
        if math.hypot(s.x, s.y) > R + 200:
            continue
        r = gs.reach_of(s)
        cds = [md.cell(k, layers=("buildings", "roads"), kind="demand") for k in gs._cells_near(f, s.x, s.y, r)]
        rls = [c.layers.get("roads") for c in cds]
        la, lo, _ = f.enu_to_geodetic(s.x, s.y, 0.0)
        site = gs.layout(s, gs.buildings_near(f, [c.layers.get("buildings") for c in cds], s.x, s.y, r),
                         gs.drive_lines(f, rls, s.x, s.y, r + 50), gs.service_lines(f, rls, s.x, s.y, r),
                         gs.style_of(float(la), float(lo)))
        if site is not None:
            sites.append(site)
    kept = list(gs._one_per_shop(sites))
    chs = [c for c in ev.merge(ev.charger_pins(f, pl), gs._osm_points(f, osm, amenity="charging_station"))
           if math.hypot(c.x, c.y) <= R]
    c = collections.Counter(); ms = []
    for ch in chs:
        t0 = time.perf_counter()
        site = gs._charger_site(f, md, ch, kept)
        ms.append((time.perf_counter() - t0) * 1000)
        c["sites"] += 1; c["big"] += ch.big; c["tesla"] += ch.tesla
        c["beside"] += gs._beside_station(ch, kept) is not None
        if site is None:
            c["skipped"] += 1
        else:
            c["laid"] += 1; c["chargers"] += len(site.props)
    tot.update(c)
    print(f"{name}: sites {c['sites']} (big {c['big']}, tesla {c['tesla']}, by a station {c['beside']}), laid out "
          f"{c['laid']}, skipped {c['skipped']}, chargers {c['chargers']}; layout ms mean "
          f"{np.mean(ms) if ms else 0:.1f} max {max(ms) if ms else 0:.1f}", flush=True)
print("ALL:", dict(tot))
