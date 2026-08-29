# STEP-04 — The adversary

`packages/world/interpretex_world/attacker.py` + `demo.ATTACK_FALLBACK`.

`attack(spec, llm)` returns `case_adv_004`: the deterministic fallback that keeps
**every** individual signal low or medium, exactly so the demo shows why naive
single-signal screening misses a structured scheme:

- zinc under-invoiced 17.0% (under the 30% threshold) → `low`
- cargo at 96.0% of vessel capacity (under the 1.00 limit) → `low`
- transit at the fast edge of the plausible band, not impossible → `low`
- same-day insurance (lag 0 days, under the 3-day threshold) → `low`
- one fresh intermediary shared with a single prior held case → `low`

`attack()` runs a `_self_check` that re-runs the relevant tools and **warns** if
any signal lands `high` — a guard so a regression can never silently push the
attacker case into the high band. The LLM path is reserved; the deterministic
fallback is preferred for byte-stable fixtures.
