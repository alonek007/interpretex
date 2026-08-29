# Interpretex — AI Trade Investigation Agent
## Master Plan: architecture, tech stack, work division and integration protocol

Repository: **https://github.com/alonek007/interpretex**
Branches: `main` · `part1-world` · `part2-agent` · `part3-app`
Contract version: **1.0.0** — frozen at T+2h
Build window: **24 hours**, three engineers, each driving an Opus-level coding agent on a separate machine.

---

## 1. What we are building, in one paragraph

Interpretex is an autonomous investigation layer for bank trade-finance and AML teams. It takes a complete trade-finance case file — letter of credit, commercial invoice, bill of lading, packing list, certificate of origin, insurance certificate — and, instead of merely scoring it, conducts an investigation: it reads the case, works out what is unusual, generates competing explanations for each anomaly (both innocent and illicit), decides which check would best discriminate between those explanations, calls that check, re-reads its own beliefs in light of the result, and repeats until the evidence is sufficient. It then issues an operational recommendation — **RELEASE**, **HOLD + request documentation**, or **ESCALATE / BLOCK** — accompanied by an auditable evidence graph in which every conclusion traces back to a named document field or reference-data lookup, a ledger of evidence both for and against the suspicion, the hypotheses it considered and how each fared, and a list of the specific documents the bank should request from the customer to close the remaining uncertainty.

Two pitch lines to use verbatim:

> "A trade can look perfectly consistent on paper and still not make sense in the real world. Our agent investigates the gap."

> "We are not building another system that flags suspicious trade transactions. We are building an AI investigator that decides what to investigate, tests competing explanations, correlates evidence across the trade and its real-world context, and produces an auditable recommendation for the bank."

---

## 2. Problem framing, and the positioning we must not get wrong

Trade-finance compliance systems already perform document matching, tampering detection, price anomaly checks, vessel and route checks, sanctions screening, counterparty screening, TBML red-flag rules and transaction monitoring. **We claim none of those individual checks as novel, and we never suggest banks lack them.** Any pitch that says "banks can't detect this" is factually wrong and a knowledgeable judge will destroy it.

The gap we target sits *after* detection. When a signal fires, a human investigator has to assemble a story: pull the documents, look up a market price, check whether the named vessel could physically carry the declared cargo, check whether the voyage could have happened in the claimed time, check what this customer has historically paid, check who else transacts through the same broker, decide whether an innocent explanation survives, decide what more to ask for, and write it all up defensibly. That connective reasoning is slow, inconsistent between investigators, and poorly documented. **That is the layer we automate.**

The consequence for design is that an anomaly is an input to investigation, never a conclusion. A price 20% below benchmark is not fraud; it is a question. The system's credibility rests on it being visibly willing to talk itself out of a suspicion.

---

## 3. Target user and the workflow being replaced

The persona is a bank trade-finance or AML investigator holding a case that a monitoring system has queued for review. Their current loop is: read documents → compare fields → research market price → research vessel → research route → research counterparties → review customer history → decide → write the report. Interpretex performs that loop and hands the investigator a dossier plus a recommendation. The human still decides; we are decision support, not a decision maker, and never a legal authority.

---

## 4. The core investigation loop

```
                     ┌──────────────────────────────┐
                     │  Trade case file (documents) │
                     └───────────────┬──────────────┘
                                     ▼
                        Extraction → canonical TradeRecord
                                     ▼
                    TRIAGE  what does this trade claim to be?
                            what looks unusual on its face?
                            what cannot be judged from paper alone?
                                     ▼
              HYPOTHESISE  for every anomaly, generate rival explanations
                           — at least one benign, at least one illicit
                                     ▼
          ┌───────────►  PLAN  which single check best discriminates
          │                    between the live hypotheses, per unit of
          │                    budget spent?  (record what you rejected)
          │                          ▼
          │                 ACT  call exactly that one tool
          │                          ▼
          │           INTERPRET  observation → evidence:
          │                      assign dimension, stance (supports /
          │                      refutes / neutral), weight, provenance
          │                          ▼
          │              UPDATE  move hypothesis posteriors; mark any
          │                      hypothesis refuted or supported
          │                          ▼
          │             ENOUGH?  corroborated across ≥2 independent
          └──────no───────┤       dimensions? benign explanation tested?
                          │       budget left? informative tool left?
                        yes▼
              CORROBORATE  are the supporting signals genuinely
                           independent of one another, or one cause
                           seen three times?
                                     ▼
                  DECIDE  deterministic policy gate over the ledger
                                     ▼
        ┌────────────────┬───────────────────────┬────────────────┐
     RELEASE       HOLD + request docs       ESCALATE / BLOCK
        └────────────────┴───────────┬───────────┴────────────────┘
                                     ▼
              Dossier: evidence graph · for/against ledger ·
              hypotheses · action timeline · typology · asks
```

The word that matters is **investigate**, not detect. Five properties make this loop real rather than cosmetic, and each must be visible in the demo:

**The tool sequence is not fixed.** The planner chooses the next check from the current evidence state. Case 1 should terminate in two or three calls; Case 3 should take five or six and in a different order.

**Rejected options are recorded.** Every plan step logs the tools it considered, the information gain it expected from each, and why it passed on them. This is what proves deliberation rather than a checklist.

**Benign hypotheses are tested, not just listed.** Escalation is blocked unless the agent actually spent a tool call trying to find the innocent explanation.

**Tools report facts; the agent assigns meaning.** No tool ever returns `fraud=true` or a risk score. A tool says "declared unit price is 38.2% below the August 2026 benchmark". Whether that supports or refutes suspicion is the agent's call, made in light of the other evidence.

**A deterministic policy makes the final call.** The LLM proposes; a hard-coded gate disposes. This is both the reproducibility mechanism for a live demo and the correct answer when a judge asks how you stop the model hallucinating an escalation.

---

## 5. System architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│ PART 3 · frontend/  React + Vite + TypeScript                          │
│  case selector │ live timeline │ hypothesis board │ FOR/AGAINST ledger │
│  evidence graph │ network graph │ budget meter │ decision │ dossier    │
└───────────────────────────────┬────────────────────────────────────────┘
                       HTTP + Server-Sent Events
