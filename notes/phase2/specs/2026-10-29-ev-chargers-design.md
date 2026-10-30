# EV chargers (gas stations phase two) — design

2026-10-29. Supersedes part F of `2026-10-26-gas-stations-phase-two-design.md` where they differ.

## Intent

Players are asking for EV charging: "real life ev stations mapped like the gas stations are but using beam assets to
have real recharging in the game" (the user, 2026-10-29). An electric car should be able to pull into a real charging
site and charge through the game's own prompt, the same way our pumps refuel today.

The picture to aim for is a **Tesla Supercharger**: a row of charging stalls in a parking lot. But the user wants
**as many chargers as possible** ("i would like as many chanrgers as possible"), so every charger in the data gets
placed, sized by what we know about it.

## Goals

- Every EV charging site that Overture or OpenStreetMap lists near the car is placed, with working charging.
- Big fast-charging sites look like it: a row of chargers.
- Everything else gets one or two chargers where it really is, in a clear spot.
- The world map / minimap show them with the game's charging (bolt) icon, as the stock POI does.

## Non-goals

- Charging speed, price, plug types. The game decides charging: in freeroam the stock prompt fills the battery at once
  (`freeroam/gasStations.lua` `refuelCar`: `setEnergyStorageEnergy` to `maxEnergy`); career goes through
  `career_modules_fuel`. The user: "speed of the charger does not matter as i am pretty sure it is istant in beam".
