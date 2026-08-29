# Part 1 — The World: Handoff

This package is **Part 1 — The World** of *Interpretex — AI Trade Investigation
Agent*. It owns everything that is *real* and *shared*: the synthetic reference
world, the document layer, the eight investigation tools, the adversary, and the
frozen `interpretex_contracts` package that Parts 2 (agent) and 3 (app) import.

## What is delivered

| Component | Location | Purpose |
|-----------|----------|---------|
| Frozen contracts | `packages/contracts/interpretex_contracts/` | The immutable interface (v1.0.0) Parts 2/3 code against |
| Reference world | `packages/world/interpretex_world/reference.py` + `data/*.json` | Commodities, ports, vessels, entities, history, networks |
| Document layer | `packages/world/interpretex_world/documents.py` | 8 documents rendered from one `Shipment` source of truth |
| Eight tools | `packages/world/interpretex_world/tools/` | `read_document`, `check_document_consistency`, `check_price_benchmark`, `check_vessel_capacity`, `check_transit_plausibility`, `check_historical_trade`, `check_counterparty_network`, `check_contract_or_supporting_evidence` |
| Adversary | `packages/world/interpretex_world/attacker.py` | Deterministic `case_adv_004` that beats naive single-signal screening |
| Public surface | `packages/world/interpretex_world/api.py` | The `WorldAPI` (`World` class) |
| Fixtures | `packages/contracts/interpretex_contracts/fixtures/` | Golden cases, tool specs, tool results, run trace |
| Generators | `packages/world/interpretex_world/{fixtures_gen,demo_trace}.py` | Rebuild fixtures deterministically |

## How to run

```bash
.venv/bin/pip install -e packages/contracts
.venv/bin/pip install -e packages/world
.venv/bin/python -m interpretex_world.fixtures_gen   # regenerate case/tool fixtures
.venv/bin/python -m interpretex_world.demo_trace     # regenerate the run trace
.venv/bin/python -m pytest -q                        # 26 tests
```

## Definition-of-Done status (all met)

- Four demo cases — `case_clean_001` (release), `case_explainable_002` (hold,
  one economic medium), `case_suspicious_003` (escalate, ≥4 high dimensions),
  `case_adv_004` (adversarial, all low/medium).
- Tools resolve partial args from the case record; `ToolRegistry.call` **never
  raises** (unknown tool / bad args / internal error all return `ok=False`).
- Observations carry `severity` + numeric `metrics` + `sources`; **no verdict
  language** appears in any tool `statement`/`summary`.
- `AgentCaseView` strips the label and world-side context at the agent boundary.
- Fixtures validate through their pydantic models; the scripted run trace has a
  gapless `seq`, `run_started` at 0, `report_ready` last, `decision` before it.
- `contracts` is installable standalone with **zero** world dependencies.

## Key design decisions

- **One source of truth.** Every anomaly mutates a `Shipment`; documents are
  re-rendered afterwards, so each anomaly is visible to *every* tool that should
  see it — never just one document's text.
- **Tools never decide.** A tool reports a quantified fact with a severity. The
  verdict lives only in the investigation `Decision`. The attacker case proves
  why: five low/medium signals, none damning alone, become informative together.
- **Transit band.** `band_low = ceil(D / (0.95·v·24))`,
  `band_high = floor(D / (0.60·v·24)) + 1`. Documented limitation: the C1 band
  upper bound is [15, 23] days vs the brief's "15–19" (a 17-day transit stays
  inside), because Pacific Dawn's 16 kn speed widens the band.
- **Network / contract-not-found.** Shared-UBO fires for the focal entity *and*
  its depth-2 counterparties. "No sales contract on file" is a `low` absence, not
  an accusation; "contract exists but lacks the claim" is `medium`.

## For Part 2 (agent)

Import `interpretex_contracts` and receive a `ToolRegistry` + `LLMClient` by
dependency injection. Use `CaseSummary` to list cases, `load_case` →
`to_agent_view()` to get the agent-safe view, then drive the tools. The scripted
trace in `fixtures/runs/case_suspicious_003.*` is a reference investigation you
can replay.

## For Part 3 (app)

Wire a `World` (this package) behind two env vars. Render `ToolResult`,
`NetworkView`, and `InvestigationResult` from the fixtures before the agent
exists. The event stream is SSE-ready (`helpers.sse_frame`).