┌───────────────────────────────┴────────────────────────────────────────┐
│ PART 3 · packages/app/  FastAPI                                        │
│  /api/cases  /api/runs  /api/runs/{id}/events (SSE)  /api/attack       │
│  /api/network  /api/tools  wiring.py: real ⇄ stub dependency injection │
└──────────────┬──────────────────────────────────────┬──────────────────┘
               │ WorldAPI                             │ Investigator
┌──────────────┴───────────────────┐  ┌───────────────┴──────────────────┐
│ PART 1 · packages/world/         │  │ PART 2 · packages/agent/         │
│                                  │  │                                  │
│  reference world (JSON)          │  │  triage                          │
│   benchmarks · vessels · ports   │  │  hypothesis engine               │
│   entities · history · networks  │  │  planner (info gain + budget)     │
│  case generator + ground truth   │  │  tool dispatch + recovery        │
│  document renderer (6 doc types) │  │  evidence ledger (stance/weight) │
│  extraction → TradeRecord        │  │  corroboration analyser          │
│  ── 8 investigation tools ──────►│  │  decision policy gate            │
│   ToolRegistry.specs()/.call()   │  │  evidence-request generator      │
│  attacker agent (adversarial)    │  │  evidence graph builder          │
│  network intelligence            │  │  dossier writer · event emitter  │
│                                  │  │  eval harness                    │
└──────────────┬───────────────────┘  └───────────────┬──────────────────┘
               │                                      │
               └──────────────┬───────────────────────┘
                              ▼
        ┌─────────────────────────────────────────────────┐
        │ MAIN · packages/contracts/  (owner: Part 1)     │
        │  pydantic models · enums · Protocols            │
        │  OpenRouter LLM adapter + cassette cache        │
        │  golden fixtures (3 cases, tool results, trace) │
        │ MAIN · stubs/ + wiring.py   (owner: Part 3)     │
        └─────────────────────────────────────────────────┘
```

The load-bearing architectural decision: **Part 2 imports nothing from Part 1.** The agent receives a `ToolRegistry` and an `LLMClient` by dependency injection, both defined as `typing.Protocol` in the shared contracts package. Part 3 is the only place the two are wired together, and that wiring is a single file that reads two environment variables. Integration on hour 10 is therefore `INTERPRETEX_WORLD=real INTERPRETEX_AGENT=real`, not a refactor.

---

## 6. Tech stack (locked — do not deviate on a branch)

| Layer | Choice | Why this and not the obvious alternative |
|---|---|---|
| Language (backend) | Python 3.11 | One language across world, agent and API. |
| Models / schemas | pydantic v2 | Validation *is* the contract; `extra="forbid"` catches field drift the moment it happens rather than at hour 10. |
| LLM provider | **OpenRouter**, OpenAI-compatible REST over raw `httpx` | Model id is one env var. Raw HTTP over an SDK because tool-calling / `response_format` support is inconsistent across OpenRouter's alpha and stealth models, and a dependency bump at 03:00 is how demos die. |
| Model | `LLM_MODEL` env var, set to the OpenRouter slug for **Ox Alpha** | **Verify the exact slug on https://openrouter.ai/models in hour 0 and paste it into the shared `.env`.** All three machines must use the identical string. |
| Structured output | Strict-JSON prompting + local JSON-Schema validation + a re-prompt repair loop | Portable across every OpenRouter model. Does not depend on native function calling being present. |
| LLM determinism | On-disk cassette cache keyed by a hash of (model, system, messages, temperature, max_tokens) | `LLM_CACHE_MODE=read` on stage: zero network, zero rate limits, zero latency, byte-identical run. This is the single highest-value 40 lines in the repo. |
| Agent framework | **None.** Hand-rolled loop, ~200 lines | A framework buys nothing here and costs debuggability. We need to *show* the reasoning trace; owning the loop means the trace is a first-class output rather than something scraped from callbacks. Say this out loud to judges — it is a deliberate choice, not naivety. |
| API | FastAPI + uvicorn | SSE from a plain generator with no extra machinery. |
| Streaming | Server-Sent Events, `text/event-stream` | One-directional, survives proxies, `EventSource` reconnect and `Last-Event-ID` resume come free. WebSockets add a protocol for no benefit. |
| Frontend | Vite + React 18 + TypeScript | Chosen for stage presence. Accepted cost: a real HTTP contract, which is why Part 3 owns both sides of it. |
| Styling | Tailwind CSS | No design-system bikeshedding at hour 15. |
| Frontend state | `useReducer` over the event stream + TanStack Query for REST | The event stream is literally a reducer input; do not reach for Redux. |
| Graph rendering | **React Flow** for the evidence graph and the network graph | Dagre or ELK for layout. D3 force layouts look impressive and read as noise on a projector. |
| Motion | framer-motion, sparingly | Evidence nodes fade in as they are discovered — that single effect carries the demo. |
| Reference data | Plain JSON files loaded into memory, indexed at import | SQLite adds migration friction for zero demo value. Nothing here needs a query planner. |
| Tests | pytest, plus one Playwright smoke test if time allows | |
| Packaging | Monorepo, one venv, four editable installs | `pip install -e packages/contracts -e packages/world -e packages/agent -e packages/app` |
| Reproducibility | Every generator and the agent take a `seed` | Same seed ⇒ same case ⇒ same run. Judges will ask. |

**Python dependency floor:** `pydantic>=2.6`, `httpx>=0.26`, `jsonschema>=4.21`, `fastapi>=0.110`, `uvicorn[standard]>=0.29`, `python-dotenv`, `pytest`, `rich`.
**Frontend:** `react`, `react-dom`, `typescript`, `vite`, `tailwindcss`, `reactflow`, `dagre`, `@tanstack/react-query`, `framer-motion`, `react-markdown`, `lucide-react`.

---

## 7. How the work divides, and why this way

Three candidate splits were considered. Splitting by *vertical slice* (each person owns pricing, or physical, or network, end-to-end) balances effort but puts three people inside the agent loop and inside the UI simultaneously, which is a merge-conflict generator. Splitting by *demo case* guarantees three working demos but triples the shared core. The chosen split is **by layer**, because the three layers have naturally narrow seams that can be written down completely in advance, and because it gives every part an independent critical path.

| | **Part 1 — World & Adversary** | **Part 2 — Investigator Core** | **Part 3 — Interface & Demo** |
|---|---|---|---|
| Branch | `part1-world` | `part2-agent` | `part3-app` |
| Owns | `packages/contracts/`, `packages/world/`, `data/` | `packages/agent/`, `agent_prompts/` | `packages/app/`, `frontend/`, `stubs/`, `wiring.py`, `scripts/` |
| Character of work | Broad, mechanical, front-loaded | Deep, novel, highest risk | Broad, visual, integration-facing |
| Advanced feature | Attacker agent, network intelligence data | Investigation budget + information gain, eval harness | Network graph view, budget meter, reveal mode |
| Depends on | Nothing | `ToolRegistry` protocol + fixtures | Both, via two protocols |
| Blocks | Everyone (owns contracts + fixtures) | Part 3's live mode | Nobody |

Two deliberate rebalancing decisions are worth stating, because they are the difference between this working and not:

**The attacker agent belongs to Part 1, not Part 3.** Its job is to craft an evasive case, which means driving the case generator's knobs — that is Part 1's domain, it needs no new interface, and Part 1's work front-loads so Part 1 has capacity late.

**Part 1 owns the shared contracts package and the golden fixtures.** One owner for all shared data shapes. Part 1 publishes `packages/contracts/` to `main` by T+1.5h and the v0 fixtures by T+3h, before touching its own branch. Everything downstream keys off this, so it is the only genuinely serialising dependency in the plan, and it is deliberately placed in hour one when nobody is tired.

### Critical path

```
T+0   T+1.5        T+3      T+5           T+10              T+14        T+18
 │      │           │        │              │                 │           │
 P1 ──contracts──fixtures──┬─tools 1-3──┬──tools 4-8────┬──attacker───┬─freeze
 │                         │            │  network data │             │
 P2 ──prompt design────────┴─loop on ───┴──ledger +─────┴──budget +───┤
 │    + policy spec          own fakes     decision        eval       │
 │                                                                    │
 P3 ──app shell + TS types─┬─FastAPI +──┬──all panels────┬──network───┤
                           │  stubs+SSE │                │  graph     │
                        WINDOW 1     WINDOW 2         WINDOW 3
                        (30 min)     (60 min)         (45 min)
                                     ▲ MVP GATE
