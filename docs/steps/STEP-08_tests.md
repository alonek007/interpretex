# STEP-08 — Tests & Definition of Done

`tests/contracts/` and `tests/world/`; run with `.venv/bin/python -m pytest -q`.

## Tests
- `tests/contracts/test_fixtures_validate.py` — every fixture parses through its
  pydantic model; run trace has gapless `seq`, `run_started` first, `report_ready`
  last, `decision` before it, verdict `escalate`.
- `tests/contracts/test_agent_view_has_no_label.py` — `to_agent_view()` drops the
  label and world-side context.
- `tests/contracts/test_llm_cache.py` — `ScriptedLLM`/`build_llm` deterministic.
- `tests/world/test_world.py` — demo cases deterministic; tools never raise;
  **DoD severities** (clean no-above-low, explainable exactly one medium,
  suspicious ≥4 high dims, adversary no high); no verdict language in any output.

## Definition of Done (all met)
1. Four demo cases with the exact intended verdicts above.
2. Eight tools, case-scoped, `call()` never raises; partial args resolved from the
   case record.
3. Observations carry `severity` + numeric `metrics` + `sources`; **no verdict
   language**.
4. `AgentCaseView` strips label + context at the boundary.
5. Fixtures validate and the scripted run trace is replayable (SSE-ready).
6. `interpretex_contracts` installs with zero world dependencies.
7. `attack()` self-checks that no signal exceeds `high`.
8. Generators are deterministic (byte-stable).

## Known limitations (documented)
- C1 transit band upper bound is [15, 23] days, not the brief's "15–19", because
  Pacific Dawn's 16 kn speed widens it; a 17-day transit stays inside.
- Reference data is synthetic and scoped to this prototype; the three standard
  caveats are carried on every decision.