- Brand looks (no Tesla model exists in the game; stock chargers stand in).
- Home chargers, private chargers, chargers inside garages we can't reach.
- A station finder / GPS to the nearest charger (that's the phase-two finder PR).

## Anti-goals (would make it a failure even if it works)

- A single street pole turned into a fake 8-stall Supercharger.
- A charger inside a building, on a road or blocking a lane.
- Two chargers for one site because both sources list it.
- Dense places (Utrecht: 225 chargers within 1.5 km) causing hitches or memory growth, especially on the Steam Deck
  (`BNGE_BUDGET=small`; see memory "steam-deck-performance").

## What we know (recon, 2026-10-29)

**Game support.** `freeroam/gasStations.lua` (0.40.3) treats a station whose `energyTypes` contains `electricEnergy`
as a charger: charging translation (`recharge`), bolt icon (`poi_charge_round`, `cardIcon = "charge"`). Our mod's
stations are POIs built with `freeroam_gasStations.formatGasStationPoi` and `energyTypes = M.ENERGY` (`gasoline`,
`diesel`) in `mod/.../beamngEarth/gasstations.lua` `M.pois`; each pump is a `BeamNGGameplayArea` +
`BeamNGPointOfInterest`. A charger is the same pair with `energyTypes = {'electricEnergy'}`. To confirm with a probe
first (a stock-model charger + area + POI, an electric car, the prompt charges).

**Models** (levels zips, 0.40.3):
- East Coast USA: `levels/east_coast_usa/art/shapes/buildings/eca_charging_station`
- West Coast USA: `s_fuel_charger_car_2020`, `s_fuel_charger_car_2022`, `s_fuel_charger_concrete_base`
- Italy: `charging_station_a`, `charging_station_b`
- Hirochi / Motorsports Playground: `hr_charging_station`

**Data, 8 sample places, 1.5 km round the centre** (scratchpad `ev_count.py`, through the server's own readers):

| Place | Overture | OSM | in both (≤ 60 m) |
|---|---:|---:|---:|
| Denver | 5 | 0 | 0 |
| Los Angeles | 10 | 1 | 1 |
| Utrecht | 0 | 225 | 0 |
| Oslo | 15 | 41 | 12 |
| Berlin | 23 | 65 | 16 |
| Tokyo | 0 | 2 | 0 |
| São Paulo | 0 | 0 | 0 |
| Sydney | 1 | 4 | 1 |

- Overture: `basic_category` / `taxonomy` contain `charging` (`ev_charging_station`); brands like Shell Recharge,
  ChargePoint, Electrify America, SemaConnect, e.on Drive.
- OSM: `amenity = charging_station` in the same Layercake POIs file `osmfuel.py` reads (PR #502). Often unnamed
  (Utrecht: 211 of 225). No `capacity`, `socket:*` or power tags in that file, so **we can't tell fast from slow, or
  the stall count, from the data**.
- Neither source alone is enough; both are needed.

**Existing code.** `gasstations._is_ev` / `EV_WORDS` already spot chargers filed as gas stations (Shell Recharge, BP
Pulse, Superchargers, Ionity, Electrify America, ChargePoint, EVgo, Fastned, Allego...) and leave them out of the fuel
layouts "for phase two's EV part".

## Decided

- **Every charger is placed** (the user's choice). Size by what we know:
  - **Big site:** a known fast-charging network by name or brand (a list like `EV_WORDS`'s: Tesla Supercharger,
    Electrify America, Ionity, EVgo, Fastned, Shell Recharge, BP Pulse, Allego, ...), **or** several charger records
    merged into one site. Gets a **row of 4–8 chargers**.
  - **Everything else:** **1–2 chargers**.
  - (Agreed with the user: "yea yeah".)
- **Sources merged:** Overture + OSM; records within ~60 m are one site (as `MERGE_M`). A charger that's one of our
  gas stations' own listings (Overture filed it as a gas station) stops being dropped and becomes a charger site.
- **At a gas station:** a charger site within `MERGE_M` of a laid-out fuel station joins it: its chargers stand at the
  forecourt's edge instead of a separate site.
- **Placement:** clear of buildings and roads (the gas stations' `_clear` rules). A big site's row runs along the
  nearest parking aisle or service road within ~30 m of the pin; a small one stands at the pin, or at the nearest
  clear kerb/lot edge. No clear spot: skip (not forced).
- **No canopy. Ground paint at its minimum** (the user, 2026-10-29: "Ground paint minimum"): one plain asphalt
  patch per site, just covering the chargers and the parking spaces in front of them (a stall's depth, ~5.5 m), so a
  charger never stands on grass or dirt. No stall lines or markings. It goes through the gas stations' pad store
  (`keep_fuel_pads` / `surface.Surface.add_fuel_pads`, the blocks under it re-rendered), as one more small pad; where
  the ground is already paved it changes nothing visible.
- **Streaming:** the same as gas stations: laid out per road tile by the server's workers, only round the car,
  spawned within the mod's per-frame budget (`governor`), shapes preloaded per region only (`style_shapes` →
  `anchor_ready.fuelShapes`).
- **Model per region:** `style_of`: Europe → Italy's charger; US East → East Coast's; else → West Coast's 2022 charger
  (+ concrete base if it looks right). Builder picks a/b and the exact pick after seeing them in game.
- **On with the gas stations** (my call: upstream made gas stations always-on, c003c48; no separate switch). OSM
  chargers off with `BNGE_OSM_FUEL=0` as OSM fuel is.
- **One PR**, on top of PR #502 (it needs `osmfuel.py` and the merged station code); based on `dev` once #502 is in.

## Left to the builder

- The exact network list and the "several records = big site" threshold (start: 2+ merged records, or a listed
  network).
- Row length per site within 4–8 (e.g. from the merged record count; Superchargers 8).
- How chargers face (to the aisle), spacing (~3 m, a stall's width), and collision (charger mesh collidable; small).
- Gameplay area size per charger so the prompt fires parked beside it.
- Generalising `osmfuel.py` to read two amenities in one pass (same FIND columns, so no extra requests for step 1).
- Revisit-cache / versions handling: charger layouts follow the same rules as fuel (`station_cells`, `revisit.fault`
  on an unfetched OSM cell).
- Tests in the existing style (`test_gasstations.py`, `test_osmfuel*.py`), and a 64-place before/after count like
  #502's (chargers placed, lost fuel stations: must be 0).
- In-game checks: a Supercharger-like site in the US, Berlin or Oslo (dense, both sources), Utrecht (225 unnamed: cost
  and clutter), with `BNGE_BUDGET=small` too.

## Open risks

- **Density cost.** Utrecht-like places mean hundreds of small sites; measure spawn time, objects per tile, and the
  pads' cost to the ground painters (hundreds of small pads re-rendering photo blocks).
- **Chargers in garages.** OSM points inside a building's outline (parking garage) have no clear spot; they're skipped,
  which may drop real sites. Acceptable; count them in the 64-place run.
- **Stock POI with only `electricEnergy`:** confirm in game before building on it (probe).