```

Nobody is ever blocked, because each part codes against the other parts' *protocols* and against fixtures, never against their implementations.

---

## 8. The frozen contract

Everything below is authored by Part 1 into `packages/contracts/interpretex_contracts/` on `main` and imported by all three parts. `extra="forbid"` on every model. **Field names in this section are normative — copy them exactly.**

### 8.1 Closed vocabularies (enums)

| Enum | Members |
|---|---|
| `DocType` | `letter_of_credit`, `commercial_invoice`, `bill_of_lading`, `packing_list`, `certificate_of_origin`, `insurance_certificate`, `inspection_certificate`, `sales_contract` |
| `Dimension` | `economic`, `physical`, `temporal`, `documentary`, `behavioural`, `network` |
| `Severity` | `none`, `low`, `medium`, `high` — *deviation salience emitted by a tool, never a fraud verdict* |
| `Stance` | `supports_suspicion`, `refutes_suspicion`, `neutral` — *assigned by the agent only* |
| `HypothesisKind` | `benign`, `suspicious` |
| `HypothesisStatus` | `open`, `supported`, `weakened`, `refuted`, `untestable` |
| `Verdict` | `release`, `hold`, `escalate` |
| `CaseClass` | `clean`, `suspicious_but_legitimate`, `illicit`, `adversarial` — *ground truth, never shown to the agent* |
| `AnomalyKind` | `under_invoicing`, `over_invoicing`, `capacity_exceeded`, `impossible_transit`, `insurance_after_shipment`, `description_drift`, `quantity_mismatch`, `hs_code_mismatch`, `route_deviation`, `historical_deviation`, `intermediary_reuse`, `shared_ownership`, `none` |
| `SourceKind` | `document`, `reference_db`, `derived`, `model` |
| `EventType` | `run_started`, `case_loaded`, `triage`, `hypotheses_updated`, `plan_step`, `tool_call_started`, `tool_call_completed`, `evidence_added`, `graph_updated`, `budget_updated`, `corroboration`, `decision`, `evidence_requested`, `report_ready`, `run_failed`, `heartbeat` |

`Dimension` is load-bearing, not decorative: corroboration is *defined* as suspicion-supporting evidence appearing in two or more distinct dimensions.

### 8.2 World-side models

**`Entity`** — `entity_id`, `name`, `country` (ISO-2), `role` (`buyer|seller|broker|vessel_owner|insurer|intermediary`), `incorporated_on?`, `registry_id?`, `ultimate_beneficial_owners: list[str]`, `sanctions_status` (`not_listed|match|near_match|unknown`), `notes?`

**`Vessel`** — `vessel_name`, `imo?`, `dwt_tons` (max cargo capacity), `vessel_type`, `max_speed_knots`, `flag?`, `owner_entity_id?`

**`Port`** — `port_code` (UN/LOCODE, e.g. `SGSIN`), `name`, `country`, `lat`, `lon`

**`TradeDocument`** — `doc_id`, `doc_type: DocType`, `issuer`, `issue_date`, `fields: dict[str, Any]`, `raw_text: str`, `extraction_confidence: float`
> `fields` keys must use the canonical `TradeRecord` names wherever the concept exists there, so cross-document comparison is a dict intersection rather than a mapping exercise. `raw_text` is what OCR would return. Where the two disagree, that disagreement is itself a documentary signal — never silently reconcile them.

**`TradeRecord`** — the canonical normalised view:
`commodity`, `commodity_grade?`, `hs_code?`, `quantity`, `unit`, `unit_price`, `currency`, `total_value`, `incoterm?`, `exporter_id`, `importer_id`, `broker_id?`, `insurer_id?`, `vessel_name?`, `imo?`, `container_count?`, `gross_weight_tons?`, `origin_port?`, `destination_port?`, `ship_date?`, `arrival_date?`, `lc_issue_date?`, `insurance_issue_date?`, `lc_number?`, `bl_number?`, `contract_reference?`
> When documents disagree, hold the LC/invoice value here and surface the disagreement as an observation.

**`CaseLabel`** (ground truth) — `case_class: CaseClass`, `injected_anomalies: list[AnomalyKind]`, `expected_verdict`, `benign_explanation?`, `evasion_notes?`, `generator_seed?`

**`AgentCaseView`** — `case_id`, `received_at`, `bank_reference?`, `applicant_note?`, `documents: list[TradeDocument]`, `record: TradeRecord`, `available_tool_names: list[str]`
> **This type has no `label` field, by design.** Part 2's entry point accepts `AgentCaseView`, so ground-truth leakage is a type error rather than a code-review question.

**`TradeCase`** — everything in `AgentCaseView` plus `title`, `entities: list[Entity]`, `vessel?`, `label: CaseLabel|None`, and a method `to_agent_view() -> AgentCaseView` that strips the label. **Call it at every agent boundary.**

**`CaseSummary`** (case-selector row) — `case_id`, `title`, `commodity`, `quantity`, `unit`, `total_value`, `currency`, `exporter_name`, `importer_name`, `origin_port?`, `destination_port?`, `document_count`, `received_at`, `is_adversarial`

**`CaseSpec`** (generation recipe) — `case_class`, `commodity?`, `quantity?`, `exporter_id?`, `importer_id?`, `anomalies: list[AnomalyKind]`, `anomaly_magnitudes: dict[str, float]`, `benign_explanation?`, `plant_supporting_contract: bool`, `seed: int`

**`AttackSpec`** — `known_thresholds: dict[str, float]`, `max_dimensions: int`, `target_stealth: float`, `seed: int`

### 8.3 Tool-layer models — the Part 1 → Part 2 seam

**`SourceRef`** — `kind: SourceKind`, `ref: str`, `value?`, `as_of?`, `label?`
`ref` locator format is normative: documents `"<doc_id>.<field>"` e.g. `"INV-2026-0912.unit_price"`; reference world `"<table>/<key>[/<as_of>]"` e.g. `"benchmarks/copper_cathode/2026-08"`; derived `"<tool>:<metric>"` e.g. `"check_price_benchmark:deviation_pct"`.

**`Observation`** — `observation_id`, `dimension: Dimension`, `statement: str`, `severity: Severity`, `metrics: dict[str, float]`, `sources: list[SourceRef]`, `expected_range?`
`statement` is one factual quantified sentence with no verdict language. `metrics` must carry the numbers behind the statement so the UI and report never re-parse prose.

**`ToolSpec`** — `name`, `description`, `dimensions: list[Dimension]`, `args_schema: dict` (JSON Schema), `cost_units: int`, `discriminates: list[str]`
`description` is rendered straight into the planner prompt, so it must state *what evidence this yields and which hypotheses it separates* — not how it is implemented.

**`ToolResult`** — `tool`, `call_id`, `args`, `ok: bool`, `summary: str` (≤200 chars, the first thing the planner reads), `observations: list[Observation]`, `raw: dict` (UI drill-down), `sources: list[SourceRef]`, `cost_units`, `latency_ms`, `error?`
> **`ToolRegistry.call()` must never raise.** Unknown tool, bad args and internal failure all return `ok=False` with `error` set, so the agent can recover and re-plan. That recovery path is demoed, so it has to work.

**`ToolRegistry` protocol** — `specs() -> list[ToolSpec]` (stable order) and `call(name, args) -> ToolResult`. Case-scoped: the registry closes over one case, so tool args never carry a `case_id` and the agent cannot query the wrong case.

### 8.4 The eight tools

| Tool | Args | Dimensions | Cost | Yields |
|---|---|---|---|---|
| `read_document` | `doc_type` or `doc_id` | documentary | 1 | Structured fields plus raw text for one document |
| `check_document_consistency` | `fields?: list[str]` | documentary | 1 | Per-field agreement across the whole set; description drift; quantity and HS-code mismatches |
| `check_price_benchmark` | `commodity`, `grade?`, `quantity`, `as_of_date`, `declared_unit_price` | economic | 1 | Benchmark, band, deviation %, and any applicable volume-tier guidance |
| `check_vessel_capacity` | `vessel_name`, `claimed_weight_tons` | physical | 1 | `dwt_tons`, claimed load, utilisation %, excess tons |
| `check_transit_plausibility` | `origin_port`, `destination_port`, `ship_date`, `arrival_date`, `vessel_name?` | temporal, physical | 1 | Great-circle distance, expected transit band at vessel speed, claimed transit, implied speed in knots |
| `check_historical_trade` | `entity_id`, `commodity`, `lookback_months?` | behavioural | 2 | Prior trades for this entity: price range, median, quantity range, counterparties, z-score of the current price |
| `check_counterparty_network` | `entity_id`, `depth?` | network | 2 | Shared intermediaries, shared UBOs, repeated vessels, co-occurring cases, prior escalations |
| `check_contract_or_supporting_evidence` | `claim: str` (`bulk_discount`, `grade_difference`, `distressed_sale`, `long_term_offtake`, `inspection`) | economic, documentary | 1 | Whether a document in the file supports the claimed commercial explanation, with the clause quoted, or an explicit not-found |

Optional if time allows: `check_sanctions_and_entity(entity_id)` and `check_container_volume_consistency(commodity, quantity, container_count)`.

Exhaustive cost of one call to each of the eight is **10 units**. Default budget is **6**. The gap is the efficiency story.

### 8.5 Reasoning models — internal to Part 2, rendered by Part 3

**`Triage`** — `trade_narrative` (2–4 plain sentences), `initial_concerns: list[str]`, `unknowns: list[str]`, `dimensions_to_probe: list[Dimension]`

**`Hypothesis`** — `hypothesis_id` (`H1`…), `kind: HypothesisKind`, `statement`, `explains: list[Dimension]`, `prior: float`, `posterior: float`, `status: HypothesisStatus`, `discriminating_evidence_needed: list[str]`, `supporting_evidence_ids`, `contradicting_evidence_ids`, `rationale?`

**`EvidenceItem`** — `evidence_id` (`E1`…), `dimension`, `stance: Stance`, `statement`, `weight: float` (agent-assigned strength, not a probability), `severity`, `hypotheses_affected: list[str]`, `observation_ids: list[str]`, `tool_call_id?`, `sources: list[SourceRef]`, `interpretation?` (one line: why this stance, given the alternatives)

**`PlanStep`** — `step: int`, `reasoning`, `chosen_tool: str|None` (`None` means stop), `chosen_args`, `targets_hypotheses: list[str]`, `expected_information_gain: float`, `considered: list[{tool, expected_information_gain, why_not}]`, `stop_reason?` (`sufficient_evidence` | `budget_exhausted` | `no_informative_tool_left`)

**`BudgetState`** — `limit`, `spent`, `remaining`, `calls_made`, `tools_skipped: list[{tool, reason}]`, `exhaustive_cost?`

**`Corroboration`** — `corroborated_dimensions: list[Dimension]`, `independent_signal_count`, `refuting_dimensions`, `strongest_benign_hypothesis?`, `strongest_benign_posterior`, `narrative` (why these signals are or are not independent of one another)

**`Decision`** — `verdict: Verdict`, `confidence: float`, `headline` (readable in two seconds), `rationale` (3–6 sentences citing evidence ids), `corroboration: Corroboration`, `typology?`, `caveats: list[str]`, `decisive_evidence_ids: list[str]`

**`EvidenceRequest`** — `item`, `why`, `resolves_hypotheses: list[str]`, `priority: 1..3`

**`GraphNode`** — `id`, `kind` (`document|field|reference|tool|finding|dimension|hypothesis|decision|entity|vessel`), `label`, `dimension?`, `stance?`, `severity?`, `meta`
**`GraphEdge`** — `source`, `target`, `relation` (`states|compared_with|produced|supports|refutes|corroborates|concludes|linked_to`), `label?`
**`EvidenceGraph`** — `nodes`, `edges`. Every finding must be reachable from a source node; the graph is a provenance DAG, not a picture.

**`NetworkFinding`** — `finding_id`, `pattern` (`intermediary_reuse|shared_ownership|vessel_reuse|circular_trade|price_pattern`), `statement`, `entity_ids`, `case_ids`, `severity`, `metrics`
**`NetworkView`** — `focus_entity_id?`, `nodes`, `edges`, `findings`

### 8.6 The event stream — the Part 2 → Part 3 seam

**`InvestigationEvent`** — `seq: int`, `ts: datetime`, `run_id: str`, `type: EventType`, `narration: str`, `payload: dict`
`narration` is a single human-readable line; the timeline must be renderable from `narration` alone, so the UI degrades gracefully if a payload shape surprises it.

| `type` | `payload` keys |
|---|---|
| `run_started` | `case_id`, `budget`, `model`, `flags`, `contract_version` |
| `case_loaded` | `record`, `document_ids`, `applicant_note` |
| `triage` | `triage` |
| `hypotheses_updated` | `hypotheses`, `changed_ids` |
| `plan_step` | `plan_step` |
| `tool_call_started` | `call_id`, `tool`, `args`, `targets_hypotheses` |
| `tool_call_completed` | `tool_result` |
| `evidence_added` | `evidence` |
| `graph_updated` | `nodes_added`, `edges_added` |
| `budget_updated` | `budget` |
| `corroboration` | `corroboration` |
| `decision` | `decision` |
| `evidence_requested` | `requests` |
| `report_ready` | `result` (full `InvestigationResult`), `report_markdown` |
| `run_failed` | `error`, `stage`, `degraded` |
| `heartbeat` | *(empty)* |

Ordering guarantees, part of the contract: `seq` starts at 0 and increments by exactly 1 with no gaps; `run_started` is always `seq` 0; the stream always terminates with `report_ready` or `run_failed`; a `tool_call_completed` always follows its matching `tool_call_started`; `decision` always precedes `report_ready`.

Wire format, so it cannot drift from the model:
```
id: <seq>
event: <type>
data: <event as JSON>

