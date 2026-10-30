import sys, os, math
sys.path.insert(0, sys.argv[1])
import numpy as np, geodesy, mapdata, netfetch, overture, gasstations as gs
md = mapdata.MapData("G:/BeamNGEarthCache", netfetch.Fetcher(stats_dir=os.path.join("G:/BeamNGEarthCache", "netstats")), overture.RELEASE)
_r = (lambda s: gs.reach_of(s)) if hasattr(gs, 'reach_of') else (lambda s: gs.REACH_M)
AREAS = [("Tokyo", 35.6812, 139.7671, 1500), ("Osaka", 34.6937, 135.5023, 1500), ("Sydney", -33.8688, 151.2093, 1500),
 ("Melbourne", -37.8136, 144.9631, 1500), ("Auckland", -36.8485, 174.7633, 1500), ("Toronto", 43.6532, -79.3832, 1500),
 ("Montreal", 45.5019, -73.5674, 1500), ("London", 51.5074, -0.1278, 1500), ("Paris", 48.8566, 2.3522, 1500),
 ("Berlin", 52.52, 13.405, 1500), ("Madrid", 40.4168, -3.7038, 1500), ("Rome", 41.9028, 12.4964, 1500),
 ("Warsaw", 52.2297, 21.0122, 1500), ("MexicoCity", 19.4326, -99.1332, 1500), ("SaoPaulo", -23.5505, -46.6333, 1500),
 ("BuenosAires", -34.6037, -58.3816, 1500), ("Johannesburg", -26.2041, 28.0473, 1500), ("Cairo", 30.0444, 31.2357, 1500),
 ("Dubai", 25.2048, 55.2708, 1500), ("Mumbai", 19.076, 72.8777, 1500), ("Bangkok", 13.7563, 100.5018, 1500),
 ("Houston", 29.7604, -95.3698, 1500), ("LosAngeles", 34.0522, -118.2437, 1500), ("Chicago", 41.8781, -87.6298, 1500),
 ("Atlanta", 33.749, -84.388, 1500), ("Denver", 39.7392, -104.9903, 1500), ("AmesIowa", 42.0308, -93.6319, 2500),
 ("Reykjavik", 64.1466, -21.9426, 1500), ("Nairobi", -1.2921, 36.8219, 1500), ("Istanbul", 41.0082, 28.9784, 1500),
 ("Nagoya", 35.1815, 136.9066, 2500), ("Sapporo", 43.0618, 141.3545, 2500), ("Fukuoka", 33.5902, 130.4017, 2500), ("Tsukuba", 36.0835, 140.0764, 3000),
 ("Moscow", 55.7558, 37.6173, 3000), ("StPetersburg", 59.9343, 30.3351, 3000), ("Kazan", 55.7963, 49.1088, 2500), ("Novosibirsk", 55.0084, 82.9357, 2500),
 ("Yekaterinburg", 56.8389, 60.6057, 2500), ("Kyiv", 50.4501, 30.5234, 2500), ("Minsk", 53.9006, 27.5590, 2500), ("Prague", 50.0755, 14.4378, 2500),
 ("Vienna", 48.2082, 16.3738, 2500), ("Budapest", 47.4979, 19.0402, 2500), ("Bucharest", 44.4268, 26.1025, 2500), ("Athens", 37.9838, 23.7275, 2500),
 ("Stockholm", 59.3293, 18.0686, 2500), ("Oslo", 59.9139, 10.7522, 2500), ("Helsinki", 60.1699, 24.9384, 2500), ("Copenhagen", 55.6761, 12.5683, 2500),
 ("Amsterdam", 52.3676, 4.9041, 2500), ("Lisbon", 38.7223, -9.1393, 2500), ("Milan", 45.4642, 9.1900, 2500), ("Lyon", 45.7640, 4.8357, 2500)]
for name, lat, lon, R in AREAS:
  try:
      frame = geodesy.EnuFrame(lat, lon)
      pl = [md.cell(k, layers=("places",), kind="demand").layers.get("places") for k in gs._cells_near(frame, 0, 0, R)]
      for s in sorted(gs.merge(gs.pins(frame, pl)), key=lambda s: s.id):
          if math.hypot(s.x, s.y) > R: continue
          la, lo, _ = frame.enu_to_geodetic(s.x, s.y, 0.0)
          cds = [md.cell(k, layers=("buildings","roads"), kind="demand") for k in gs._cells_near(frame, s.x, s.y, _r(s))]
          rls = [c.layers.get("roads") for c in cds]
          site = gs.layout(s, gs.buildings_near(frame, [c.layers.get("buildings") for c in cds], s.x, s.y, _r(s)),
                           gs.drive_lines(frame, rls, s.x, s.y, _r(s) + 50), gs.service_lines(frame, rls, s.x, s.y, _r(s)), gs.style_of(float(la), float(lo)))
          out = "none" if site is None else f"{len(site.props)} props {len(site.areas)} pumps drop={sorted(d[:8] for d in site.drop_ids)} shop={site.shop_id[:13]}"
          print(f"{name} | {s.name} {float(la):.5f},{float(lo):.5f} | {out}", flush=True)

  except Exception as e:
    print(f'{name} | ERROR {e!r}', flush=True)