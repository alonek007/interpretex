# STEP-01 — Reference world

`packages/world/interpretex_world/reference.py` + `data/*.json`.

The reference world is a small, indexed, **in-memory** view over `data/*.json`
(commodities with 13-month benchmarks + volume tiers + plausible band, ports with
coordinates, vessels with `dwt`/`max_speed_knots`, entities with beneficial owners
+ sanctions status, historical trades, and cluster definitions).

Key methods used by the tools:
- `find_commodity`, `benchmark(month)`, `grade_multiplier`, `tier_for`
- `vessel(name)`, `find_port`, `distance_nm` (haversine), `transit_band(distance, speed)`
- `entity`, `entities_with_ubo`, `trades_for_entity`, `trades_for_broker`,
  `escalated_trades_for_broker`

`ReferenceWorld.default()` resolves the data directory from `$INTERPRETEX_DATA_DIR`
or by walking up from the module file — so `data/` can live at the repo root.

The transit band is documented as
`band_low = ceil(D / (0.95·v·24))`, `band_high = floor(D / (0.60·v·24)) + 1`.
Limitation: the C1 (coffee) band widens to [15, 23] days because Pacific Dawn's
16 kn speed is high; a 17-day transit stays inside. This is noted in the handoff.