```
`id:` carrying `seq` gives `EventSource` `Last-Event-ID` resume for free.

**`InvestigationResult`** — `meta: RunMeta`, `record`, `triage`, `hypotheses`, `plan_steps`, `tool_calls`, `evidence_for`, `evidence_against`, `evidence_neutral`, `budget`, `graph`, `decision`, `evidence_requests`, `report_markdown`, `events` (full replayable trace)
**`RunMeta`** — `run_id`, `case_id`, `started_at`, `finished_at?`, `model`, `llm_calls`, `prompt_tokens`, `completion_tokens`, `wall_ms`, `replayed: bool`, `degraded: bool`

### 8.7 Entry-point signatures — the three seams

```python
# PART 1 — packages/world/api.py
list_cases()            -> list[CaseSummary]
load_case(case_id)      -> TradeCase                      # KeyError if unknown
generate_case(spec)     -> TradeCase                      # deterministic on (spec, seed)
build_tool_registry(case) -> ToolRegistry
network_view(entity_id=None, depth=2) -> NetworkView
attack(spec, llm=None)  -> TradeCase                      # deterministic fallback if llm is None

# PART 2 — packages/agent/api.py
investigate_stream(case: AgentCaseView, tools: ToolRegistry, *,
                   llm=None, budget=6, seed=None) -> Iterator[InvestigationEvent]
