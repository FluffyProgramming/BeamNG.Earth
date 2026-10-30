# Gas stations phase two: EV chargers, handoff (2026-10-30)

Working notes for continuing on another machine. **This whole `notes/` folder is one commit ("Notes: phase two
handoff ..."): drop it before the EV PR is posted** (`git rebase -i` is not needed: `git revert` or rebuild the branch
without that commit; or `git rm -r notes && git commit` on top before the rebase onto `dev`).

## Where things are

- **PR #502** (OSM fuel stations + wider pump search + travel centres): open, rebased on `dev` 1.7.2-beta (8375d51),
  head 47c414d on the fork's `feature/gas-station-coverage`, MERGEABLE. Waiting for TecnaGamer to merge.
- **This branch, `feature/ev-chargers`**: 11 commits on top of #502's 47c414d (EV chargers), plus this notes commit.
  Decision (2026-10-30): wait for #502 to merge, then rebase onto `dev` and post the EV PR. The PR text is
  `pr_ev.md` here; its `SCREENSHOT:` placeholders need the images pushed to a screenshots branch on the fork (like
  `pr-gas-coverage-screenshots`), and it needs the user's read and "post" before it goes up.
- Screenshots for the PR are on the Windows PC (scratchpad): `ev_barstow_supercharger.jpg`, `ev_berlin_street4.jpg`,
  `ev_berlin_charging.jpg` (and `ev_barstow_supercharger_wide.jpg`, `ev_berlin_post.jpg`). Re-take them in game if
  needed: Barstow CA Supercharger 34.849129, -117.085449 (a row of 8); Berlin e.on Drive kerb chargers near
  52.519355, 13.414760.

## What was built (see specs/2026-10-29-ev-chargers-design.md and plans/2026-10-29-ev-chargers.md)

- `server/evchargers.py`: charger sites from Overture (`ev_charging_station`, and gas listings named as chargers,
  `gasstations._is_ev`) and OSM `amenity=charging_station` (`osmfuel.py` reads both amenities in one pass; cells in
  `osmfuel_cells/v2`). Records within 60 m merge (seeded, no chaining). Big site = known fast network
  (`NETWORK_WORDS`) or 2+ records: a row of 4-8 (Tesla 8) along the nearest aisle with 5.5 m stalls and one asphalt pad.
  Street chargers: on the kerb 0.8 m behind the carriageway edge, the car parked at the road's edge, no pad, driveways
  kept clear (row slides along the kerb by whole spaces). Small: a pair. Skipped when nothing fits (garages).
- `gasstations.tile_sites` adds charger records with `"energy": ["electricEnergy"]`; a charger within 60 m of a
  laid-out station stands off its forecourt edge. Chargers use `buildings_touching` (by outline), stations keep
  `buildings_near` (by centre) so fuel layouts are unchanged.
- Mod `gasstations.lua`: `energyTypes = r.energy or M.ENERGY`, unnamed charger "EV charger", Italy's materials loaded.
- Probe `probes/ev_charger.lua`, findings `docs/research/2026-10-29-ev-chargers.md`. `CHARGER_DYAW = 90` measured in
  game (mod yaw 0 faces -y, 90 faces +x).

## Measured

- Gas stations unchanged: 64 places (Overture only), #502 code vs this branch: 963 of 969 identical; the 6 others are
  chargers Overture filed as gas stations (5 had wrongly got pumps).
- Chargers, 8 sample places (Denver, LA, Utrecht, Oslo, Berlin, Tokyo, Sao Paulo, Sydney): 236 of 267 sites laid out,
  634 chargers; with the driveway rule Utrecht+Berlin+Oslo 234 of 254. Skipped = pins inside buildings. ~4 ms a site
  warm, ~20 ms the first site of a cell.
- In game (0.40.3, BNGE_BUDGET=small): Barstow Supercharger row of 8; Berlin kerb chargers; an SBR `electric_500`
  charged 10 % -> 100 % at e.on Drive through the stock "Recharge Vehicle"; Utrecht dense: no charger hitches, 0 Lua
  errors.
- OSM charger counts were measured on 8 places only: 64 places' OSM cells are ~4800 requests, over OSM fuel's daily
  share (2500 of data.openstreetmap.us's 5000).

## Rulings made (cost if wrong)

- Merge is seeded at a site's first record (a street of poles doesn't chain) — two records of one big site 60-120 m
  apart become two sites.
- Kerbside charge areas overlap the road's edge (trigger only) — AI traffic passes close to a charging car.
- 2 records within 60 m = big (row of 4) — two nearby street poles become one row at the first pole.
- No US Supercharger in the 8 samples; Berlin's Supercharger pin is inside a building (skipped). Barstow checked later.
- test_style_shapes' fallback check excludes chargers (per style); test_never_on_a_road now checks the carriageway.
- Final review was a self-review (no reviewer agent without the user's ask).

## Deferred minors (follow-up PR candidates)

- Align charger rows with upstream's painted lot stalls (#442) / keep rows inside the mapped lot's edge.
- Street furniture (lamp posts) next to kerb chargers.
- A small site within 10 m of a road goes to the kerb even if the real charger is in a lot beside it.
- Italy's materials file loads in every region.

## Tests

```sh
cd server && python3 -m unittest tests.test_evchargers tests.test_gasstations tests.test_osmfuel tests.test_osmfuel_tiles -v
luajit mod/tests/test_gasstations.lua
```

Known failures that also fail on plain `dev` 1.7.2-beta (not ours): `test_bare_verge_beside_roads`, two
`test_roadgeo` RealDataTest (offline map data), `test_cache_in_the_mod`, and `test_roads.lua` "then the pending rebuild
runs". `test_protocol_agreement` `test_session_messages` times out only while the game + a server are running.

## Measure scripts (`measure/`)

`ev_sample.py <server dir>` (8 places: sites, laid out, skipped, ms), `ev_why.py` (why sites are skipped),
`cmp_world.py <server dir>` (54 cities' gas station layouts, diff two runs). They hard-code the Windows cache
`G:/BeamNGEarthCache`: change `C` / the MapData path for the laptop's cache. Run with `PYTHONIOENCODING=utf-8`.

## House rules (the user's)

- Never post a PR or comment until the user has read it and said "post".
- No Co-Authored-By / Claude lines in commits or PRs.
- Never name the user's home area in anything public; "the Pittsburgh area" at most.
- Design for the Steam Deck (memory-bound): measure with `BNGE_BUDGET=small`.
