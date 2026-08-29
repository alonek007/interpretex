# STEP-03 — The eight tools

`packages/world/interpretex_world/tools/` + `registry.py`.

Each tool module exposes `SPEC: ToolSpec` and `run(registry, args) -> ToolOutcome`.
The registry closes over **one** `TradeCase` + the `ReferenceWorld`, so tool args
never carry a `case_id` and the agent cannot query the wrong case. Missing args
are resolved from the case record.

| Tool | Dimension(s) | What it proves / separates |
|------|--------------|----------------------------|
| `read_document` | documentary | what the paperwork states (catches internal doc errors) |
| `check_document_consistency` | documentary | per-field agreement across docs + insurance-after-shipment |
| `check_price_benchmark` | economic | under/over-invoicing vs monthly benchmark; shows volume-tier discount |
| `check_vessel_capacity` | physical | phantom/inflated shipment vs wrong vessel vs misstated qty |
| `check_transit_plausibility` | temporal/physical | impossible voyage vs date error vs transhipment |
| `check_historical_trade` | behavioural | "unusual for this customer" vs consistent prior pricing |
| `check_counterparty_network` | network | isolated tx vs structured network vs ordinary group |
| `check_contract_or_supporting_evidence` | documentary | supported by contract vs contradicts vs no contract on file |

Severity sits in `tools/base.py`: price (±band: none/low/med/high), capacity
(≤100 none, ≤105 low, ≤120 med, else high), transit (ratio to nearest edge),
z-score (≥4 high, ≥2.5 med, ≥1.5 low), network (broker escalation: ≥2 high,
1 med, else low). **No tool ever uses verdict language** — it reports a fact + a
number + a `severity`. The verdict is the agent's job (and lives only in `Decision`).