investigate(case, tools, *, llm=None, budget=6, seed=None,
            emit=None) -> InvestigationResult             # blocking wrapper

# SHARED — interpretex_contracts.llm
complete(*, system, messages, temperature=0.2, max_tokens=2048, tag="") -> str
complete_json(*, system, messages, schema, temperature=0.1,
              max_tokens=2048, tag="", retries=2) -> dict
```

`investigate_stream` must be a generator so Part 3 streams straight to SSE with no queue and no thread. Its final yielded event is `report_ready`, whose `payload["result"]` is the full result serialised with `model_dump(mode="json")`.

### 8.8 HTTP surface (Part 3 owns; the other two must know it)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{status, contract_version, model, flags, world, agent}` |
| GET | `/api/flags` | feature-flag map |
| GET | `/api/tools` | `ToolSpec[]` |
| GET | `/api/cases` | `CaseSummary[]` |
| GET | `/api/cases/{case_id}` | `AgentCaseView` (label-stripped) |
| GET | `/api/cases/{case_id}/label` | `CaseLabel` — judge reveal, 409 until a run has completed |
| GET | `/api/cases/{case_id}/documents/{doc_id}` | `TradeDocument` including `raw_text` |
| POST | `/api/runs` | `{run_id}` — body `{case_id, budget?, mode: live\|replay, seed?}` |
| GET | `/api/runs/{run_id}/events` | **SSE** stream of `InvestigationEvent` |
| GET | `/api/runs/{run_id}` | `InvestigationResult` |
| GET | `/api/runs/{run_id}/report.md` | `text/markdown` |
| GET | `/api/runs/{run_id}/baseline` | `{agent_cost, exhaustive_cost, agent_verdict, baseline_verdict, tools_skipped}` |
| POST | `/api/attack` | `{case_id}` — body `{max_dimensions, target_stealth, seed}` |
| GET | `/api/network?entity_id=&depth=` | `NetworkView` |

