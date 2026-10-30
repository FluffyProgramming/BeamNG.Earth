# EV Chargers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every EV charger Overture or OpenStreetMap lists near the car is placed in game with the stock charger models and charges an electric car through the stock prompt.

**Architecture:** Chargers ride on the gas stations' pipeline. The server reads chargers from the same two sources (Overture places, OSM Layercake POIs via `osmfuel.py`), lays them out per road tile in a new `server/evchargers.py`, and emits them as extra records in the road tile's station list with `"energy": ["electricEnergy"]` and a small asphalt pad. The mod spawns them exactly like stations and hands the stock `freeroam_gasStations` POI the record's energy types.

**Tech Stack:** Python 3.10+ (numpy, DuckDB via `rangeread`), GE Lua (luajit-testable modules), BeamNG.drive 0.40.3 stock assets.

**Spec:** `.claude/superpowers/specs/2026-10-29-ev-chargers-design.md`

## Global Constraints

- Base: branch `feature/ev-chargers` off `feature/gas-stations-osm-b` (PR #502) in a new worktree `E:\Codespace\FluffySwizzPublicGit\bne-ev`; rebase onto `dev` once #502 is merged.
- Every charger in the data is placed; never a building, road or lane blocked: skip a charger with no clear spot.
- Big site = a known fast network by name/brand, or 2+ merged records: a row of 4–8 chargers. Everything else: 1–2.
- Records within `MERGE_M` (60 m) of each other are one site, across both sources.
- Ground paint at its minimum: one plain asphalt patch per site (chargers + stall depth 5.5 m), no markings.
- No canopy. No separate settings switch: chargers come with the gas stations; OSM chargers off with `BNGE_OSM_FUEL=0`.
- Streaming as gas stations: per road tile, round the car, spawned in the mod's governor budget, shapes preloaded per region only (`style_shapes` → `anchor_ready.fuelShapes`). Must hold on `BNGE_BUDGET=small` (Steam Deck).
- Energy type string: `electricEnergy` (stock `freeroam/gasStations.lua`).
- Comments cite the user with dates and quotes ("the user, 2026-10-29: ..."), engine sources by file. No `Co-Authored-By` or Claude lines in commits. Commit subjects start `EV chargers:`.
- Tests: `cd server && ../.venv/Scripts/python.exe -m unittest tests.<module>`; Lua: `luajit mod/tests/test_gasstations.lua` (skip if luajit is missing, say so).

## Review Focus

1. A charger point inside a building outline (a parking garage): not placed inside it; skipped when no clear kerb is within reach. → Task 4 `test_charger_in_garage_skipped`.
2. A charger site seen by two road tiles: the same layout in both, one record only (in the tile that owns its position). → Task 5 `test_charger_owned_by_one_tile`.
3. The same charger in Overture and OSM 30 m apart: one site, not two. → Task 3 `test_merge_across_sources`.
4. An Overture listing filed as `gas_station` but named as a charger (Shell Recharge, BP Pulse): becomes a charger site, never gets fuel pumps. → Task 3 `test_ev_gas_listing_is_a_charger`.
5. A tile with no places data or an unfetched OSM cell: no crash; chargers from what's there; the tile isn't kept in the revisit cache (`revisit.fault`). → Task 5 `test_chargers_without_data`.

---

### Task 1: Probe: a stock charger that charges

Everything later assumes a `BeamNGGameplayArea` + POI with `energyTypes = {'electricEnergy'}` makes the stock prompt charge an electric car, and needs each model's real footprint and facing.

**Files:**
- Create: `probes/ev_charger.lua` (pattern: `probes/fuel_pump.lua`)
- Create: `docs/research/2026-10-29-ev-chargers.md` (findings)

**Interfaces:**
- Produces (findings, copied as constants in Task 4): per model path its footprint (m), the direction its front faces relative to yaw 0, its height offset, and the materials file it needs:
  - `/levels/east_coast_usa/art/shapes/buildings/eca_charging_station.DAE`
  - `/levels/west_coast_usa/art/shapes/buildings/s_fuel_charger_car_2022.dae` (+ `s_fuel_charger_concrete_base.dae`)
  - `/levels/italy/art/shapes/buildings/charging_station_a.DAE`, `charging_station_b.DAE`

- [ ] **Step 1:** Write `probes/ev_charger.lua`: spawn the 4 models in a row 3 m apart in front of the player vehicle, one area + POI per charger with `energyTypes = {'electricEnergy'}` (as `fuel_pump.lua` does for fuel), and print each shape's object box.
- [ ] **Step 2:** In game (Earth level, cache on G:, `--cache-dir G:/BeamNGEarthCache`), spawn an electric car (stock `etk800` EV or `vivace` e-variant), drain it, run `python tools/mcp.py luafile probes/ev_charger.lua`, drive into an area. Expected: the stock charge prompt; the battery fills; the minimap shows a bolt icon.
- [ ] **Step 3:** Screenshot each model from the side and front; record footprint, facing, base needed or not, missing materials (pink/white) in `docs/research/2026-10-29-ev-chargers.md`. Pick one model per style (`default`, `us_east`, `europe`).
- [ ] **Step 4:** If the prompt does not charge, stop and report: the rest of the plan depends on it.
- [ ] **Step 5:** Commit `EV chargers: a probe of the stock chargers (charging works through the stock prompt; footprints)`.

### Task 2: OSM reads chargers too

**Files:**
- Modify: `server/osmfuel.py` (`FIND` step filter at the `r[1] == "fuel"` comparison; row dict)
- Modify: `server/mapdata.py` (`osm_fuel_path`, `versions()`)
- Modify: `server/gasstations.py` (`_osm_points`)
- Test: `server/tests/test_osmfuel.py`, `server/tests/test_gasstations.py`

**Interfaces:**
- Produces: `osmfuel.AMENITIES = ("fuel", "charging_station")`; `OsmFuel.cell(bounds, kind) -> list[dict]` rows now carry `"amenity"`; `mapdata.OSM_POI_VERSION = 2`; cached cells live under `raw/osmfuel_cells/v2/`; `versions()["osmfuel"] = OSM_POI_VERSION if OSM_FUEL else False`; `gasstations._osm_points(frame, cells, amenity="fuel")` keeps only that amenity.

- [ ] **Step 1: Write the failing tests**
  - `test_osmfuel.OsmFuelReadTest.test_charging_stations_read`: the DuckDB fixture gets some rows with `amenity='charging_station'`; `_fuel` on their box returns them with `r["amenity"] == "charging_station"`; still no bloom-filter read (reuse the fixture's read-range check).
  - `test_gasstations.test_osm_points_by_amenity`: rows `[{"id": 1, "amenity": "fuel", ...}, {"id": 2, "amenity": "charging_station", ...}]` → `_osm_points(FRAME, [rows])` ids `[1]`; with `amenity="charging_station"` ids `[2]`.
- [ ] **Step 2:** Run both; expect FAIL (no `amenity` key / unexpected keyword).
- [ ] **Step 3:** Implement: compare `r[1] in AMENITIES`, keep the amenity in the row; `osm_fuel_path` under `osmfuel_cells/v2`; `versions()` as above; `_osm_points` filter (a row without `"amenity"` counts as fuel).
- [ ] **Step 4:** Run `tests.test_osmfuel tests.test_osmfuel_tiles tests.test_gasstations`; expect PASS.
- [ ] **Step 5:** Commit `EV chargers: OpenStreetMap's charging stations read with its fuel stations (one pass, no more requests)`.

### Task 3: Charger sites from both sources

**Files:**
- Create: `server/evchargers.py`
- Modify: `server/gasstations.py` (`pins`: a listing `_is_ev` by name or brand is no fuel station)
- Test: `server/tests/test_evchargers.py` (reuse `FRAME`, `feats`, `box_ring`, `FakeMD`, `flat` from `test_gasstations.py` by import)

**Interfaces:**
- Consumes: `gasstations.MERGE_M`, `gasstations._is_ev`, `gasstations.classify`, `gasstations._osm_points(..., amenity="charging_station")`.
- Produces:
  - `@dataclass(frozen=True) class Charger: id: str; x: float; y: float; name: str; brand: str; records: int; big: bool; tesla: bool`
  - `NETWORK_WORDS` (regex): Tesla / Supercharger, Electrify America, Ionity, EVgo, Fastned, Shell Recharge, BP Pulse, Allego, EnBW, Aral pulse, Circle K charge, ChargePoint express... (start from `gasstations.EV_WORDS`).
  - `charger_pins(frame, layers) -> list[tuple[id, x, y, name, brand]]`: Overture places with `charging` in `basic_category` or `taxonomy`, or a gas listing whose name or brand `_is_ev`; closed ones out (`classify`'s `CLOSED`).
  - `merge(pins, osm, merge_m=MERGE_M) -> list[Charger]`: Overture pins and OSM points clustered within `merge_m`; id = smallest member id, stable across tiles; name from a named member (Overture first); `big = records >= 2 or NETWORK_WORDS matches name/brand`; `tesla` when name/brand says Tesla or Supercharger.

- [ ] **Step 1: Write the failing tests**
  - `test_overture_charger_pins`: places with `basic_category="ev_charging_station"` and one plain gas station → 1 pin.
  - `test_ev_gas_listing_is_a_charger`: a `gas_station` listing named "Shell Recharge" → in `charger_pins`, not in `gasstations.pins`.
  - `test_merge_across_sources`: Overture pin and OSM point 30 m apart → 1 `Charger`, `records == 2`, `big`.
  - `test_network_is_big`: one record named "Tesla Supercharger" → `big and tesla`; one unnamed OSM point → not big.
  - `test_merge_ids_stable`: the same inputs in another order → same ids.
- [ ] **Step 2:** Run `tests.test_evchargers`; expect FAIL (module missing).
- [ ] **Step 3:** Implement `evchargers.py` (signatures above) and the `pins` exclusion in `gasstations.py`.
- [ ] **Step 4:** Run `tests.test_evchargers tests.test_gasstations`; expect PASS (no gas station test may change).
- [ ] **Step 5:** Commit `EV chargers: charger sites from Overture's and OpenStreetMap's records, merged; a known network or two records is a big site`.

### Task 4: A charger site's layout

**Files:**
- Modify: `server/evchargers.py`
- Modify: `server/gasstations.py` (`style_shapes` adds the style's charger shapes)
- Test: `server/tests/test_evchargers.py`

**Interfaces:**
- Consumes: Task 1's model constants; `gasstations.Site`, `_clear`, `_yaw`, `service_lines`/`drive_lines` outputs (`[(line (k, 2), half_width)]`), `Bld`.
- Produces:
  - Constants: `CHARGER_GAP_M = 3.0`, `STALL_M = 5.5`, `AISLE_REACH_M = 30.0`, `ROW_BIG = 4`, `ROW_TESLA = 8`, `ROW_MAX = 8`, `ENERGY = ("electricEnergy",)`, `CHARGER_SHAPES = {"default": ..., "us_east": ..., "europe": ...}` (Task 1's picks).
  - `count_of(ch: Charger) -> int`: `ROW_TESLA` if `ch.tesla`; `min(ROW_MAX, max(ROW_BIG, 2 * ch.records))` if `ch.big`; else 2.
  - `layout(ch, blds, roads, service, style) -> gasstations.Site | None`: a straight row of `n` chargers `CHARGER_GAP_M` apart, each facing a stall `STALL_M` deep in front of it, along the nearest service line within `AISLE_REACH_M` of the pin (row parallel to it, stalls on the aisle side), else centred on the pin facing the nearest road. Every charger and stall corner `_clear`; if fewer than `n` fit, shorten the row down to 1 (small) or `ROW_BIG` … 1 (big); none: `None`. One `area` per charger centred in its stall (`half` = stall half size); `Site.pad` = one rectangle round chargers + stalls; `Site.station` = a `gasstations.Station` built from the charger (`confirmed=True`).
  - `reach_of(ch) -> float`: `AISLE_REACH_M + ROW_MAX * CHARGER_GAP_M / 2 + STALL_M`.

- [ ] **Step 1: Write the failing tests**
  - `test_big_row_along_aisle`: a service road 15 m from a big charger's pin in an open lot → 4 props, 4 areas, all stalls on the aisle side, chargers parallel to the aisle, pad covers all props and areas.
  - `test_tesla_row_of_eight`: same with a Tesla charger → 8.
  - `test_small_pair_at_pin`: no aisle within 30 m → 2 chargers at the pin facing the nearest road.
  - `test_shortened_when_tight`: walls leave room for 3 → 3 chargers.
  - `test_charger_in_garage_skipped`: the pin inside a building box with no clear spot within reach → `None`.
  - `test_never_on_a_road`: pin on a road centreline → every prop and area `_clear` (or `None`).
  - `test_style_shapes_have_chargers`: `gasstations.style_shapes(s)` contains `CHARGER_SHAPES[s]` for each style.
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests.test_evchargers tests.test_gasstations`; expect PASS.
- [ ] **Step 5:** Commit `EV chargers: a site's row of chargers along its aisle (or a pair at the pin), stalls in front, one small pad`.

### Task 5: Chargers in the road tiles

**Files:**
- Modify: `server/gasstations.py` (`tile_sites`)
- Test: `server/tests/test_evchargers.py`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces: `tile_sites(...)` returns charger records among its records: same keys as `_record` plus `"energy": ["electricEnergy"]`, id `"ev:" + charger.id`; their pads go to `pads` as `("ev:" + id, ...)`. A charger whose position is within `MERGE_M` of a laid-out fuel site of this tile's layouts is placed against that site's pad edge: its search starts from the nearest pad point instead of its pin (it stays its own record and POI, so the map shows a bolt for it and a pump for the station).

- [ ] **Step 1: Write the failing tests**
  - `test_tile_has_chargers`: `station_md()`-style FakeMD plus an `ev_charging_station` place → one record with `energy == ["electricEnergy"]`, and its pad in `pads`.
  - `test_charger_owned_by_one_tile`: a charger near a tile edge, `tile_sites` for both tiles → it is a record in exactly one; both tiles give it the same props.
  - `test_charger_beside_station`: a charger 30 m from the test station → its props within 12 m of the station's pad, none on the pad.
  - `test_chargers_without_data`: no places layer and `osm_fuel_cached` returning `None` → no error, no chargers, `revisit.faults()` grew.
  - `test_no_fuel_station_lost`: the existing `station_md()` station still gives the same record as before chargers existed.
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement in `tile_sites` after the fuel sites are chosen (`_one_per_shop`), with chargers' own `reach_of` for the tile-window test and `roads.box_owns` for ownership.
- [ ] **Step 4:** Run `tests.test_evchargers tests.test_gasstations tests.test_osmfuel_tiles tests.test_roads tests.test_roadgeo tests.test_protocol_agreement`; expect PASS except the three known failures (`test_bare_verge_beside_roads`, two `test_roadgeo` real-data tests).
- [ ] **Step 5:** Commit `EV chargers: the road tiles lay out the chargers near them (a charger by a gas station stands at its forecourt's edge)`.

### Task 6: The mod charges

**Files:**
- Modify: `mod/beamng_earth/lua/ge/extensions/beamngEarth/gasstations.lua` (`M.pois`: `energyTypes = r.energy or M.ENERGY`; `M.MATERIAL_FILES` += the charger models' materials files from Task 1; name fallback "EV charger" when unnamed)
- Test: `mod/tests/test_gasstations.lua`

**Interfaces:**
- Consumes: records with `energy` (Task 5).

- [ ] **Step 1:** Add to `mod/tests/test_gasstations.lua` a record with `energy = {'electricEnergy'}` and no name; check `els[k].data.facility.energyTypes[1] == 'electricEnergy'` and its name `'EV charger'`; the existing gas record still `'gasoline'`.
- [ ] **Step 2:** Run `luajit mod/tests/test_gasstations.lua`; expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it again; expect PASS.
- [ ] **Step 5:** Commit `EV chargers: the mod hands the stock gas station POI a charger's electric energy (the bolt icon, the charge prompt)`.

### Task 7: Measure and check in game

**Files:**
- Create (local, not committed): `.superpowers/gas-test-kit/ev_world.py` (as `cmp_world.py`, plus chargers)
- Modify: `server/README.md` (gas stations section: chargers, sources, `BNGE_OSM_FUEL`), `docs/ARCHITECTURE.md` if it lists the station record keys

- [ ] **Step 1:** Run the 64-place comparison before/after on the same code base: fuel stations laid out must be unchanged (0 lost, 0 changed); report chargers placed / skipped per region, big vs small, and per-tile layout time (Athens and Utrecht).
- [ ] **Step 2:** In game, cache on G:, normal and `BNGE_BUDGET=small`: a US Tesla Supercharger (find one in the data near Denver or LA), Berlin (both sources), Utrecht (225 unnamed: perf log hitches, spawn ms, objects), a charger beside a gas station. Charge an electric car at one; screenshot each.
- [ ] **Step 3:** If Utrecht hitches (worst frame over the gas stations' own), stop and report numbers before tuning.
- [ ] **Step 4:** Update `server/README.md`; commit `EV chargers: README`.
- [ ] **Step 5:** Draft the PR text in `.superpowers/pr_ev.md` (#502's style, measured numbers, screenshots); show the user; nothing pushed or posted without their go.
