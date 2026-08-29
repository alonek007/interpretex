# STEP-06 — Fixtures

`packages/contracts/interpretex_contracts/fixtures/` (golden) +
`packages/world/interpretex_world/{fixtures_gen,demo_trace}.py` (generators).

Layout (normative):
```
fixtures/
  cases/case_*.json            full TradeCase incl. label
  tool_specs.json              all 8 ToolSpec
  tool_results/case_*.json     {tool_name: ToolResult}
  runs/case_*.events.jsonl     one InvestigationEvent per line
  runs/case_*.result.json      full InvestigationResult
```

`fixtures_gen.py` writes the 3 demo cases + tool specs + tool results (all 8 tools
× 3 cases) from the **real** world, so the fixtures are shaped exactly like live
output. `demo_trace.py` builds a full scripted `InvestigationResult` (54 events)
for `case_suspicious_003` that ends in `verdict: escalate`.

Regenerate (deterministic — byte-equal across runs):
```bash
.venv/bin/python -m interpretex_world.fixtures_gen
.venv/bin/python -m interpretex_world.demo_trace
```

`FixtureToolRegistry(case_id)` satisfies the `ToolRegistry` protocol entirely from
canned JSON, so Parts 2 and 3 build and render before the world exists. A fixture
that fails pydantic validation raises `FixtureError` — see `tests/contracts`.