### 8.9 The decision policy gate (deterministic, owned by Part 2)

The LLM produces evidence, stances, weights and posteriors. The verdict is then computed by fixed rules over that ledger:

**ESCALATE** requires all of: suspicion-supporting evidence at `severity >= medium` in **two or more distinct dimensions**; no benign hypothesis with `posterior >= 0.6`; and at least one tool call whose `targets_hypotheses` included a benign hypothesis — i.e. the agent actually *tried* to find the innocent explanation.

**RELEASE** requires: no suspicion-supporting evidence above `low`, **or** every `medium`+ signal is matched by a refuting evidence item in the same dimension with `weight >= 0.6`.

**Otherwise HOLD**, and `evidence_requests` must be non-empty.

Two hard rules, and they are the credibility of the whole project:

1. **Single-dimension anomalies can never escalate.** One anomalous dimension caps the verdict at HOLD, however extreme the deviation. This is what produces Case 2's behaviour and it is the direct answer to "isn't this just a threshold with extra steps".
2. **No escalation without a tested benign hypothesis.** If no tool call ever targeted a benign explanation, the verdict is capped at HOLD regardless of the evidence.

If the policy and the LLM's own suggested verdict disagree, **the policy wins** and the disagreement is recorded in `decision.rationale`. Say this to judges; it is the strongest single answer you have on reliability.

---

## 9. Repository layout and file ownership

```
interpretex/
├── README.md                     main
├── .env.example                  main
├── Makefile                      P3
├── docker-compose.yml            P3          (optional)
├── requirements.txt              main
├── docs/
│   ├── 00_MASTER_PLAN.md         main        ← this document
│   ├── 10_CONTRACTS.md           P1          generated field reference
│   ├── 20_DEMO_SCRIPT.md         P3
│   ├── 30_CLAIMS.md              main
│   └── diagrams/                 P3
├── prompts/
│   ├── PART1_WORLD.md            main
│   ├── PART2_AGENT.md            main
│   └── PART3_APP.md              main
├── packages/
│   ├── contracts/                ★ P1 — on main only
│   │   └── interpretex_contracts/
│   │       ├── enums.py  trade.py  investigation.py
│   │       ├── protocols.py  llm.py  helpers.py  fixtures.py
│   │       └── fixtures/
│   │           ├── cases/*.json
│   │           ├── tool_specs.json
│   │           ├── tool_results/*.json
│   │           └── runs/*.events.jsonl  *.result.json
│   ├── world/                    ★ P1 — branch part1-world
│   │   ├── api.py  reference.py  generator.py  documents.py
│   │   ├── extraction.py  tools/*.py  network.py  attacker.py
│   ├── agent/                    ★ P2 — branch part2-agent
│   │   ├── api.py  loop.py  triage.py  hypotheses.py  planner.py
│   │   ├── ledger.py  corroboration.py  policy.py  graph.py
│   │   ├── report.py  fallback.py  eval.py
│   └── app/                      ★ P3 — branch part3-app
│       ├── main.py  routes/*.py  sse.py  runs.py  cors.py
├── agent_prompts/                ★ P2      LLM prompt templates as .md
├── data/                         ★ P1      reference-world JSON
├── stubs/                        ★ P3 — on main
│   ├── fake_world.py  fake_agent.py
├── wiring.py                     ★ P3 — on main
├── scripts/                      ★ P3
├── tests/
│   ├── contracts/  P1   world/  P1   agent/  P2   app/  P3
└── frontend/                     ★ P3
    └── src/{components,hooks,types,lib}/
```

**The rule that prevents merge conflicts: never edit a file outside your ownership.** If you need a change in someone else's file, open a single-file PR against `main` and say so in the team channel. `packages/contracts/` after T+2h is a contract change requiring all three to agree.

---

## 10. Branch strategy and bootstrap

GitHub is not reachable from the environment this plan was written in, so run this yourself. One person does it once, immediately, before anyone starts:

```bash
git clone https://github.com/alonek007/interpretex.git
cd interpretex

# commit the plan + prompts to main first
mkdir -p docs prompts
#   ...copy 00_MASTER_PLAN.md into docs/, the three prompts into prompts/...
git add . && git commit -m "docs: master plan and three work prompts" && git push origin main

# create the three tracked branches off main
for b in part1-world part2-agent part3-app; do
  git checkout main
  git checkout -b "$b"
  git push -u origin "$b"
done
git checkout main
```

Optional but recommended on GitHub: protect `main` so it only takes pull requests, and set the default branch to `main`.

**Per-engineer setup:**
```bash
git clone https://github.com/alonek007/interpretex.git && cd interpretex
git checkout part1-world      # or part2-agent / part3-app
python3.11 -m venv .venv && source .venv/bin/activate
cp .env.example .env          # paste the shared OPENROUTER_API_KEY and LLM_MODEL
```

**Merge protocol.** Commit to your own branch continuously — at minimum every 30 minutes, and always before an integration window. Before each window, `git fetch origin && git rebase origin/main`. At the window, open a PR into `main` and merge with `--no-ff`. **Never merge another part's branch directly into yours**; go through `main` so there is exactly one integration history. After the window, everyone rebases on the new `main`.

---

## 11. Integration protocol

Integration is deliberately reduced to flipping two environment variables, because everything is developed against protocols and fixtures:

```
INTERPRETEX_WORLD=stub|real
INTERPRETEX_AGENT=stub|real
```

`wiring.py` (Part 3, on `main`) reads these and returns either the real module or the stub. Part 3 therefore has a working full-stack application from hour four, with a fake world and a fake agent, and integration is a sequence of three flips rather than one big-bang merge at hour twenty.

