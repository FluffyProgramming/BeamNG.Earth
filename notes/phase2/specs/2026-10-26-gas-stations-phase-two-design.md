# Gas stations, phase two: design

Date: 2026-10-26. Status: draft for the user's review. Nothing is built.
Base: upstream `main` at v1.6.3-beta (PR #220 merged; gas stations always on, Tecna's c003c48).

## Intent

Phase one put real stations in the world and made them refuelable. Phase two makes them *findable* and *believable*,
and cleans up the known limits from PR #220. This is a free-roam mod, so there's nothing for career.

The user, 2026-10-26: "Let's plan for everything except lighting (for now) AI traffic and career firm prices, this is
a free roam mod". On finding a station: "I figured I would use the map or in game menu to navigate to nearest gas
station". On the plan: "plan it to the best of your ability keeping in mind performance, deck usage".

## Goals, non-goals, anti-goals

**Goals:**
- From the world map or an in-game menu, a player can route the GPS to the nearest gas station (and to an EV charger).
- Stations are visible on the world map, with their names.
- Stations look more like the real thing: brand colours, price signs, small props, a store at kiosk-only stations.
- EV chargers and truck stops are placed.
- The known limits from PR #220 are fixed: big spawns stutter, re-sent tiles respawn with a flash, there's dirt between
  the pad and the shop, and the Marathon case is skipped.

**Non-goals:**
- Night lighting. Tecna's ROADMAP has "Night lights: lit windows, street lamps", so it waits for his light system and
  the user raises it with him.
- AI traffic using stations.
- Career fuel prices or any economy.
- Real-time fuel prices. There's no free worldwide source, and the shown prices are decoration.

**Anti-goals (a failure even if it works):**
- Any measurable frame cost when driving fast (players drive 150-300 mph, docs/ROADMAP.md) or noticeable extra memory
  on a Steam Deck (small budget, mapdata.MEM_MB = 160).
- Loading another map-data layer into the block processes, or decoding `places` for many cells just to answer
  "nearest station".
- Station props that don't follow PR #220's rules: a car wash must never become a canopy, and nothing is placed where
  data doesn't support it.
- New assets shipped in the mod. Everything comes from stock levels, as in phase one.

## Constraints (measured or found in recon)

- **Data.** Overture places has `basic_category` / `taxonomy` / `brand_name` / `brand_wikidata` / `name` /
  `operating_status`, but no fuel-type fields.
  - `ev_charging_station` exists (31 pins in the Pittsburgh-area, New Braunfels and Utrecht samples).
  - `truck_gas_station` appears in `taxonomy`.
  - OpenStreetMap's `fuel:*`, `hgv`, `socket:*` and `capacity` tags are absent from both Overture and the Layercake
    POIs parquet. So **fuel types from OSM tags cannot be done with the data the server reads today** (see "Dropped").
- **Stock shapes found** (levels zips, 0.40.3):
  - East Coast: `eca_gastation_store`, `eca_gastation_pricedisplay`, `eca_gastation_concretebase`,
    `eca_charging_station`, `garbage_bin_a/b`, `clutter_city_bollard_concrete`.
  - Italy: `italy_petrolstation_pricedisplay_big/small`, `charging_station_a/b`, `italy_city_extras_trash_bin`,
    `italy_petrolstation_pump_number_a..d`.
  - West Coast: `airCompressor`, `garbage_bin_a/b`, `bollard_yellow`, `dumpster`.
  - Hirochi: `hr_charging_station`.
  - Johnson Valley: `s_gasstation_sign`.
  - Utah: `ut_gas_station`.
  - Every new shape must be preloaded through `style_shapes` → `anchor_ready.fuelShapes`, and only for the anchor's
    style. Each new shape is one more prewarm, so add few.
- **Spawning.** `gasstations.lua` `spawn` makes a whole station in one governor slot (`PRIOR.fuel = 3.0`). Most take
  under 5 ms, but the Buc-ee's took 23.8 ms. A re-sent tile whose record has a different prop/area count calls
  `deleteObjs` and respawns: that's the flash. A same-count record is moved in place (`replace`).
- **Collision.** Each spawn triggers `onCollide` → a batched `be:reloadCollision()` costing ~0.3 ms per 1k collidable
  tris. New props default to `collisionType = 'None'` unless they're big enough to hit (store, price sign pole,
  charger).
