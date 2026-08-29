# The Frozen Contract (`interpretex_contracts`, v1.0.0)

Part 1's contract is **immutable for the hackathon**: if Part 2 or Part 3 need a
field, they ask Part 1 to bump the version, never edit it themselves. It has
**zero** dependency on `interpretex_world`, so it installs and validates alone.

## Layers

### 1. Enums (`enums.py`)
`DocType`, `Dimension`, `Severity`, `Stance`, `HypothesisKind`, `HypothesisStatus`,
`Verdict`, `CaseClass`, `AnomalyKind`, `SourceKind`, `EventType`. `CONTRACT_VERSION = "1.0.0"`.

### 2. Trade (`trade.py`)
`Entity`, `Vessel`, `Port`, `TradeDocument`, `TradeRecord`, `CaseLabel`,
`AgentCaseView`, `TradeCase`, `CaseSummary`, `CaseSpec`, `AttackSpec`.
`TradeCase.to_agent_view()` strips `label` + `entities` + `vessel` — the agent
must never read the intended verdict.

### 3. Investigation seam (`investigation.py`)
Tool side (Part 1 → Part 2): `SourceRef`, `Observation`, `ToolSpec`, `ToolResult`.
Reasoning (Part 2): `Triage`, `Hypothesis`, `EvidenceItem`, `PlanStep`,
`BudgetState`, `Corroboration`, `Decision`, `EvidenceRequest`, `EvidenceGraph`,
`GraphNode`, `GraphEdge`, `NetworkView`, `NetworkFinding`. Stream (Part 2 → Part
3): `InvestigationEvent`, `InvestigationResult`.

`Observation` fields: `observation_id`, `dimension`, `statement` (one factual
sentence, no verdict language), `severity`, `metrics` (all `float`), `sources`
(`SourceRef` with the normative `ref` format), `expected_range?`.
`ToolResult` fields: `tool`, `call_id`, `args`, `ok`, `summary` (≤200 chars),
`observations`, `raw`, `sources`, `cost_units`, `latency_ms`, `error?`.

### 4. Protocols (`protocols.py`)
`ToolRegistry` (case-scoped: `specs()`, `call(name, args)` never raises),
`LLMClient` (`complete`, `complete_json`), `WorldAPI` (the `api.World` surface),
`Investigator`. These are the *whole* interface surface — Part 2 imports none of
Part 1's code.

### 5. Helpers (`helpers.py`)
`IdCounter`, `SeqEmitter` (gapless `seq`), `sse_frame`/`sse_stream`, `Flags`
(`FEATURE_NETWORK`/`FEATURE_ATTACKER`/`FEATURE_HISTORICAL`, default on),
`STANDARD_CAVEATS` (carried on every decision).

### 6. LLM (`llm.py`)
`OpenRouterClient` + `ScriptedLLM` + `build_llm()` factory. `ScriptedLLM` is
offline-deterministic (`LLM_PROVIDER=scripted`). `complete_json` repairs partial
JSON before raising.

### 7. Fixtures (`fixtures.py`)
Loaders + `FixtureToolRegistry` from `fixtures/`: `cases/case_*.json` (full
`TradeCase`), `tool_specs.json`, `tool_results/case_*.json`, `runs/case_*.events.jsonl`
+ `.result.json`. A fixture that does not validate is worse than no fixture.

## SourceRef `ref` format (normative)
- documents: `"<doc_id>.<field>"` e.g. `"INV-2026-0912.unit_price"`
- reference world: `"<table>/<key>[/<as_of>]"` e.g. `"benchmarks/copper_cathode/2026-08"`
- derived: `"<tool>:<metric>"` e.g. `"check_price_benchmark:deviation_pct"`

## Tool names (stable order)
`read_document`, `check_document_consistency`, `check_price_benchmark`,
`check_vessel_capacity`, `check_transit_plausibility`, `check_historical_trade`,
`check_counterparty_network`, `check_contract_or_supporting_evidence`.