| Window | Time | Duration | What lands | Green gate |
|---|---|---|---|---|
| **0** | T+1.5h | — | P1 pushes `packages/contracts/` to `main` | All three `import interpretex_contracts` successfully and print the same `CONTRACT_VERSION` |
| **0b** | T+3h | — | P1 pushes v0 fixtures to `main` | P2 runs its loop against `FixtureToolRegistry`; P3 renders three real cases |
| **1** | T+5h | 30 min | P3 pushes `stubs/` + `wiring.py`; everyone rebases | `WORLD=stub AGENT=stub` — browser shows three cases and replays a full fake investigation to a decision |
| **2** | T+10h | 60 min | P1 merges world; P2 merges agent | `WORLD=real AGENT=real` — **Case 3 runs live end-to-end in the browser and escalates.** This is the MVP gate. |
| **3** | T+14h | 45 min | Advanced features merge behind flags | Each flag toggled independently; any red feature has its flag set to 0 and is abandoned on the spot |
| **Freeze** | T+18h | — | No new features | `LLM_CACHE_MODE=read`, three consecutive clean dry runs |

Every part logs `CONTRACT_VERSION` at startup. If two parts disagree you will see it in one second instead of debugging a validation error for twenty minutes.

---

## 12. The 24-hour timeline, with kill switches

| Hours | Part 1 · World | Part 2 · Agent | Part 3 · App |
|---|---|---|---|
| **0 – 1.5** | **Author `packages/contracts/` and push to `main`.** Confirm the exact OpenRouter model slug for Ox Alpha and put it in the shared `.env`. | Author the four LLM prompt templates (triage, hypothesise, plan, interpret) as markdown, and write the decision-policy spec. No code deps. | Vite + React + Tailwind shell; hand-write TypeScript mirrors of the contract; layout skeleton with all panels empty. |
| **1.5 – 3** | Reference world JSON: 8 commodities with monthly benchmarks and volume tiers, 6 vessels, 10 ports, 12 entities, 40 historical trades, 3 network clusters. | Loop skeleton with a 20-line hand-rolled fake registry; triage and hypothesis generation working against the real LLM. | FastAPI skeleton, CORS, `/api/health`, `/api/cases`, SSE endpoint shape, `EventSource` hook + reducer. |
| **3 – 5** | Case generator + anomaly injection + ground-truth labels; document renderer; extraction. **Push v0 fixtures to `main`.** | Planner with information-gain scoring and rejected-candidate logging; tool dispatch with failure recovery. | Stubs + `wiring.py` to `main`; live timeline renders from `narration`; case selector from real fixtures. |
| — | **WINDOW 1 @ T+5** | | |
| **5 – 10** | Tools 1–8 against the real reference world; unit test each; historical and network data wired. | Evidence ledger with stance/weight assignment; corroboration analyser; **deterministic policy gate**; dossier writer; deterministic fallback path. | Hypothesis board, FOR/AGAINST ledger, evidence graph (React Flow + dagre), decision panel, dossier viewer with markdown. |
| — | **WINDOW 2 @ T+10 — MVP GATE** | | |
| **10 – 14** | Attacker agent (`FEATURE_ATTACKER`) + network intelligence (`FEATURE_NETWORK`). | Investigation budget and information gain (`FEATURE_BUDGET`) + eval harness over labelled cases. | Network graph view, budget meter, judge reveal mode, replay mode. |
| — | **WINDOW 3 @ T+14** | | |
| **14 – 18** | Record LLM cassettes for all four demo cases; tune Case 4 until the attacker reliably lands every signal under threshold. | Verify all four cases hit their expected verdicts three runs in a row; tighten report prose. | Visual polish, empty and error states, architecture diagram, README. |
| **18 – 21** | Freeze. `LLM_CACHE_MODE=read`. Three clean dry runs. Deck and demo script. Rehearse twice against a timer. **Record a screen capture as the ultimate fallback.** |
| **21 – 24** | Buffer. One-line bug fixes only. No new features, no refactors, no dependency changes. |

**Sleep:** rotate one person resting two hours at a time between T+11 and T+17. Three exhausted engineers at hour 20 is a worse outcome than one feature cut.

### Kill switches — decide at the stated hour, do not negotiate

| Feature | Owner | Deadline | If not working, then |
|---|---|---|---|
| MVP end-to-end on Case 3 | all | **T+10** | Cut all four advanced features immediately and spend hours 10–18 on the three core cases. Non-negotiable. |
| Investigation budget | P2 | T+13 | `FEATURE_BUDGET=0`; keep only the hard `AGENT_MAX_STEPS` cap. |
| Network intelligence | P1 + P3 | T+14 | `FEATURE_NETWORK=0`; drop the network tool from the registry. |
| Attacker agent | P1 | T+15 | Ship the pre-tuned deterministic evasive case as a fourth static case; never attempt live generation on stage. |
| Judge reveal mode | P3 | T+16 | Read ground truth from the fixture JSON manually during the demo. |
| Playwright smoke test | P3 | T+17 | Manual checklist. |

---

## 13. The demo cases — exact numbers, so all three parts converge

All three engineers build to these figures. They are the shared acceptance test.

### Case 1 — `case_clean_001` → expect **RELEASE** in ≤ 3 tool calls
Coffee, 480 t, Santos `BRSSZ` → Rotterdam `NLRTM`, MV Pacific Dawn (2,500 t capacity). Declared $4,420/t against a $4,500/t benchmark, −1.8%. Shipped 2026-07-02, arrived 2026-07-19 against an expected 15–19 day band. Insurance issued 2026-07-01, before shipment. Every document agrees. The agent should stop early and say plainly that no significant corroborated anomaly was found — and the short trace is the point: it demonstrates the agent is not running a checklist.

### Case 2 — `case_explainable_002` → expect **HOLD** (RELEASE acceptable), never ESCALATE
Aluminium ingots, 1,600 t, Jebel Ali `AEJEA` → Nhava Sheva `INNSA`, MV Gulf Trader (2,800 t). Declared $1,968/t against $2,400/t, **−18.0%**. Shipped 2026-08-03, arrived 2026-08-09 against a 4–7 day band. Insurance issued 2026-08-01. A genuine three-year offtake contract with volume tiers **is** in the file, and this entity's own history shows $1,940–$2,010/t across six prior trades.

This is the case that proves the system reasons. The agent must find the economic anomaly, generate the bulk-discount hypothesis, *test* it, find it supported by two independent sources, find no anomaly in any other dimension, and then **explicitly state that a single-dimension economic anomaly with a corroborated benign explanation does not meet the escalation bar.** Requests: current-year pricing addendum, independent inspection certificate for grade.