- **World map.** It's EarthMap.vue: SVG overlays, `placeMarkers` (saved places; clicking calls
  `setGps(lat, lon, name)`), and a layers panel with persisted checkboxes.
  - Server round trips copy the geocode pattern: map → settings.lua bridge id → core.lua net message → earthd
    `spawn(...)` → `*_result` → core table → the map polls.
  - The minimap is the stock 0.40 navigation app. It shows POIs from `gameplay_rawPois`, which our stations already
    feed. Like the stock stations, they only show with "gas stations in freeroam" on (to be checked in game).
- **Where to steer, not who.** The GPS takes a lat/lon. The server's OSRM routes it, and gps.lua follows the route on
  the local navgraph (ARRIVE_M = 40).
- **Upstream habits** (memory): defaults are Tecna's call. Any new earthd flag goes in both start.py and launcher.py
  RECOMMENDED. Check `dev` as well as `main` before starting each PR.

## Design, by part

The parts are ordered by value to the player against risk. Each part is its own PR (the user wants each feature
proposed on its own).

### A. Find a station: world map layer + "nearest" (PR 1, highest value)

**Station index (server).** Add a compact per-cell index of stations (`stationindex.py`):
- Each record is lat, lon, display name, brand, kind (`fuel` | `ev` | `truck`).
- It's built from the `places` layer through the existing `gasstations.classify` (one rule set), plus
  `ev_charging_station` and `truck_gas_station` as new kinds.
- Its cell is the map-data cell. It's cached on disk next to the map-data cache as a small JSON/npz per cell
  (about 1 KB a city cell), so a later lookup never decodes `places` again.
- Building a cell's index decodes `places` once for that cell, in the worker pool and never on the event loop. The
  decoded frame is dropped right away rather than kept in mapdata's LRU, so the 160 MB Deck cap isn't touched.

**Messages (additive, Protocol 4 table):**
- `stations {id, lat, lon, r_km, kind}` → `stations_result {id, items:[{lat, lon, name, brand, kind, km}]}`. It
  returns up to 50 nearest within r_km, which is capped at 25 km. The map uses it for the visible area; the menu uses
  it with the car's position.
- Cells outside the cache are built on demand, up to 9 cells per request. If more are needed, it returns what's ready
  and `partial: true`, and the map asks again on its next poll.

**World map.**
- The layers panel gets a "Gas stations" checkbox, saved like the others (`beamngEarth.map.stations`, default on).
  It shows a pump icon per station (a bolt for EV, a truck for truck stops) at zoom ≥ 12, and names at ≥ 15 using
  `mm.visibleLabels`' collision thinning.
- Clicking a marker sets the GPS: `setGps(lat, lon, name)`.
- The context menu adds "Nearest gas station from here".
- **Nearest:** a "⛽ Nearest" button beside the search box asks with the car's lat/lon and kind `fuel`, then sets the
  GPS to the first result. A second button or a long press does EV.

**In-game menu (without opening the map).** Add a radial/quick-access action "Navigate to nearest gas station",
following the way core.lua registers its other actions; check that registration path at plan time. It uses the same
message. There's no new UI app.

**"Nearest" means by straight line.** It's the 50 nearest by straight line, then the first one. Ranking by route
distance through OSRM would mean one request per candidate. My call: straight line, because it's cheap. A river
between the car and the station is a known limit.

**Cost:** nothing per frame. Requests come only from the open map or a button. The disk cache is tiny.

### B. Spawning smoothly (PR 2, small, fixes a known limit)

- **Spread big stations over frames.** `spawn` becomes resumable. A station keeps a cursor (props, then areas), and
  `M.update` makes objects until `gov:try('fuel')` says the budget's spent, then resumes next frame. `charge` stays
  per chunk.
  - The station counts as `made` (POIs registered, `onCollide` called) only after its last object, so the collision
    rebuild still happens once per station.
  - Its objects load in the order they're listed: the server already lists roofs/units before small props, so
    the canopy shows first.
- **No flash on re-sent tiles.** When a re-sent record differs only by props (a new count), diff it by a
  per-prop key (shape + rounded local position). Keep the matches with `place`, delete the extras, and queue only the
  missing ones.
  - Areas are matched the same way. A changed area set re-registers the POIs (`poisDirty`).
  - Only a record from another anchor frame that can't be matched falls back to delete + respawn, and that happens
    only during a rebase, when the screen is already busy.
