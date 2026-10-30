**Title:** EV chargers with charging (real chargers from Overture and OpenStreetMap, the stock charge prompt)

Hi! Players have been asking for EV charging. This places real charging stations with the game's own charger models, and an electric car charges there through the stock prompt, the same way #401's pumps refuel. Builds on #502 (it reuses its OpenStreetMap reader); I'll rebase onto `dev` once that's in.

## Charging uses the stock gas station module

A charger is the same `BeamNGGameplayArea` + `BeamNGPointOfInterest` pair as a pump, handed to `freeroam_gasStations` with `energyTypes = { 'electricEnergy' }` instead of gasoline and diesel. The stock module then shows the bolt icon (`poi_charge_round`) and the "Recharge Vehicle" prompt, and fills the battery (freeroam; career goes through `career_modules_fuel`). Checked with `probes/ev_charger.lua` and an SBR `electric_500`: 10 % → 100 %. Findings in `docs/research/2026-10-29-ev-chargers.md`.

## Where the chargers come from (`server/evchargers.py`)

- **Overture's places:** `ev_charging_station`, plus chargers Overture files as gas stations (Shell Recharge, BP Pulse, Allego...: `gasstations._is_ev`). Those no longer get pumps; with #502's code five of them in the test places did.
- **OpenStreetMap's `amenity=charging_station`:** read by #502's `osmfuel.py` in the same pass as the fuel stations, from the same columns, so no extra requests. The cached cells move to `osmfuel_cells/v2`.
- Records within 60 m are one site. Neither source says how fast a charger is or how many stalls it has, so the size comes from what is known: a known fast network (Tesla, Electrify America, Ionity, EVgo, Fastned...) or two or more records is a big site.

## Layout

- **Big site:** a row of 4–8 chargers (Tesla's 8) along the nearest parking aisle within 30 m, each facing a 5.5 m stall, one plain asphalt pad under it (the gas stations' pad store, no markings).
- **Street charger:** most chargers in European cities are on the kerb. They stand 0.8 m behind the carriageway's edge facing the road; the car charges parked along the road's edge. Driveways stay clear (the row slides along the kerb by whole spaces to find room). No pad, since road and sidewalk are paved already.
- **Otherwise** a pair at its position facing the nearest road. A row shortens to fit, clear of buildings and roads; a charger with no clear spot (inside a parking garage) is skipped.
- **By a gas station:** a charger within 60 m of a laid-out station stands off its forecourt's edge, as its own site and POI.
- **Models:** West Coast's 2020 / 2022 units, East Coast's in the US East, Italy's in Europe, preloaded per region like the pumps.

The records go out with the station records, with `"energy": ["electricEnergy"]`; the mod passes that to the stock POI. Chargers come and go with the gas stations; OpenStreetMap's with `BNGE_OSM_FUEL`.

![A Tesla Supercharger in Barstow, California: a row of 8](SCREENSHOT: ev_barstow_supercharger.jpg)

![Street chargers in Berlin, on the kerb](SCREENSHOT: ev_berlin_street4.jpg)

![Charging at e.on Drive's chargers in Berlin](SCREENSHOT: ev_berlin_charging.jpg)

## Checks

- **Unit tests:** `server/tests/test_evchargers.py` covers sites from both sources and their merge, sizes, the aisle row, the kerb, shortening, a charger in a garage, a long building over the pin, one record per site across tiles, a charger beside a station, and missing data. `test_osmfuel.py` reads charging stations without a bloom filter read. `mod/tests/test_gasstations.lua` checks a charger's energy reaching the stock POI.
- **Gas stations unchanged:** the 64 test places (54 cities and #401's 10 areas, 969 listings), #502 vs this branch: 963 laid out identically. The other 6 are the chargers filed as gas stations above.
- **Chargers, 8 sample places** (Denver, Los Angeles, Utrecht, Oslo, Berlin, Tokyo, São Paulo, Sydney): 236 of 267 sites laid out (88 %), 634 chargers; with the driveway rule, Utrecht, Berlin and Oslo went from 229 to 234 of 254. The skipped ones are pins inside buildings. A site's layout takes about 4 ms once its map cells are loaded (about 20 ms on the first site of a cell).
- **In game** (0.40.3, `BNGE_BUDGET=small`): a Tesla Supercharger in Barstow, CA, as a row of 8; Berlin's street chargers on the kerb; an electric car parked at e.on Drive's charged 10 % → 100 % through the stock prompt; Utrecht's dense chargers spawned with no hitches from them and no Lua errors.