### Case 3 — `case_suspicious_003` → expect **ESCALATE** on four dimensions
Copper cathodes, 2,200 t, Singapore `SGSIN` → Nhava Sheva `INNSA`, MV Ocean Star (**1,800 t capacity**). Declared $5,500/t against $8,900/t, **−38.2%**. Shipped 2026-08-10, arrived 2026-08-11 — one day against a 5–8 day band. Insurance issued **2026-08-18, eight days after shipment**. Packing list describes "Copper Scrap" where the invoice says "Copper Cathodes". No supporting contract exists. Entity history is $8,600–$9,100/t. The broker recurs across three previously flagged trades.

Economic + physical + temporal + documentary, with behavioural and network reinforcement. Typology wording must be **"Indicators consistent with potential under-invoicing / trade-value manipulation"** — never "money laundering confirmed".

### Case 4 — `case_adv_*`, generated by the attacker → expect **HOLD or ESCALATE** with an explicit "no single signal exceeds threshold" narrative
The attacker is told the rules (`price_deviation_pct: 0.30`, `capacity_utilisation: 1.00`, `insurance_lag_days: 3`) and instructed to stay under every one of them while still moving value. A good result looks like: zinc at −17% (under the 30% rule), 96% capacity utilisation (under the limit), transit at the fast edge of plausible but not impossible, same-day insurance, and one fresh intermediary shared with a single prior case. Every individual signal is `low` or `medium`. The investigator connects economic + behavioural + network and escalates anyway.

**This is the wow moment and therefore the most fragile thing in the build.** It must have a recorded cassette and a pre-tuned deterministic fallback. Never generate it live on stage.

---

## 14. Claims discipline

Say these:

- "An autonomous investigation layer for bank trade-finance teams that turns suspicious signals into evidence-backed, auditable investigations."
- "The prototype demonstrates the investigation workflow over a controlled synthetic environment."
- "In production the same layer connects to real commodity price feeds, AIS and vessel intelligence, customs data, sanctions and ownership registries, and the bank's own transaction history."
- "Indicators consistent with potential under-invoicing / trade-value manipulation."
- "Decision support for a human investigator."

Never say these:

- "We invented TBML detection." / "Existing systems don't check prices, vessels or routes." — false, and a compliance-literate judge knows it.
- "Nobody else does this."
- "Our system proves money laundering." / "confirmed fraud"
- "Our vessel database is real-world intelligence." — it is synthetic; say so unprompted, it buys credibility.
- "Our risk score is a regulatory AML probability."
- "This replaces compliance officers."

Every `Decision` carries these caveats, on every run without exception: reference data is synthetic and scoped to the prototype; the output is investigative decision support and not a regulatory determination; anomalies may have legitimate explanations no available tool can observe.

### What is actually novel — the nine points, ranked by how well they survive a hostile question

1. **The deterministic policy gate over LLM-produced evidence.** The model proposes, fixed rules dispose. Answers reliability, reproducibility and audit in one move.
2. **Escalation is blocked unless a benign hypothesis was actually tested.** A structural, checkable anti-confirmation-bias mechanism, not a prompt instruction.
3. **Corroboration defined across independent dimensions**, with single-dimension escalation forbidden by policy.
4. **Hypothesis-driven investigation** — rival explanations generated and discriminated between, rather than anomalies labelled.
5. **Dynamic next-step selection with the rejected candidates logged**, which is what distinguishes an agent from a pipeline.
6. **An auditable provenance DAG** in which every conclusion traces to a document field or a dated reference lookup.
7. **Automatic evidence requests** tied to the specific hypotheses they would resolve — turns a warning into a workflow.
8. **Investigation budget with information-gain prioritisation**, measured against an exhaustive baseline.
9. **Adversarial validation** — a second agent constructs cases that defeat thresholds, which is the cleanest available argument that dynamic investigation beats static rules.

---

## 15. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| The chosen OpenRouter model does not support native tool calling | High for alpha/stealth models | We never use native tool calling. Strict-JSON prompting plus local schema validation plus a re-prompt repair loop. Portable to any model. |
| Rate limits or provider outage mid-build | High | Cassette cache from hour one. `LLM_PROVIDER=scripted` for offline unit tests. |
| Model returns malformed JSON | Certain, occasionally | Repair loop, then a deterministic non-LLM fallback path that still produces a valid `InvestigationResult` with `meta.degraded=true`. |
| Live demo network failure | Medium | `LLM_CACHE_MODE=read` replays from disk. Recorded screen capture as the final fallback. |
| Agent loops or wanders | Medium | `AGENT_MAX_STEPS` hard cap independent of budget; no tool may be called twice with identical args. |
| SSE and CORS friction | Medium | Vite dev proxy so the browser sees one origin. Test SSE with `curl -N` before wiring any UI. |
| Field-name drift between parts | High without discipline | `extra="forbid"` everywhere, one owner for contracts, `CONTRACT_VERSION` logged at startup, fixtures as the shared acceptance test. |
| Merge conflicts | Medium | Strict file-ownership map; integration only through `main`. |
| Case 2 escalates anyway, destroying the "no overreaction" story | Medium | The single-dimension rule is enforced in code by the policy gate, not requested in a prompt. Regression-tested in the eval harness. |
| Attacker produces something the investigator misses entirely | Medium | Pre-tuned deterministic evasive case as the shipped fallback; live generation is a bonus, never the demo's spine. |
| Advanced features consume MVP time | High | Hard kill switches at stated hours, every feature behind a flag that defaults to off until its gate passes. |

---

## 16. Final demo narrative (six minutes)

Open on the problem in two sentences: banks already surface suspicious trades; connecting the evidence afterwards is the slow, inconsistent, badly-documented part. Then run Case 1 and let it release in three calls — establishing that the system does not cry wolf. Run Case 2 and narrate the moment the agent generates the bulk-discount hypothesis, spends a call testing it, finds it supported, and declines to escalate; pause on the sentence where it explains why one dimension is not enough. Run Case 3 and let the evidence graph fill in dimension by dimension, then read the corroboration narrative and the requested documents aloud. Finally, invoke the attacker live if and only if it is green, otherwise present the pre-generated adversarial case: every signal under every threshold, and the investigator escalates on correlation. Close by revealing ground truth for all four, then state plainly what is synthetic and what production integration would require.

Have ready, because you will be asked: how you stop the LLM hallucinating an escalation (the policy gate); how you know it is not just thresholds (the single-dimension rule and the rejected-candidate log); what happens when the model is wrong (degraded fallback, human decides); and why no agent framework (the trace is the product).