- **Cost:** less per frame than today (a Buc-ee's spread over about 5 frames at ≤ 5 ms each).

### C. Paving the whole lot (PR 3)

- `forecourt_pad` reaches the shop's front only when it's within `PAD_SHOP_LINK_M = 10`. Phase two paves the whole
  lot: the station's site, meaning the hull of the pad, the shop's outline and the gap between, plus any OSM
  `amenity=parking` area that touches the pad.
- The lot is clipped short of neighbouring buildings (`PAD_BLD_GAP_M`) and road edges, exactly as the pad is today.
- **Guard rails:**
  - Never pave more than `LOT_MAX_M2` (my call: 6,000 m², a big truck stop's forecourt).
  - Never pave over a mapped grass/landuse polygon inside the hull.
  - A Buc-ee's-size site keeps today's per-canopy pads.
- The parking-lots-v2 branch is paused and has its own lot rules. If it lands later, its lots win where they overlap;
  this only paves gas station sites.
- **Cost:** the same three painters as today (1-3 ms per block surface, 4-7 ms per photo with a pad). Bigger polygons
  are the same cost class.

### D. The Marathon case: a pin inside an unlabelled building (PR 3, with C)

- Today a station is skipped if its pin falls inside an unlabelled building that might be its canopy.
- New rule: the pin's building is treated as the canopy when **all** of these hold:
  - It's rectangular (`CANOPY_RECT_MIN`).
  - Its size is canopy-like (the same short/long bounds as ML canopies).
  - It's unlabelled (no class, or `roof`).
  - Another building within `SHOP_SEARCH_M` could be the shop.
  - It's not tagged as a car wash or anything in `NOT_SHOP_CLASSES`.
- Otherwise it stays skipped. The car wash rule stands.
- Tests reuse the real Marathon footprint near Pittsburgh under `BNGE_GAS_REAL=1`, named only as "a Marathon near
  Pittsburgh".

### E. Looks: brand colours, price signs, small props, the kiosk store (PR 4)

- **Brand colours.**
  - A small table maps `brand_wikidata` to an accent colour, for about 20 big brands (Shell, BP, Exxon, Sunoco,
    Sheetz, Speedway, Wawa, GetGo, Marathon, Circle K, Aral, Esso, Total, Q8, Eni, Repsol...). A brand not in the
    table stays stock.
  - The colour is applied through a per-brand material, made once per brand per session, as a
    `Material` cloned from the stock canopy fascia with a `diffuseColor` tint.
  - It affects only the canopy's edge/fascia and the brand sign's panel.
  - **Risk:** it depends on which submesh carries the fascia material in each stock shape. A short in-game probe
    comes first (Task 1 of that plan). If the stock shapes can't be tinted per instance, this part shrinks to the
    price sign's colour or is dropped.
  - **Cost:** one material per brand seen, no new textures.
- **Price signs.** One sign per station at the driveway nearest the main road, set back
  `ROAD_CLEAR_M`:
  - Europe gets `italy_petrolstation_pricedisplay_big`, US East gets `eca_gastation_pricedisplay`, and West gets the
    Johnson Valley `s_gasstation_sign` (to be checked in game for looks).
  - The numbers are whatever the stock texture shows. There are no dynamic prices: a non-goal.
  - It's collidable (it's a pole at the road's edge, where the car can hit it).
- **Small props.** At most 4 per station: bins by the shop's door, an air compressor (West/East) at a pad corner, and
  bollards at canopy pillars (Europe/East).
  - They're placed by the same `_clear` test as pumps, with no collision except bollards.
  - They're left out entirely in the small budget (`BNGE_BUDGET=small`, which the mod knows through the budget
    profile). That's the Deck.
- **East Coast kiosk store.** When a US East station has no mapped shop (the pumps sit at the pin), place
  `eca_gastation_store` facing the pumps, behind the pad, if `_clear` passes. Otherwise there's no store. It's never
  placed where any building is mapped.

### F. EV charging (PR 5)

- **Data.** `ev_charging_station` pins, from the same index as part A.
- **Placement.** Most chargers are in parking lots, often with no mapped outline.
  - Place a row of 2-4 chargers (`eca_charging_station` US, `charging_station_a` Europe, `hr_charging_station` else)
    along the nearest parking aisle or service road within 30 m of the pin, clear of buildings and roads.
  - If there's no aisle, place a pair at the pin if `_clear` passes. Otherwise skip.
  - No canopy and no pad. The lot is already paved, or it's dirt and we don't pave for chargers: my call, to keep the
    ground painters' cost where it is.
- **Use.** Each charger gets a `BeamNGGameplayArea` + POI with energy type `electricEnergy`, if the stock
  `gasStations.lua` supports it. 0.40's stock levels have EV chargers that work, so the same pair should serve; to be
  confirmed with a probe.
- **Overlap with fuel stations.** A charger pin within `MERGE_M` of a fuel station is folded into that station (a
  pair of chargers at its pad's edge) instead of standing alone.

### G. Truck stops (PR 5, with F)

- **Data.** `truck_gas_station` in `taxonomy`, plus a small brand list (Pilot, Flying J, Love's, TA, Petro). Big
  brands are often tagged plain `gas_station`.
- **Layout.** After the car canopy is laid out, look for a second canopy-shaped `roof` or ML outline on the far side
  of the shop or ≥ 40 m from the car canopy. Treat it as the diesel canopy:
  - wider lanes (`LANE_GAP_M` up to 14 m),
  - pumps marked diesel only (`ENERGY = {'diesel'}` for those areas),
  - the West Coast kit (taller roof; the East Coast unit's roof is too low for a truck).
- If there's no second canopy, it's a normal station.
- The truck-stop pad uses the `LOT_MAX_M2` exception from part C.

## Dropped, and why

- **Fuel types from OSM tags.** Neither data source the server reads has `fuel:*` tags. Reaching OSM directly means a
  new download (Overpass or a regional .pbf) per area: a new network dependency, rate limits and more Deck memory.
  That's too much cost for a label on the refuel prompt.
  - The truck-stop rule (part G) gets the one visible difference, diesel-only lanes, from data we have.
  - Revisit if Layercake adds fuel tags or Overture adds attributes.
- **Night lighting, AI traffic, career prices.** Out of scope (see Non-goals).

## Performance and Steam Deck summary

| Part | Per frame | Memory | Collision |
|---|---|---|---|
| A index + map | none (on request) | ~1 KB per city cell on disk; places decoded once per cell, dropped right away | none |
| B spawn spreading | lower peak (≤ budget per frame) | none | unchanged (once per station) |
| C/D lot paving | none extra; painters same class | none | none |
| E looks | +4 props per station (0 with the small budget) | one material per brand | price sign + bollards only |
| F/G EV/truck | one more station kind | shapes preloaded per region only | charger collision meshes |

Each PR measures with `BNGE_BUDGET=small` and reports it in its PR text, as #220 did.

## Added 2026-10-26, after #308 / PR #309 testing

The user, 2026-10-26: "PR is good but we have more work to do in Phase 2". Found in the world-wide test of PR #309
(403 stations in 30 cities on the server, 25 in game):

### H. Coverage gap: Japan, Melbourne (new PR 0, before A, highest value)
- Tokyo and Osaka lay out 0 of 20 stations, and Melbourne 3 of 33. This happens on `dev` too, so it isn't from PR #309.
- **Found (2026-10-26):**
  - **Japan:** 18 of the 20 are confirmed stations (ENEOS, Cosmo...) whose pin is inside an unclassed building of
    200-450 m², 6-7 m tall where mapped. That building is the whole station, its canopy with the office under it,
    mapped as one outline. We take it for the shop, find no canopy, and a pump pair doesn't fit on the tight lot.
  - **Melbourne:** not a real gap. 24 of its 30 misses are city-centre 7-Elevens without fuel, rightly skipped,
    and 3 are offices with a wrong `gas_station` category.
- **Fix (PR 0):** for a station that would otherwise get nothing, a canopy-sized, low, near-rectangular unclassed
  building around its pin is its canopy. Only stations that get no layout today may change, which the world script
  checks.

### I. L-shaped mapped roofs (part of E, or its own small PR)
- Since PR #309, a mapped roof that isn't a neat rectangle is taken by its area (120-900 m2). v1.6.3 took any roof.
- On strongly L-shaped roofs (filling about 0.5 of their box), the West Coast slab covers the whole box and cuts into
  the shop in the L's notch. Seen at Buenos Aires' YPF (-34.5986, -58.3906). Other examples: Madrid Repsol 0.51,
  Montreal Petro-Canada 0.56, São Paulo Posto Shell 0.58.
- Options, my order:
  1. Lay out on the roof's largest rectangle (cut the L into its two arms and use the bigger one).
  2. Use a fill floor of 0.6 (these fall back to a pump pair).
  3. Use one roof slab per arm.
- Keep Pittsburgh's BP (0.71) and Johannesburg's Shell (0.70) as they are.

### J. Left over from PR 1's review (2026-10-27; the user: "add this to phase 2 overall")
- **Trees and bushes on the paved forecourt (with part C, whole lots).** Corrected 2026-10-27 after measuring
  (gas-test-kit/trees_check.py): not under canopies (vegetation.py masks the map's buildings, so the outlines are
  avoided; 0 of 21 stations), but ON the pad: 6 of 21 stations in Pittsburgh and Mexico City have 1-2 items
  (deciduous, shrub, palm, desert rock) on the asphalt. vegetation cells know buildings, roads and water, not the
  stations' pads. Fix: (1) vegetation.tile_items drops items inside the kept fuel pads (as it drops water); (2) when
  a pad arrives after a veg tile was sent, that tile is sent again (the same race as the ground's pads_stale /
  hm_stage fix in PR 1). Whole lots grow the paved area, so do both together. Test: trees_check.py -> 0 on pad.
- **One-building stations ignore mapped drive lanes (part C/D).** `_one_building_site` always lays the islands
  along the outline; where the forecourt's lanes are mapped among the service roads (`find_lanes`), use them as
  `_layout_core` does.
- **Small efficiency notes (any PR that touches the code):**
  - `_fuel_named` builds one regex per fuel brand per call. Precompile one alternation of `_FUEL_NAMES`.
  - `M.reset` asks a collision rebuild for half-made stations too (level end: harmless, but skip it there).

### Coverage baseline (after PR 1, 2026-10-27; the user: "hold the number gained in this one as it's more of a fix
and mention overall will be coming in phase 2 next")
- Sample: 968 places listed as gas stations in 54 places (gas-test-kit cmp_world.py + cmp.py, G: cache). Built:
  `dev` 456 (47%), PR 1 512 (53%). By region with PR 1: Japan 49%, Russia/Ukraine/Belarus 87%, Latin America 50%,
  Africa/Middle East/Asia 45%, Europe 52%, US/Canada 67%, Oceania 20% (mostly Melbourne's city 7-Elevens).
- Accuracy against the brands' own lists (AllThePlaces, gas-test-kit accuracy.py): of 290 brand-listed stations,
  `dev` builds 46%, PR 1 57%. Of the stations PR 1 builds, 81% are backed by a current record.
- Phase two's target: the brand-listed share (57%) and the overall share (53%), measured the same way, reported per
  region in its PR (the coverage numbers were kept out of PR 1 on purpose).

### Overlap with Tecna's 2b44946 (the #308 fix)
- He added `LOT_MIN_M2` / `LOT_MAX_M2 = 6000`, `_is_lot` and `_lot_canopy`: a building named like the station is its
  whole lot. Part C must build on those, and rename its own cap (`PAVE_MAX_M2`) so it doesn't clash.
- Part D (pin inside an unlabelled building) is partly covered by `_is_lot` (named lots) and by PR #309's `_home_shop`
  (homes beside a canopy). What's left is unnamed, unclassed buildings around the pin.
- Before starting any part, check `dev` (Tecna fixes public issues himself within the hour).

### How every phase-two PR is tested (learnt the hard way)
- **Server.** Compare dev against the branch, laying out every station in the 30 world cities plus Pittsburgh,
  Baltimore, Munich, Utrecht, New Braunfels, Rio and Nagambie. Use `MapData("G:/BeamNGEarthCache", ...)`, **never
  the default cache on C:** (a 30-city run wrote 3.2 GB there and filled the drive). Review every changed station.
- **BNGE_GAS_REAL.** RealSpotsTest must pass. Tecna doesn't run it, so run it after his gas station commits too.
- **In game.** Use the branch's start.py from its worktree (copy `.beamng_earth.json`, link `.venv`), load the
  level with `freeroam_freeroam.startFreeroam("levels/beamng_earth/main.level.json")`, and visit each station type.
  Wait until station props exist within 160 m of the car (up to 10 minutes in an uncached city), then screenshot.
  Check beamng.log for gas station errors.
- No PR or comment goes up until the user has read it and said post.

## Left to the builder

- Icon artwork for the map markers. Inline SVG paths in EarthMap.vue, styled like the saved-place markers.
- The exact brand colour values.
- Whether the in-game action is a radial menu entry or an action map binding. Follow whatever core.lua already uses.

## Calls I made (for the user to check)

1. "Nearest" means nearest by straight line, not by driving distance.
2. The station index is its own small disk cache per map-data cell, not part of the map-data LRU.
3. The map layer is on by default, with names only when zoomed in.
4. The whole lot is capped at 6,000 m² and never paves over mapped grass.
5. Small props are left out entirely on the small budget (Deck).
6. EV chargers get no pad and no canopy.
7. Fuel types are dropped (no data). Truck stops give diesel-only lanes instead.
8. Brand colours start with a probe, and that part may shrink if the stock shapes can't be tinted.
9. Three PRs (the user, 2026-10-26: "I like the 3 PRs"): (1) fixes for what's live: H (Japan) + B (smooth spawning);
   (2) find a station: A; (3) looks and kinds: C, D, E, I, F, G. Each part is its own commit or commits, so Tecna
   can drop one.
