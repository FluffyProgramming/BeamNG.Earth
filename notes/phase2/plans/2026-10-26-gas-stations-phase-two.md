# Gas Stations Phase Two Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stations where the map data supports them, everywhere (Japan first); then finding a station from the map
or a menu, smooth spawning, whole lots, better looks, EV chargers and truck stops.

**Architecture:** three PRs (the user, 2026-10-26: "I like the 3 PRs"), each on its own branch cut from upstream
`dev` as it stands that day (check `dev` first: Tecna fixes public issues himself, #308 within 30 minutes):

| PR | Branch | Parts | What it is |
|---|---|---|---|
| **1. Fixes for what's live** | `fix/gas-stations-japan-spawn` | H (Japan), B (smooth spawning) | Japan's stations, big stations spread over frames, no flash on re-sent tiles |
| **2. Find a station** | `feature/gas-station-finder` | A | world map layer, Nearest button, radial menu entry |
| **3. Looks and kinds** | `feature/gas-stations-looks` | C, D, E, I, F, G | whole lots, brand colours, price signs, props, kiosk store, L-shaped roofs, EV chargers, truck stops |

PR 1 and PR 2 are planned task by task. PR 3 is outlined: the code under it will have moved by then, so it gets a
detailed plan when it starts. Within a PR, each part is its own commit or commits, so Tecna can drop one part if he
doesn't want it.

**Tech Stack:** Python 3.10+ asyncio server (earthd), DuckDB/GeoParquet map data; GE Lua (luajit tests with
mod/tests/stubs.lua); Vue 3 world map (node test for mapmath).

**Spec:** `.claude/superpowers/specs/2026-10-26-gas-stations-phase-two-design.md` (parts A-I; "Added 2026-10-26").

## Global Constraints

- Base every branch on `origin/dev` of TecnaGamer/BeamNG.Earth (after PR #309 if it is merged by then), in its own worktree (copy `.beamng_earth.json`, link `.venv` to the main checkout's).
- New protocol messages are additive and go in server/README.md "Protocol 4"; test_protocol_agreement passes for them.
- Nothing CPU-heavy on the event loop; no extra map-data layer in the block processes.
- A new earthd flag goes in both start.py and launcher.py RECOMMENDED.
- No new assets: stock level shapes only, preloaded only for the anchor's region style (`style_shapes`).
- Comments cite the user with dates and quotes. Never name the user's town; say "the Pittsburgh area".
- Commits: no Co-Authored-By lines, no Claude footers. **No push, PR, comment or "ready" without the user's explicit go after reading the text** (memory: pr-review-before-posting).
- Deck: measure with `BNGE_BUDGET=small`; report the numbers in the PR.
- Map data for tests and comparisons comes from `G:/BeamNGEarthCache`, **never the default cache on C:** (C: has ~3 GB free).
- Stop earthd before any checkout or rebase (it locks server/earthfast.pyd).

## The test kit (every PR)

Saved in `.superpowers/gas-test-kit/` (git-ignored):
- `cmp_world.py SERVER_DIR` lays out every station in 30 world cities and prints one line per station; `cmp.py` does
  the same for Pittsburgh, Baltimore, Munich, Utrecht, New Braunfels, Rio and Nagambie. Run each on a `dev` worktree
  and on the branch, then `diff`. **Every changed line is reviewed** (why it changed: `why.py`), and the PR text lists
  the counts.
- `BNGE_GAS_REAL=1 python -m unittest tests.test_gasstations.RealSpotsTest` passes on the branch.
- In game: `sweep_c.sh LIST OUT` (teleport, wait up to 10 minutes for station props within 160 m of the car,
  screenshot, scan beamng.log). The lists hold one station of every layout type; add the PR's own stations.
- Baselines from PR #309's run (2026-10-26): 403 stations in 30 cities and 114 in the seven areas; no errors.

## Review Focus

1. **A pin inside a shop that is not a canopy (US, Europe):** PR 1's Japan rule must not turn a mapped kiosk into a
   canopy where today's pipeline already lays the station out. Only stations that get nothing today may change.
2. **Map-data gaps:** a city whose places, buildings or roads layer is missing or unreachable. Stations quietly
   disappear (tile_sites' try/except); nothing raises on the event loop.
3. **A rebase in the middle of a spread-out spawn (PR 1):** the objects already made move with the world; the rest
   spawn in the new frame.
4. **A re-sent record with one prop fewer (PR 1):** exactly that object goes; nothing else blinks; the POIs stay.
5. **The world map over the ocean or the poles (PR 2):** an empty answer, not an error; "Nearest" says none found.

---

# PR 1: Fixes for what's live. Branch `fix/gas-stations-japan-spawn`

## Part 1: Japan, stations mapped as one building (spec part H)

**What we know (2026-10-26, Tokyo and Osaka on dev):** 0 of 20 stations laid out. 18 are confirmed stations
(ENEOS, Cosmo, Idemitsu...) whose pin lies inside, or within 5 m of, an **unclassed building of 200-450 m²** (height
unmapped or 5.7-6.8 m). That is the whole station (the canopy, with the office under it) mapped as one outline.
find_shop takes it as the shop; no other canopy exists, and a pump pair does not fit on the tight lot, so the station
gets nothing. The other 2 are 7-Elevens, rightly skipped. (Melbourne is not a gap: 24 of its 30 misses are CBD
7-Elevens, convenience stores without fuel, and 3 are offices with a wrong `gas_station` category.)

**The rule:** only for a station that would get **no site at all** today. If its pin lies inside, or within
`ONE_BLD_PIN_M` of, one building that is:
- unclassed or `roof` / `commercial` / `service` (the classes Task 1 confirms),
- of a canopy's area (`CANOPY_AREA_M2`, 120-900 m²),
- no taller than `CANOPY_MAX_H_M` where a height is mapped,
- at least `ONE_BLD_FILL` of its oriented box (Task 1 picks the value; Tokyo's outlines are near-rectangles),

then that building is the station's canopy: it is left out of the building mesh, and the islands go under it
(`_outline_lanes`, the West Coast roof slab). The shop is the nearest other building within `SHOP_SEARCH_M`, not
across a public road and not a home. With none, the canopy stands alone.

The car wash rule stands: a building named or classed as a car wash never qualifies.

### Task 1: Measure Japan (read-only, no code in the repo)

- [ ] Extend the kit's world list with Nagoya (35.1815, 136.9066), Sapporo (43.0618, 141.3545), Fukuoka
  (33.5902, 130.4017) and Tsukuba (36.0835, 140.0764) as a suburban case. Run `why.py`-style diagnostics on every
  unlaid station there. Record in the ledger:
  - the area, class, height and box-fill distribution of the buildings the pins are in;
  - how many have a second building within 30 m (the office);
  - three real coordinates for tests: a Tokyo ENEOS, an Osaka Cosmo, a suburban one.
- [ ] Run the same diagnostics over the 30 world cities, counting stations that get no site today and whose pin is
  inside a building that would qualify. Those are the stations outside Japan that the rule would add, and each is
  reviewed in Task 4.
- [ ] Rule in the ledger: the exact `ONE_BLD_PIN_M`, the allowed classes and `ONE_BLD_FILL`, each with the numbers
  behind it.

### Task 2: The rule, test first

**Files:**
- Modify: `server/gasstations.py` (a new `_one_building_site`; `_layout` calls it last, only when `site is None`)
- Test: `server/tests/test_gasstations.py`

**Interfaces:**
- Produces:
  - `ONE_BLD_PIN_M: float`, `ONE_BLD_CLASSES: set`, `ONE_BLD_FILL: float`
  - `_pin_building(st, blds) -> Bld | None`
  - `_one_building_site(st, blds, roads, service, style) -> Site | None`

- [ ] **Step 1: Write the failing tests:**
  - `test_station_mapped_as_one_building`: a 20 × 15 m unclassed building with the pin inside, a street 12 m
    away, and no other buildings. The site is not None, `drop_ids == ("bld",)`, and every area is inside the
    building's box (pad 1.5).
  - `test_one_building_with_an_office_beside_it`: plus a 6 × 5 m building 8 m away. That's the shop
    (`site.shop_id`).
  - `test_one_building_never_over_a_working_layout`: a pin inside the shop, with a mapped canopy beside it. The
    layout is identical to today's (compare with `gs.layout` without the new rule: the drop_ids and the prop count).
  - `test_one_building_limits`: each of these gives None:
    - a 1,200 m² building,
    - an 18 m-tall one,
    - a home,
    - a car wash (named "Car Wash", or classed `car_wash`),
    - an L-shape below `ONE_BLD_FILL`,
    - a convenience-brand-only pin.
- [ ] **Step 2: Run** `cd server && python -m unittest tests.test_gasstations -k one_building -v`. Expected: FAIL
  (AttributeError / None).
- [ ] **Step 3: Implement.** `_layout` keeps its current pipeline; at each `return None` path for a confirmed station,
  try `_one_building_site` first. It reuses `_outline_lanes`, `_lane_site`, `forecourt_pad` with the building as the
  canopy.
- [ ] **Step 4: Run** the same command, then the whole `tests.test_gasstations`. Expected: PASS.
- [ ] **Step 5: Commit** `Gas stations: a station mapped as one building around its pin is its canopy (Japan)`.

### Task 3: Real-data test

- [ ] Add `RealSpotsTest.test_one_building_japan` with Task 1's Tokyo ENEOS: one record, its building in `skip`, a
  `s_fuel_structure_06` slab. Run `BNGE_GAS_REAL=1 ... RealSpotsTest`. Expected: all pass (5/5 with Nagambie's).
- [ ] Commit `Gas stations: a real Tokyo station in RealSpotsTest`.

### Task 4: The world comparison and the in-game tour

- [ ] Kit: `cmp_world.py` + `cmp.py` (plus the four Japanese cities) on dev and on the branch, then `diff`.
  Expected: only additions (none → a site), no other line changes. Review every addition outside Japan with `why.py`.
  Any that is a kiosk, a car wash or a bus garage tightens Task 2's limits (a new failing test first).
- [ ] In game: three Tokyo stations, two in Osaka, one in Sapporo, plus the kit's standard list (Buc-ee's, Pittsburgh
  BP, Sunoco, Nagambie, Munich Aral, Rio Ipiranga, Johannesburg Shell). Screenshots, beamng.log scan, and the
  `BNGE_BUDGET=small` spawn time of the biggest Japanese station.
- [ ] Record the before/after counts per city, the screenshots and the Deck numbers in the ledger for the PR text
  (written after Part 2).

---

## Part 2: Smooth spawning (spec part B), on the same branch as Part 1

Everything is in `mod/beamng_earth/lua/ge/extensions/beamngEarth/gasstations.lua`; the tests are in `mod/tests/test_gasstations.lua`.

### Task 5: Resumable spawn

**Interfaces:** the station field `st.cursor` (`nil` | `{phase='props'|'areas', i=int}`); `spawnStep(id, st, gov) -> done:boolean`.

- [ ] **Step 1: Write the failing tests:**
  - `test_big_station_spread`: 40 props, with a gov allowing 10 objects a frame. After frame 1: 10 objects, `made == false`, no `onCollide`. After frame 5: everything, `made == true`, `onCollide` called once.
  - `test_drop_mid_spawn`: `dropKey` after frame 1 deletes the 10 objects and clears the station.
  - `test_rebase_mid_spawn`: `transform` after frame 1 moves the 10 objects; the rest spawn in the new frame.
- [ ] **Step 2: Run** `cd mod/tests && luajit test_gasstations.lua`. Expected: the new tests FAIL, the old ones PASS.
- [ ] **Step 3: Implement:**
  - Per-object helpers driven by `st.cursor`.
  - `M.update` keeps the station at the queue's head until it's done.
  - Charge the governor per chunk.
  - Set `made` / `poisDirty` / `onCollide` at the end.
- [ ] **Step 4: Run** it. Expected: PASS. **Step 5: Commit** `Gas stations: a big station spawns over several frames`.

### Task 6: No flash on re-sent tiles

**Interfaces:** `propKey(p) -> string` (the shape plus its position rounded to 0.5 m), used inside `onRows`.

- [ ] **Step 1: Write the failing tests:**
  - one prop fewer: one object deleted, the other ids unchanged, nothing queued;
  - one prop more: one object created;
  - a new frame (every key different): delete + respawn, as today;
  - areas changed: POIs re-registered, unchanged areas keep their ids.
- [ ] **Step 2: Run** it. Expected: FAIL. **Step 3:** Implement the diff in `onRows`' "another layout" branch. **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5: In game:** past the Buc-ee's, no frame-time spike above the fuel budget; back and forth across a road tile edge at a station, no blink. Record the `BNGE_BUDGET=small` numbers.
- [ ] **Step 6: Commit** `Gas stations: a re-sent road tile keeps its station's objects (no flash)`.

PR 1 is done when: the kit's world comparison shows only Japan's additions (plus whatever Task 4 ruled in); the
server tests on the branch match those on a `dev` worktree; all mod tests pass; the in-game tour is clean. Then write
the PR text to a local file for the user (the per-city counts, the screenshots, the Deck numbers, each part's commits
listed so Tecna can drop one). **Do not open it**; the user reads it first.

---

# PR 2: Find a station (spec part A). Branch `feature/gas-station-finder`

### Task 1: The station index (server)

**Files:** Create `server/stationindex.py`; Test `server/tests/test_stationindex.py`.

**Interfaces:**
- Consumes: `gasstations.classify`, `gasstations._display_name`, the map-data cell grid (as `gasstations._cells_near`).
- Produces:
  - `KINDS = ("fuel", "ev", "truck")`
  - `kind_of(category, taxonomy, wikidata, status, brand_name) -> str | None`
  - `cell_index(md, cell) -> list[dict]`: dicts `{lat, lon, name, brand, kind}`, cached at `<cache>/stations/<cell>.json`
  - `nearest(md, lat, lon, r_km, kind, limit=50, max_build=9) -> (items, partial)`, sorted by `km`, r_km clamped to 25

- [ ] **Step 1: Write the failing tests:**
  - `test_kind_of`:
    - `gas_station` → `"fuel"`
    - `ev_charging_station` → `"ev"`
    - taxonomy `truck_gas_station` → `"truck"`
    - closed → `None`
    - a convenience brand → the same as `classify`
  - `test_cell_index_cached`: the second call reads the JSON and the fake reader's call count stays 1.
  - `test_nearest_sorted_and_capped`: sorted by km, at most `limit`, every km ≤ r_km, and 100 is clamped to 25.
  - `test_nearest_partial`: `max_build=1` with 3 unbuilt cells gives `partial is True`.
- [ ] **Step 2: Run** `cd server && python -m unittest tests.test_stationindex -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement.**
  - Read `places` for one cell without putting it in mapdata's LRU, so Deck memory is untouched.
  - Write the JSON atomically (tmp + replace, as cache.py does).
  - Use haversine distances.
- [ ] **Step 4: Run** it. Expected: PASS. **Step 5: Commit** `Gas station finder: a small per-cell station index (fuel, EV, truck stops)`.

### Task 2: The `stations` message (server)

**Files:** Modify `server/earthd.py` (beside `geocode`, and its dispatch), `server/README.md` (Protocol 4); Test
`test_stationindex.py`, `test_protocol_agreement.py`.

**Interfaces:**
- The client sends `{"type":"stations","id","lat","lon","r_km","kind"}`.
- The server replies `{"type":"stations_result","id","items":[{lat,lon,name,brand,kind,km}],"partial"?:true,"error"?:str}`.

- [ ] **Step 1: Write the failing tests:**
  - `test_stations_message_runs_off_loop`: copy geocode's check.
  - `test_stations_bad_input`: an `error`, and items `[]`.
  - The two messages added to the protocol table.
- [ ] **Step 2: Run** `cd server && python -m unittest tests.test_stationindex tests.test_protocol_agreement -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** `async def stations(self, msg)` like `geocode`, and add `elif kind == "stations": self.spawn(self.stations(msg))`.
- [ ] **Step 4: Run** it. Expected: PASS. **Step 5: Commit** `Gas station finder: the stations message (nearest stations to a point)`.

### Task 3: The mod bridge (Lua)

**Files:** Modify `core.lua` (`stationResults` beside `geocodeResults`, the handler beside `geocode_result`, and the
request/poll functions beside `requestGeocode`), `settings.lua` (a bridge beside `geocodeId`); Test
`mod/tests/test_stationfinder.lua`.

**Interfaces:**
- `core.requestStations(id, lat, lon, rKm, kind) -> bool`
- `core.pollStations(id) -> {items, partial, error} | nil`
- `settings.askStations(lat, lon, rKm, kind) -> {id}`, `settings.pollStations(id)`
- `core.gpsToNearestStation(kind)`: asks with the car's lat/lon, then sets the GPS to item 1, or shows the message "No gas station found nearby".

- [ ] **Step 1: Write the failing tests** (stubs.lua net capture):
  - the exact sent table;
  - the result returned once, then nil;
  - the nearest one's GPS call;
  - the empty-answer message.
- [ ] **Step 2: Run** `cd mod/tests && luajit test_stationfinder.lua`. Expected: FAIL.
- [ ] **Step 3: Implement**, mirroring the geocode functions.
- [ ] **Step 4: Run** it, plus `test_gps.lua` and `test_gasstations.lua`. Expected: PASS.
- [ ] **Step 5: Commit** `Gas station finder: the mod's bridge and "navigate to the nearest station"`.

### Task 4: The world map layer and the Nearest button (Vue)

**Files:** Modify `EarthMap.vue` (a layers checkbox, a stations computed beside `placeMarkers`, markers, a context
menu entry, a button by the search box), `mapmath` + `mod/tests/test_mapmath.mjs`.

**Interfaces:** `mm.stationQuery(view) -> {lat, lon, rKm}` (the view's centre and half-diagonal, capped at 25).

- [ ] **Step 1: Write the failing test** `stationQuery`: zoom 14 at 1280×720 gives about the half-diagonal (±5%); zoom 8 is capped at 25.
- [ ] **Step 2: Run** `node mod/tests/test_mapmath.mjs`. Expected: FAIL.
- [ ] **Step 3: Implement:**
  - The checkbox `beamngEarth.map.stations`, default on.
  - Ask when the view settles, at zoom ≥ 12; poll every 300 ms; ask again while `partial`.
  - Pump, bolt and truck icons; names at zoom ≥ 15 via `mm.visibleLabels`.
  - A marker click calls `setGps`.
  - The context menu entry "Nearest gas station from here".
  - The "Nearest" button calls `gpsToNearestStation('fuel')`.
- [ ] **Step 4: Run** the test. Expected: PASS.
- [ ] **Step 5: In game:** markers at zoom 12+, names at 15+; a click routes there; "Nearest" routes; the server log shows index builds under 1 s and off the loop.
- [ ] **Step 6: Commit** `Gas station finder: stations on the world map, and a Nearest button`.

### Task 5: The radial menu entry

- [ ] **Step 1:** Write a probe (`probes/quickaccess.lua`) for 0.40.3's radial menu API. Ledger the finding as a ruling. If there's no safe way in, rule it out and keep the map button only.
- [ ] **Steps 2-5:** a failing test that one entry "Nearest gas station" calls `core.gpsToNearestStation('fuel')`; implement it; the test passes; then the in-game check.
- [ ] **Step 6: Commit** `Gas station finder: "Nearest gas station" in the radial menu`.

PR 2 is done when: the server tests on the branch match those on a `dev` worktree; all mod tests pass; the PR text is
in a local file for the user. Don't push.

---

# PR 3: Looks and kinds (outline; full plan when it starts). Branch `feature/gas-stations-looks`

One commit group per part, in this order: whole lots, looks, L-shaped roofs, EV chargers + truck stops.
Spec part J (PR 1's leftovers) is folded into Parts 1 and 2.

**Part 1: Whole lots, and pins inside unnamed buildings elsewhere (spec C, D).** Server only.
- `site_lot(site, shop, blds, roads, parking) -> polygon | None`: the hull of the pad and the shop's front, plus any
  touching `amenity=parking`, clipped as `forecourt_pad` clips. Its cap is `PAVE_MAX_M2 = 6000` (not `LOT_MAX_M2`,
  which is Tecna's `_is_lot`).
- Build on Tecna's `_is_lot` / `_lot_canopy` (named lots) and on PR 1's one-building rule. What D still needs is
  whatever PR 1's world comparison shows outside Japan.
- Tests: test_gasstations; BNGE_GAS_REAL; the kit. Report the painters' time before and after.
- J (moved to Part 1, whole lots; measured 2026-10-27): no tree or bush on the paved pad. vegetation.tile_items drops
  items inside the kept fuel pads, and a veg tile already sent is sent again when a pad arrives after it. Check:
  gas-test-kit/trees_check.py (before: 6 of 21 stations with items on the pad; none under a canopy).
- J: `_one_building_site` uses the forecourt's mapped lanes (`find_lanes`) when they are under the outline, as
  `_layout_core` does; a test with mapped lanes beside a one-building station.

**Part 2: Looks (spec E, plus I: L-shaped roofs).**
- Task 1 is an in-game probe: can each stock canopy shape take a per-instance material tint? That decides the brand
  colours.
- I: lay a roof filling less than ~0.8 of its box out on its largest rectangle (cut the L into its arms and use the
  bigger one).
  - The cases: Buenos Aires YPF (-34.5986, -58.3906), Madrid Repsol, Montreal Petro-Canada, São Paulo Posto Shell.
  - Pittsburgh's BP (0.71) and Johannesburg's Shell (0.70) must still look right.
- Then:
  - price signs, small props (none on the small budget) and the ECA kiosk store, every new shape in `style_shapes`;
  - mod: per-brand materials cached per session.

- J (small): precompile `_fuel_named`'s brand alternation; `M.reset` skips the collision rebuild.

**Part 3: EV chargers and truck stops (spec F, G).**
- Task 1 is a probe: does stock `gasStations.lua` take `electricEnergy` areas in freeroam?
- Server:
  - `ev_sites`: a row along a parking aisle, or a pair at the pin, or folded into a fuel station within `MERGE_M`;
  - the truck stop's second canopy, with diesel-only areas;
  - the `PAVE_MAX_M2` exception for truck stops.
- Mod: per-area energy types in `pois`.
- Uses PR 2's `kind_of`.

---

# Coverage step 1: the wider pump-pair search (planned 2026-10-27). Branch `feature/gas-station-coverage`

The user, 2026-10-27: "Yes let's do step 1 but also don't forget we are planning on adding ev chargers for phase 2";
"I thought we wanted to avoid the 4.4gb data source" (no OSM at runtime: OSM is our offline test tool only).

**Measured (gas-test-kit/osm_fuel.py, osm_why.py, pair_wide.py):** of 504 OSM-confirmed real stations in the 968-station
sample, PR 1 builds 373 (74%). Of the 131 missed, 123 have a shop but no canopy and `_pair_site` finds no room: it only
looks straight from the shop toward its one nearest road, +-8 m sideways. A grid search within 40 m of the pin, each
spot facing its own nearest road, fits 90 of them (66 with the trust check). Unconfirmed listings: 107 of 207 fit
(38 trusted), some junk (offices, EV chargers): so the wide search is gated.

**Rule:** `_wide_pair_site(st, shop, blds, roads, kit)`, only after every other layout failed, only for a station that is
confirmed, trusted (`Station.trusted`), fuel-named (`_fuel_named`) and not an EV charger (`_is_ev`): candidate centres
on a WIDE_STEP_M grid within WIDE_REACH_M of the pin, nearest to the shop first; the pair faces the candidate's nearest
road; `_clear` (3 m off carriageways, 1 m off buildings); never across a public road from the shop (or the pin).
`_is_ev(name)`: EV charging words and networks; a charger is left for phase two's EV part (spec F), which uses it.

**Tasks:** (1) `_is_ev` test first; (2) `_wide_pair_site` test first (a forecourt beside the shop, across the corner from
the nearest road; the gates; no pair across a road; time per call bounded); (3) wire into `_layout_core` (default,
us_east and europe kits); (4) cost: time per failing station (Deck), prefilter like `_pair_site`; (5) the 968-station
comparison (0 lost / 0 changed), real coverage with OSM offline (target ~87%), the new stations checked by name;
(6) in game: a sample of wide-search stations (pumps where a forecourt is), screenshots; (7) PR text, user reads it first.
