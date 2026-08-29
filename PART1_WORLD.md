# PROMPT — PART 1 OF 3 · THE WORLD, THE TOOLS AND THE ADVERSARY

> Paste this entire document as the first message to your coding agent. It is self-contained: you do not need the other two prompts to do your job. Do not paraphrase or trim it.

---

## 0 · YOUR ROLE

You are the engineer building **Part 1 of 3** of a 24-hour hackathon project called **Interpretex — AI Trade Investigation Agent**. Two other engineers, each driving their own coding agent on a separate machine, are building Part 2 (the investigator agent) and Part 3 (the API and dashboard) at the same time. The three parts will be integrated near the end of the build.

You own **the synthetic world, the document layer, the eight investigation tools, the adversary, and — critically — the shared contracts package that the other two engineers import.**

Repository: **https://github.com/alonek007/interpretex**
Your branch: **`part1-world`**
Contract version you are authoring: **1.0.0**

You are the only person who can unblock the other two. Section 3 below is time-critical and takes priority over everything else you will build.

---

## 1 · NON-NEGOTIABLE GROUND RULES

1. **Never edit a file outside your ownership.** You own `packages/contracts/` (on `main`), `packages/world/`, `data/`, `tests/contracts/`, `tests/world/`, `docs/10_CONTRACTS.md`. You do **not** touch `packages/agent/`, `packages/app/`, `frontend/`, `stubs/`, `wiring.py`, `scripts/`, `Makefile`. If you need a change there, say so in the team channel; do not make it yourself.
2. **The contract is frozen at T+2h.** After that, changing a field name in `packages/contracts/` requires all three engineers to agree. Get it right the first time; the spec in section 5 is complete, so transcribe it faithfully rather than improving it.
3. **Tools report facts. Tools never report verdicts.** No tool you write may return `fraud=true`, a risk score, a probability of laundering, or the word "suspicious" in a conclusive sense. A tool says "declared unit price is 38.2% below the August 2026 benchmark". Interpreting that is Part 2's job and it is the layer the project claims as novel. If you leak judgement into the tool layer you destroy the project's central claim.
4. **`ToolRegistry.call()` must never raise.** Unknown tool name, malformed args, missing reference data, internal exception — all return a `ToolResult` with `ok=False` and `error` populated. The agent's ability to recover from a failed tool call is part of the demo.
5. **Ground truth must never reach the agent.** `TradeCase` carries a `label`; `AgentCaseView` has no `label` field at all. Enforce this by type, and never put ground-truth hints into `applicant_note`, document text, tool output, or entity `notes`.
6. **Determinism.** `generate_case(spec)` with the same `spec` and `seed` must produce a byte-identical case. Seed a local `random.Random(seed)` instance; never touch the global `random` module. Judges will ask about reproducibility.
7. **No new dependencies** beyond `pydantic>=2.6`, `httpx>=0.26`, `jsonschema>=4.21`, `pytest`, `python-dotenv`. No pandas, no faker, no SQLAlchemy, no reportlab. Python 3.11.
8. **Everything is synthetic and we say so.** Your reference data is a controlled prototype world, not market or maritime intelligence. Never name it in a way that implies otherwise (no `lme_prices.json`, no `ais_feed.py`).
9. **Commit to `part1-world` at least every 30 minutes.** Push. An uncommitted hour is a lost hour.

---

## 2 · PROJECT CONTEXT (read once, fully — your design decisions depend on it)

### The problem

Banks financing international trade receive case files of six or more documents: letter of credit, commercial invoice, bill of lading, packing list, certificate of origin, insurance certificate. Existing compliance systems already do document matching, tampering detection, price anomaly checks, vessel checks, route checks, sanctions screening and TBML red-flag rules. **We do not claim those checks are new, and we never claim banks lack them.**

The gap is what happens *after* a signal fires. A human investigator must then connect information across documents, market data, physical constraints, timelines, counterparties and the customer's own history to decide whether the trade is actually suspicious and what to do next. That connective reasoning is slow, inconsistent between investigators and poorly documented. **Interpretex automates that investigation layer.**

### The principle that shapes your work

An anomaly is a question, not a conclusion. A price 20% below benchmark may be a bulk discount, a lower grade, a distressed sale, a long-term offtake contract, or a data-entry error — or it may be under-invoicing. The system's credibility rests on it visibly trying to talk itself out of a suspicion before escalating.

**This is why your world must contain genuine innocent explanations, not just planted anomalies.** If every anomaly in your data is guilty, Part 2 has nothing to discriminate and the project collapses into a threshold detector with extra steps. Case 2 (section 8) is the case that proves the whole thesis, and it lives or dies on the quality of the data you build for it.

### The investigation loop your tools serve

Part 2's agent reads the case, triages it, generates rival hypotheses (at least one innocent and one illicit per anomaly), decides which single check would best discriminate between them, calls one of your tools, interprets the result into evidence with a stance, updates its hypotheses, and repeats until the evidence is sufficient. Then a deterministic policy gate issues RELEASE, HOLD + request documentation, or ESCALATE / BLOCK, with an auditable evidence graph behind it.

Two policy rules constrain what your data must make possible:

- **Escalation requires suspicion-supporting evidence in two or more distinct dimensions** (`economic`, `physical`, `temporal`, `documentary`, `behavioural`, `network`). A single anomalous dimension can never escalate, however extreme.
- **Escalation is blocked unless the agent spent a tool call testing a benign hypothesis.** Your `check_contract_or_supporting_evidence` tool is the primary way it does that, so that tool must be able to return a genuine, quotable, supporting finding — not just "not found".

### Positioning you must not contradict

Interpretex is "an autonomous investigation layer for bank trade-finance teams that turns suspicious signals into evidence-backed, auditable investigations", demonstrated "over a controlled synthetic environment". Never write a comment, docstring, README line or log message claiming we invented TBML detection, that other systems don't do these checks, that the system proves money laundering, or that your reference data is real.

---

## 3 · TIME-CRITICAL: WHAT YOU DO IN THE FIRST THREE HOURS

Two other engineers are blocked on you. Do these three things before you write a single line of your own package.

### T+0 to T+0.25 — confirm the model slug

Open https://openrouter.ai/models and find the exact slug for the model the team agreed on (**Ox Alpha**). Alpha and stealth model slugs change; the string you find is the string all three machines must use. Put it in `.env.example` as `LLM_MODEL=` and tell the team in the channel. Do not guess it.

### T+0.25 to T+1.5 — author `packages/contracts/` and push it to `main`

Not to your branch — to **`main`**, so the other two can `git pull` and start. Transcribe section 5 of this prompt exactly. Include:

- `enums.py`, `trade.py`, `investigation.py` — pydantic v2 models, every one with `model_config = ConfigDict(extra="forbid")`
- `protocols.py` — the `ToolRegistry`, `LLMClient`, `WorldAPI`, `Investigator` protocols from section 5.7
- `llm.py` — the OpenRouter client described in section 6
- `helpers.py` — `utcnow()`, `new_run_id()`, a `Counter` id generator, a `SeqEmitter` that guarantees gapless event `seq`, an `sse_frame()` serialiser, a `Flags` feature-flag reader, and the `STANDARD_CAVEATS` list
- `fixtures.py` — loaders plus a `FixtureToolRegistry` class that satisfies `ToolRegistry` entirely from canned JSON
- `__init__.py` — re-export everything flat, and define `CONTRACT_VERSION = "1.0.0"`
- `pyproject.toml` — package name `interpretex-contracts`, include `fixtures/**/*.json` and `fixtures/**/*.jsonl` as package data

Announce in the channel: *"contracts v1.0.0 on main, pull now."*

### T+1.5 to T+3 — publish v0 golden fixtures to `main`

Hand-written is fine at this stage; correctness of *shape* matters more than richness of content. Write to `packages/contracts/interpretex_contracts/fixtures/`:

```
cases/case_clean_001.json            full TradeCase incl. label
cases/case_explainable_002.json
cases/case_suspicious_003.json
tool_specs.json                      all 8 ToolSpec objects
tool_results/case_clean_001.json     { "<tool_name>": <ToolResult>, ... }
tool_results/case_explainable_002.json
tool_results/case_suspicious_003.json
runs/case_suspicious_003.events.jsonl   one InvestigationEvent per line, a plausible full run
runs/case_suspicious_003.result.json    one full InvestigationResult
```

Write a test that loads every fixture through the pydantic models and asserts it validates. **A fixture that does not validate is worse than no fixture**, because it will send the other two down a wrong path.

The event trace and result fixture are for Part 3's UI: they need something to render before Part 2's agent exists. Make the trace realistic — around 22 to 30 events, with a `triage`, two `hypotheses_updated`, five `plan_step` (each with a populated `considered` list), five matched `tool_call_started`/`tool_call_completed` pairs, six `evidence_added`, several `graph_updated`, a `corroboration`, a `decision`, an `evidence_requested` and a terminal `report_ready`. Respect the ordering guarantees in section 5.6.

Announce: *"v0 fixtures on main, `FixtureToolRegistry` works, pull now."*

Then, and only then, `git checkout part1-world` and start section 7.

---

## 4 · YOUR SCOPE — THE COMPLETE DELIVERABLE LIST

### 4.1 Shared, on `main` (sections 3 and 5)
1. `packages/contracts/` — models, enums, protocols, LLM adapter, helpers, fixture loaders.
2. Golden fixtures for three cases, plus one recorded event trace and result.
3. `docs/10_CONTRACTS.md` — a generated field reference so nobody has to read the source.

### 4.2 The reference world — `data/*.json`, loaded and indexed by `packages/world/reference.py`
4. **`commodities.json`** — 8 commodities. Each: `key`, `display_name`, `hs_code`, `unit`, `grades` (list with a price multiplier per grade), `monthly_benchmarks` (at minimum 2025-09 through 2026-09, `{ "2026-08": 8900.0, ... }`), `plausible_band_pct` (normal spread, e.g. 0.06), `volume_tiers` (e.g. `[{min_qty: 1000, discount_pct: 0.04}, {min_qty: 2500, discount_pct: 0.07}]`), `density_t_per_m3` (for the optional container check).
   Include at minimum: copper cathode 8900, aluminium ingot 2400, coffee arabica 4500, wheat 300, zinc 2750, refined palm oil 960, cotton 1780, polyethylene resin 1150 — all USD/tonne as of 2026-08. Give each a realistic 13-month history with plausible drift, not a flat line.
5. **`vessels.json`** — 6 vessels. Each: `vessel_name`, `imo`, `dwt_tons`, `vessel_type`, `max_speed_knots`, `flag`, `owner_entity_id`. Must include `MV Ocean Star` at **1,800 t**, `MV Pacific Dawn` at **2,500 t**, `MV Gulf Trader` at **2,800 t**, plus `MV Titan` at 5,000 t and two others.
6. **`ports.json`** — 10 ports with real `port_code`, `name`, `country`, `lat`, `lon`. Must include `SGSIN` Singapore, `INNSA` Nhava Sheva, `AEJEA` Jebel Ali, `BRSSZ` Santos, `NLRTM` Rotterdam, plus five more spread across regions. Compute transit from great-circle distance and vessel speed at run time; do not hardcode a route table.
7. **`entities.json`** — 12+ entities across all six roles, with `ultimate_beneficial_owners` deliberately overlapping for two pairs, and `sanctions_status` `not_listed` for all but one `near_match`. Include the demo parties: ABC Trading (buyer, IN), XYZ Metals (seller, SG), and a broker that recurs across flagged trades.
8. **`historical_trades.json`** — 40+ prior trades. Each: `trade_id`, `date`, `exporter_id`, `importer_id`, `commodity`, `quantity`, `unit_price`, `vessel_name`, `broker_id`, `origin_port`, `destination_port`, `outcome` (`released` | `held` | `escalated`). Must support the two behavioural stories: the Case 2 importer has six aluminium trades at $1,940–$2,010/t, and the Case 3 importer has prior copper trades at $8,600–$9,100/t.
9. **`networks.json`** — 3 entity clusters: one benign trading group, one with a shared-UBO relationship, one with an intermediary reused across three trades that were previously escalated.

### 4.3 Case generation
10. **`generator.py`** — `generate_case(spec: CaseSpec) -> TradeCase`. Builds a coherent clean shipment first (commodity, grade, quantity, benchmark-consistent price, parties, vessel with adequate capacity, ports, plausible dates, insurance before shipment), then applies each requested `AnomalyKind` at the requested magnitude, then records exactly what it did in `CaseLabel`. Every anomaly must be applied by *mutating the underlying shipment and re-rendering the documents*, never by editing one document's text — otherwise the anomaly is only visible to whichever tool you happened to think of.
11. **Anomaly injectors** — one function per `AnomalyKind`, each taking a magnitude. `under_invoicing(0.38)` sets the price 38% below the month's benchmark. `capacity_exceeded(0.22)` makes cargo exceed `dwt_tons` by 22%. `impossible_transit` compresses the arrival date below the plausible band. `insurance_after_shipment(8)` moves the insurance issue date 8 days after `ship_date`. `description_drift` changes the commodity description on one document only. And so on for all twelve.
12. **Ground-truth labelling** — `CaseLabel` with `case_class`, `injected_anomalies`, `expected_verdict`, `benign_explanation` for legitimate-but-odd cases, `evasion_notes` for adversarial ones, `generator_seed`.
13. **The three demo cases** as named, seeded, reproducible fixtures matching section 8 exactly.

### 4.4 Documents
14. **`documents.py`** — render all six core document types (plus `inspection_certificate` and `sales_contract` when present) from one shipment. Each produces a `TradeDocument` with both `fields` (canonical names) and `raw_text` (plausible document layout with header, reference numbers, party blocks, line items, terms, signature block). The `raw_text` must actually contain the same values as `fields` — Part 3 displays it in a document viewer and a judge will read it.
15. **Field-level realism** — different documents legitimately carry different subsets of fields. A bill of lading has no unit price. A packing list has gross and net weight and carton counts. A certificate of origin has the HS code and a chamber-of-commerce reference. Getting this right is what makes `check_document_consistency` meaningful rather than trivially total.
16. **`extraction.py`** — `extract(documents) -> TradeRecord`. Deterministic, rule-based; do not use an LLM. Precedence: LC and invoice win on commercial terms, bill of lading wins on transport, packing list wins on weights. **Never silently reconcile a disagreement** — hold the winning value and make the conflict discoverable by `check_document_consistency`.

### 4.5 The eight tools — `packages/world/tools/`
17. One module per tool, each a function returning a `ToolResult`, plus a `ToolSpec` describing it. Full specification in section 7.
18. **`registry.py`** — `build_tool_registry(case) -> ToolRegistry`, closing over the case, assigning sequential `call_id`s (`TC-001`…), measuring `latency_ms`, and catching every exception into `ok=False`.
19. Unit tests: for each tool, one call that produces an observation and one that produces none, plus one deliberately malformed-args call asserting `ok=False`.

### 4.6 Advanced features (behind flags, after the T+10 MVP gate)
20. **Network intelligence** (`FEATURE_NETWORK`) — `network.py` with `network_view(entity_id, depth) -> NetworkView`, computing `NetworkFinding`s for `intermediary_reuse`, `shared_ownership`, `vessel_reuse`, `circular_trade`, `price_pattern` across `historical_trades.json` and `networks.json`.
21. **Attacker agent** (`FEATURE_ATTACKER`) — `attacker.py` with `attack(spec: AttackSpec, llm=None) -> TradeCase`. Full specification in section 9.

### 4.7 Public surface
22. **`packages/world/api.py`** — exactly these, and nothing else public: `list_cases`, `load_case`, `generate_case`, `build_tool_registry`, `network_view`, `attack`. Part 3 imports only from here. Anything not on this list is internal.

---

## 5 · THE CONTRACT YOU AUTHOR (normative — transcribe exactly)

Every model: `model_config = ConfigDict(extra="forbid")`. Field names below are the contract; the other two engineers are coding against these exact strings.

### 5.1 Enums

| Enum | Members |
|---|---|
| `DocType` | `letter_of_credit`, `commercial_invoice`, `bill_of_lading`, `packing_list`, `certificate_of_origin`, `insurance_certificate`, `inspection_certificate`, `sales_contract` |
| `Dimension` | `economic`, `physical`, `temporal`, `documentary`, `behavioural`, `network` |
| `Severity` | `none`, `low`, `medium`, `high` |
| `Stance` | `supports_suspicion`, `refutes_suspicion`, `neutral` |
| `HypothesisKind` | `benign`, `suspicious` |
| `HypothesisStatus` | `open`, `supported`, `weakened`, `refuted`, `untestable` |
| `Verdict` | `release`, `hold`, `escalate` |
| `CaseClass` | `clean`, `suspicious_but_legitimate`, `illicit`, `adversarial` |
| `AnomalyKind` | `under_invoicing`, `over_invoicing`, `capacity_exceeded`, `impossible_transit`, `insurance_after_shipment`, `description_drift`, `quantity_mismatch`, `hs_code_mismatch`, `route_deviation`, `historical_deviation`, `intermediary_reuse`, `shared_ownership`, `none` |
| `SourceKind` | `document`, `reference_db`, `derived`, `model` |
| `EventType` | `run_started`, `case_loaded`, `triage`, `hypotheses_updated`, `plan_step`, `tool_call_started`, `tool_call_completed`, `evidence_added`, `graph_updated`, `budget_updated`, `corroboration`, `decision`, `evidence_requested`, `report_ready`, `run_failed`, `heartbeat` |

Document in the `Severity` docstring that it is deviation salience emitted by a tool and explicitly not a fraud verdict. Document in the `Stance` docstring that only the agent may set it.

### 5.2 World models

- **`Entity`** — `entity_id`, `name`, `country`, `role`, `incorporated_on?`, `registry_id?`, `ultimate_beneficial_owners: list[str]`, `sanctions_status`, `notes?`
- **`Vessel`** — `vessel_name`, `imo?`, `dwt_tons`, `vessel_type`, `max_speed_knots`, `flag?`, `owner_entity_id?`
- **`Port`** — `port_code`, `name`, `country`, `lat`, `lon`
- **`TradeDocument`** — `doc_id`, `doc_type`, `issuer`, `issue_date`, `fields: dict[str, Any]`, `raw_text: str`, `extraction_confidence: float`
- **`TradeRecord`** — `commodity`, `commodity_grade?`, `hs_code?`, `quantity`, `unit`, `unit_price`, `currency`, `total_value`, `incoterm?`, `exporter_id`, `importer_id`, `broker_id?`, `insurer_id?`, `vessel_name?`, `imo?`, `container_count?`, `gross_weight_tons?`, `origin_port?`, `destination_port?`, `ship_date?`, `arrival_date?`, `lc_issue_date?`, `insurance_issue_date?`, `lc_number?`, `bl_number?`, `contract_reference?`
- **`CaseLabel`** — `case_class`, `injected_anomalies: list[AnomalyKind]`, `expected_verdict: str`, `benign_explanation?`, `evasion_notes?`, `generator_seed?`
- **`AgentCaseView`** — `case_id`, `received_at`, `bank_reference?`, `applicant_note?`, `documents`, `record`, `available_tool_names: list[str]`. **No `label` field.**
- **`TradeCase`** — all of `AgentCaseView` plus `title`, `entities: list[Entity]`, `vessel: Vessel|None`, `label: CaseLabel|None`, and the method `to_agent_view() -> AgentCaseView`
- **`CaseSummary`** — `case_id`, `title`, `commodity`, `quantity`, `unit`, `total_value`, `currency`, `exporter_name`, `importer_name`, `origin_port?`, `destination_port?`, `document_count`, `received_at`, `is_adversarial`
- **`CaseSpec`** — `case_class`, `commodity?`, `quantity?`, `exporter_id?`, `importer_id?`, `anomalies: list[AnomalyKind]`, `anomaly_magnitudes: dict[str, float]`, `benign_explanation?`, `plant_supporting_contract: bool`, `seed: int`
- **`AttackSpec`** — `known_thresholds: dict[str, float]`, `max_dimensions: int`, `target_stealth: float`, `seed: int`

### 5.3 Tool models

- **`SourceRef`** — `kind: SourceKind`, `ref: str`, `value?`, `as_of?`, `label?`
  `ref` format is normative. Documents: `"<doc_id>.<field>"` e.g. `"INV-2026-0912.unit_price"`. Reference world: `"<table>/<key>[/<as_of>]"` e.g. `"benchmarks/copper_cathode/2026-08"`. Derived: `"<tool>:<metric>"` e.g. `"check_price_benchmark:deviation_pct"`.
- **`Observation`** — `observation_id`, `dimension`, `statement`, `severity`, `metrics: dict[str, float]`, `sources: list[SourceRef]`, `expected_range?`
- **`ToolSpec`** — `name`, `description`, `dimensions: list[Dimension]`, `args_schema: dict`, `cost_units: int`, `discriminates: list[str]`
- **`ToolResult`** — `tool`, `call_id`, `args`, `ok: bool`, `summary: str`, `observations: list[Observation]`, `raw: dict`, `sources: list[SourceRef]`, `cost_units: int`, `latency_ms: int`, `error?`

### 5.4 Reasoning models (you author them; Part 2 populates them)

- **`Triage`** — `trade_narrative`, `initial_concerns: list[str]`, `unknowns: list[str]`, `dimensions_to_probe: list[Dimension]`
- **`Hypothesis`** — `hypothesis_id`, `kind: HypothesisKind`, `statement`, `explains: list[Dimension]`, `prior: float`, `posterior: float`, `status: HypothesisStatus`, `discriminating_evidence_needed: list[str]`, `supporting_evidence_ids: list[str]`, `contradicting_evidence_ids: list[str]`, `rationale?`
- **`EvidenceItem`** — `evidence_id`, `dimension`, `stance`, `statement`, `weight: float`, `severity`, `hypotheses_affected: list[str]`, `observation_ids: list[str]`, `tool_call_id?`, `sources: list[SourceRef]`, `interpretation?`
- **`PlanStep`** — `step: int`, `reasoning`, `chosen_tool: str|None`, `chosen_args: dict`, `targets_hypotheses: list[str]`, `expected_information_gain: float`, `considered: list[dict]`, `stop_reason?`
- **`BudgetState`** — `limit`, `spent`, `remaining`, `calls_made`, `tools_skipped: list[dict]`, `exhaustive_cost?`
- **`Corroboration`** — `corroborated_dimensions: list[Dimension]`, `independent_signal_count: int`, `refuting_dimensions: list[Dimension]`, `strongest_benign_hypothesis?`, `strongest_benign_posterior: float`, `narrative: str`
- **`Decision`** — `verdict`, `confidence: float`, `headline`, `rationale`, `corroboration`, `typology?`, `caveats: list[str]`, `decisive_evidence_ids: list[str]`
- **`EvidenceRequest`** — `item`, `why`, `resolves_hypotheses: list[str]`, `priority: int` (1–3)
- **`GraphNode`** — `id`, `kind`, `label`, `dimension?`, `stance?`, `severity?`, `meta: dict`
- **`GraphEdge`** — `source`, `target`, `relation`, `label?`
- **`EvidenceGraph`** — `nodes`, `edges`
- **`NetworkFinding`** — `finding_id`, `pattern`, `statement`, `entity_ids`, `case_ids`, `severity`, `metrics`
- **`NetworkView`** — `focus_entity_id?`, `nodes`, `edges`, `findings`
- **`RunMeta`** — `run_id`, `case_id`, `started_at`, `finished_at?`, `model`, `llm_calls`, `prompt_tokens`, `completion_tokens`, `wall_ms`, `replayed: bool`, `degraded: bool`

### 5.5 Result

**`InvestigationResult`** — `meta: RunMeta`, `record`, `triage`, `hypotheses`, `plan_steps`, `tool_calls`, `evidence_for`, `evidence_against`, `evidence_neutral`, `budget`, `graph`, `decision`, `evidence_requests`, `report_markdown`, `events`

### 5.6 Events

**`InvestigationEvent`** — `seq: int`, `ts: datetime`, `run_id: str`, `type: EventType`, `narration: str`, `payload: dict`

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
| `report_ready` | `result`, `report_markdown` |
| `run_failed` | `error`, `stage`, `degraded` |
| `heartbeat` | *(empty)* |

Ordering guarantees to document in the docstring and honour in your fixture trace: `seq` starts at 0 and increments by exactly 1 with no gaps; `run_started` is `seq` 0; the stream terminates with `report_ready` or `run_failed`; every `tool_call_completed` follows its matching `tool_call_started`; `decision` precedes `report_ready`.

`sse_frame(event)` in `helpers.py` must emit exactly:
```
id: <seq>
event: <type value>
data: <event.model_dump_json()>

```

### 5.7 Protocols

```python
class ToolRegistry(Protocol):
    def specs(self) -> list[ToolSpec]: ...            # stable order
    def call(self, name: str, args: dict) -> ToolResult: ...   # never raises

class LLMClient(Protocol):
    model: str
    def complete(self, *, system, messages, temperature=0.2,
                 max_tokens=2048, tag="") -> str: ...
    def complete_json(self, *, system, messages, schema, temperature=0.1,
                      max_tokens=2048, tag="", retries=2) -> dict: ...

class WorldAPI(Protocol):
    def list_cases(self) -> list[CaseSummary]: ...
    def load_case(self, case_id: str) -> TradeCase: ...
    def generate_case(self, spec: CaseSpec) -> TradeCase: ...
    def build_tool_registry(self, case: TradeCase) -> ToolRegistry: ...
    def network_view(self, entity_id=None, depth=2) -> NetworkView: ...
    def attack(self, spec: AttackSpec, llm=None) -> TradeCase: ...

class Investigator(Protocol):
    def investigate_stream(self, case: AgentCaseView, tools: ToolRegistry, *,
                           llm=None, budget=6, seed=None) -> Iterator[InvestigationEvent]: ...
    def investigate(self, case, tools, *, llm=None, budget=6,
                    seed=None, emit=None) -> InvestigationResult: ...
```

Also define `EmitFn = Callable[[InvestigationEvent], None]` and `STANDARD_CAVEATS`, a list of exactly three strings: that reference data is synthetic and scoped to the prototype; that the output is investigative decision support and not a regulatory determination; that anomalies may have legitimate commercial explanations no available tool can observe.

---

## 6 · THE SHARED LLM ADAPTER (you author it; all three parts use it)

`packages/contracts/interpretex_contracts/llm.py`. Talk to OpenRouter over **raw `httpx`**, not an SDK: OpenRouter is a plain OpenAI-compatible REST endpoint, and support for native function calling and `response_format` varies across its alpha and stealth models. Raw HTTP means a model swap is one env var and never a dependency change at 3am.

`OpenRouterClient` reads `OPENROUTER_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` (default `https://openrouter.ai/api/v1`), `LLM_CACHE_MODE`, `LLM_CACHE_DIR`, `LLM_TIMEOUT_S`, `LLM_MAX_RETRIES`. Send `HTTP-Referer` and `X-Title` headers. POST to `/chat/completions`.

Four things this class must do, each for a specific reason:

**Cassette cache.** Hash `(model, system, messages, temperature, max_tokens)` into a key; write every completion to `LLM_CACHE_DIR` as JSON. `LLM_CACHE_MODE` is `readwrite` (default, development), `write`, `off`, or **`read`** — replay only, error if a cassette is missing. On stage the team runs `read`: no network, no rate limits, no latency, byte-identical output. **This is the single highest-value component you will write today.** Name cassette files `<tag>.<hash>.json` so they are greppable.

**Retry with backoff** on 429, 500, 502, 503, 504, 520 and 529, and on empty completions. Cap at `LLM_MAX_RETRIES`, raise `LLMError` after.

**`complete_json` with a repair loop.** Append the JSON Schema to the system prompt with a hard instruction to emit one JSON object and nothing else. Parse the response with a tolerant extractor that handles bare JSON, fenced JSON, a prose preamble and trailing commentary (brace-matching fallback). Validate with `jsonschema` if importable, else check `required` keys. On failure, re-prompt with the validator's error message and the model's previous output, up to `retries` times, then raise `LLMJsonError`. **Do not use provider-side structured output** — it is not reliably available.

**Usage accounting.** Track calls, prompt tokens, completion tokens, cache hits, retries, and a per-`tag` count. Part 2 puts these into `RunMeta`.

Also ship **`ScriptedLLM`**: takes a list of canned responses, hands them out in order, loops on the last, records what it was asked. No network. `LLM_PROVIDER=scripted` selects it, and it is what makes CI and offline unit tests possible. Provide `build_llm()` as the factory both other parts call.

---

## 7 · THE EIGHT TOOLS — FULL SPECIFICATION

General rules for every tool. `summary` is at most 200 characters and is the first thing the planner reads, so it must carry the headline number. Emit an `Observation` **only when there is something to report** — a tool that finds nothing returns `observations=[]` and a summary saying so, which the agent needs in order to record refuting evidence. Populate `metrics` with the numbers behind the statement so nobody re-parses prose. Populate `sources` with real `SourceRef`s; the evidence graph is built from them and a missing source breaks provenance. Fill `raw` with the full payload for the UI drill-down. `severity` maps deviation magnitude to `low`/`medium`/`high` by fixed thresholds you document — and it is never a verdict.

**1 · `read_document`** · args `{doc_type?: str, doc_id?: str}` · `documentary` · cost 1
Returns one document's `fields` and `raw_text`. `observations` normally empty; emit one only for an internally inconsistent document (e.g. line-item total ≠ stated total). `raw.document` carries the full `TradeDocument`.
`discriminates`: ["what the paperwork actually claims", "documentation or data-entry error"]

**2 · `check_document_consistency`** · args `{fields?: list[str]}` · `documentary` · cost 1
Compares every field present on two or more documents: commodity description, `hs_code`, quantity, `gross_weight_tons`, `unit_price`, `total_value`, `container_count`, ports, `vessel_name`, dates, exporter, importer. One `Observation` per disagreeing field, naming both documents and both values. For text fields do a normalised comparison and treat "Copper Cathodes" vs "Copper Scrap" as a **material** difference (`severity=high`) while "Copper Cathode" vs "copper cathodes" is not a difference at all. `raw.field_matrix` maps field → {doc_id: value} so the UI can render a comparison table.
`discriminates`: ["clerical error", "deliberate misdescription", "documents describe different goods"]

**3 · `check_price_benchmark`** · args `{commodity, grade?, quantity, as_of_date, declared_unit_price}` · `economic` · cost 1
Look up the month's benchmark. Return `benchmark_unit_price`, `plausible_band_pct`, `deviation_pct`, the grade multiplier if a grade was supplied, and **the applicable volume tier** — that last one matters because it is how the agent can find part of the innocent explanation. Severity: within band `none`; up to 10% outside `low`; 10–25% `medium`; beyond 25% `high`. One `Observation` when outside the band.
`discriminates`: ["under-invoicing", "over-invoicing", "legitimate bulk discount", "grade difference", "stale or erroneous price"]

**4 · `check_vessel_capacity`** · args `{vessel_name, claimed_weight_tons}` · `physical` · cost 1
Look up `dwt_tons`. Return `dwt_tons`, `claimed_weight_tons`, `utilisation_pct`, `excess_tons`. Unknown vessel → `ok=True` with an observation that the vessel is not in the registry (`severity=medium`), **not** an error: "we cannot verify this vessel" is itself a finding. Severity: ≤100% `none`; up to 105% `low`; 105–120% `medium`; above `high`.
`discriminates`: ["phantom or inflated shipment", "wrong vessel recorded", "quantity misstated"]

**5 · `check_transit_plausibility`** · args `{origin_port, destination_port, ship_date, arrival_date, vessel_name?}` · `temporal`, `physical` · cost 1
Great-circle distance between the ports, expected transit band from the vessel's `max_speed_knots` (use roughly 60–90% of max as the realistic band, plus a port-handling allowance), claimed transit in days, and the **implied speed in knots** — that number is the one that lands with an audience. Severity from how far outside the band. Unknown port → observation, not error.
`discriminates`: ["impossible or fictitious voyage", "date recording error", "transhipment or undeclared route", "vessel substitution"]

**6 · `check_historical_trade`** · args `{entity_id, commodity, lookback_months?}` · `behavioural` · cost 2
Prior trades for this entity in this commodity: count, price min/median/max, quantity range, distinct counterparties, distinct vessels, and the **z-score of the current declared price against that history**. Zero history is a finding in itself (`severity=low`, first transaction in this commodity). This tool is how "unusual for the market" becomes "unusual for this customer", which is the stronger statement — and in Case 2 it produces evidence *against* suspicion.
`discriminates`: ["consistent long-standing pricing arrangement", "anomaly specific to this transaction", "new or unusual trading behaviour"]

**7 · `check_counterparty_network`** · args `{entity_id, depth?}` · `network` · cost 2
Walk the entity graph to `depth`. Return shared intermediaries, shared UBOs, repeated vessels, co-occurring counterparties, count of prior trades in this cluster and how many were previously escalated. One `Observation` per pattern found. Nothing found is a genuine result and must be reported.
`discriminates`: ["isolated transaction", "structured network activity", "ordinary commercial group structure"]

**8 · `check_contract_or_supporting_evidence`** · args `{claim: str}` where claim ∈ `bulk_discount`, `grade_difference`, `distressed_sale`, `long_term_offtake`, `inspection` · `economic`, `documentary` · cost 1
**The most important tool in the set**, because it is how the agent tests innocent explanations, and the policy gate blocks escalation unless a benign hypothesis was tested. Search the case file for a document supporting the claim. When found, return `found=true`, the `doc_id`, **the quoted clause**, and an observation with `severity=none` stating that the claim is supported. When not found, return `found=false` and an observation stating the claim is unsupported by anything in the file — with `severity` at most `medium`, because absence of evidence is weaker than evidence of absence, and your severity mapping should say so.
`discriminates`: ["the claimed commercial explanation", "an unsupported assertion"]

Optional, only if you are ahead of schedule: `check_sanctions_and_entity(entity_id)` → `network`, cost 1; and `check_container_volume_consistency(commodity, quantity, container_count)` → `physical`, cost 1, using `density_t_per_m3` against 33 m³ per TEU.

Total exhaustive cost of one call to each of the eight is **10 units**; the default budget is **6**. Do not change these numbers — Part 2's efficiency story depends on them.

---

## 8 · THE FOUR DEMO CASES — EXACT FIGURES

All three engineers build to these. They are the shared acceptance test. Every number is deliberate; do not round or improve them.

### `case_clean_001` — expected verdict RELEASE
Coffee arabica, 480 t, Santos `BRSSZ` → Rotterdam `NLRTM`, MV Pacific Dawn (2,500 t). Declared **$4,420/t** against a **$4,500/t** benchmark, −1.8%, inside the plausible band. Shipped 2026-07-02, arrived 2026-07-19, against an expected 15–19 day band. Insurance issued 2026-07-01, before shipment. Every document agrees. `case_class=clean`, `injected_anomalies=[none]`.

### `case_explainable_002` — expected verdict HOLD (RELEASE acceptable); ESCALATE is a test failure
Aluminium ingots, 1,600 t, Jebel Ali `AEJEA` → Nhava Sheva `INNSA`, MV Gulf Trader (2,800 t). Declared **$1,968/t** against **$2,400/t** — exactly **−18.0%**. Shipped 2026-08-03, arrived 2026-08-09, against a 4–7 day band. Insurance issued 2026-08-01.

The economic anomaly is real and must be discoverable. Everything else must be clean. Two independent innocent explanations must exist in your data and be findable by tools: a **three-year offtake contract with volume tiers** in the case file as a `sales_contract` document, which `check_contract_or_supporting_evidence(claim="long_term_offtake")` and `claim="bulk_discount"` both find and quote; and **six prior aluminium trades by this importer at $1,940–$2,010/t** in `historical_trades.json`, which `check_historical_trade` surfaces with a near-zero z-score.

`case_class=suspicious_but_legitimate`, `injected_anomalies=[under_invoicing]`, `anomaly_magnitudes={"under_invoicing": 0.18}`, `plant_supporting_contract=true`, `benign_explanation="Tiered pricing under a three-year offtake agreement; consistent with the importer's own six-trade history."`

**This case is the thesis of the project.** If your data does not let the agent find both innocent explanations, the demo has no argument.

### `case_suspicious_003` — expected verdict ESCALATE, four dimensions
Copper cathodes, 2,200 t, Singapore `SGSIN` → Nhava Sheva `INNSA`, **MV Ocean Star (1,800 t capacity)**. Declared **$5,500/t** against **$8,900/t**, −38.2%. Shipped 2026-08-10, arrived **2026-08-11** against a 5–8 day band. Insurance issued **2026-08-18**, eight days after shipment. Packing list describes **"Copper Scrap"** where the invoice says **"Copper Cathodes"**. **No supporting contract in the file.** Importer history is $8,600–$9,100/t. The broker recurs across three previously escalated trades in `networks.json`.

`case_class=illicit`, `injected_anomalies=[under_invoicing, capacity_exceeded, impossible_transit, insurance_after_shipment, description_drift, intermediary_reuse]`, magnitudes `{"under_invoicing": 0.382, "capacity_exceeded": 0.222, "insurance_after_shipment": 8}`, `plant_supporting_contract=false`.

Six anomalies across economic, physical, temporal, documentary, behavioural and network. Verify that each is independently discoverable by the tool that should find it.

### `case_adv_*` — generated by the attacker; expected HOLD or ESCALATE
See section 9.

---

## 9 · THE ATTACKER AGENT (`FEATURE_ATTACKER`, after T+10)

`attack(spec: AttackSpec, llm=None) -> TradeCase`. The attacker is told the thresholds a naive rule-based system would use and asked to construct a case that stays under every one of them while still moving value. It is the project's cleanest argument that dynamic investigation beats static rules — and, being the flashiest thing in the demo, it is also the most fragile, so build it defensively.

Give it `known_thresholds` such as `{"price_deviation_pct": 0.30, "capacity_utilisation": 1.00, "insurance_lag_days": 3, "transit_ratio": 0.5}`. Its action space is exactly the `AnomalyKind` list and the magnitudes in `CaseSpec.anomaly_magnitudes` — it does not write documents, it **chooses generator knobs**, which are then rendered by the same generator as every other case. This matters: it means the attacker cannot produce anything structurally impossible, and its output is auditable.

The LLM's job is one `complete_json` call returning a `CaseSpec`-shaped object plus an `evasion_notes` string. Validate the returned spec against the thresholds **in code** and clamp anything that breaches one — never trust the model to have done the arithmetic. Then generate the case, run a self-check that every individual signal lands `low` or `medium`, and if any lands `high`, reduce that magnitude and regenerate, up to a few attempts.

A good result: zinc at **−17%** (under the 30% rule), **96% capacity utilisation** (under the limit), transit at the fast edge of plausible but not impossible, **same-day insurance**, and one fresh intermediary shared with a single prior case. Every individual signal `low` or `medium`; the correlation across economic, behavioural and network is what should drive the investigator to escalate.

**Mandatory safety.** `attack()` with `llm=None`, or after any LLM failure, must return a **pre-tuned deterministic evasive case** built from a hardcoded `CaseSpec` you have verified produces the intended behaviour. Record the LLM cassettes for the attacker during hours 14–18 and ship them. Never generate this live on stage.

---

## 10 · GIT WORKFLOW

```bash
git clone https://github.com/alonek007/interpretex.git
cd interpretex

# hour 0-3: contracts and fixtures go to MAIN, not your branch
git checkout main
# ... author packages/contracts/ ...
git add packages/contracts .env.example
git commit -m "feat(contracts): v1.0.0 models, protocols, LLM adapter, helpers"
git push origin main
# ... author fixtures ...
git commit -am "feat(contracts): v0 golden fixtures for three demo cases"
git push origin main

# then move to your own branch for everything else
git checkout part1-world
git rebase origin/main
```

Commit to `part1-world` every 30 minutes and push. Before each integration window (T+5, T+10, T+14): `git fetch origin && git rebase origin/main`, then open a PR into `main` and merge with `--no-ff`. **Never merge `part2-agent` or `part3-app` into your branch** — integrate only through `main`.

Commit message prefixes: `feat(contracts)`, `feat(world)`, `feat(tools)`, `feat(data)`, `fix(world)`, `test(world)`, `docs`.

---

## 11 · ENVIRONMENT

Python 3.11, one venv at the repo root.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e packages/contracts
pip install pytest python-dotenv
cp .env.example .env    # paste the shared OPENROUTER_API_KEY and the confirmed LLM_MODEL
```

Env vars you must honour: `OPENROUTER_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_PROVIDER` (`openrouter`|`scripted`), `LLM_CACHE_MODE` (`readwrite`|`read`|`write`|`off`), `LLM_CACHE_DIR`, `FEATURE_NETWORK`, `FEATURE_ATTACKER`, `FEATURE_HISTORICAL`, `AGENT_SEED`.

---

## 12 · ORDER OF WORK WITH HOUR GATES

| Hours | Deliverable |
|---|---|
| **0 – 0.25** | Confirm the OpenRouter model slug. Post it to the team. |
| **0.25 – 1.5** | `packages/contracts/` complete, pushed to `main`. Announce. |
| **1.5 – 3** | v0 fixtures on `main`, all validating. Announce. Switch to `part1-world`. |
| **3 – 4** | Reference world: `commodities.json`, `vessels.json`, `ports.json`, `entities.json`, `historical_trades.json`, `networks.json`, plus `reference.py` loading and indexing them. |
| **4 – 5** | `generator.py` with clean-shipment construction; `documents.py` rendering all six core types; `extraction.py`. |
| **T+5** | **Integration window 1.** Push. Confirm Part 3 can list your three cases. |
| **5 – 7** | Anomaly injectors for all twelve `AnomalyKind`s; the three demo cases reproducible from seeds; `CaseLabel` correct on each. |
| **7 – 9** | Tools 1–5 against the real reference world, with unit tests. |
| **9 – 10** | Tools 6–8; `registry.py`; regenerate the fixtures from real generator output, replacing the hand-written v0 files. |
| **T+10** | **Integration window 2 — MVP GATE.** Your world + Part 2's agent must run Case 3 live in the browser. If this fails, everything in the next row is cancelled. |
| **10 – 12** | `network.py` and `network_view()` behind `FEATURE_NETWORK`. |
| **12 – 14** | `attacker.py` behind `FEATURE_ATTACKER`, including the deterministic fallback. |
| **T+14** | **Integration window 3.** Flags tested independently. |
| **14 – 18** | Tune the adversarial case until every signal reliably lands under threshold. Record LLM cassettes for all four cases and **force-add them to git**. Write `docs/10_CONTRACTS.md`. |
| **T+18** | **Freeze.** No changes to reference data or tool output after this point — Part 2's tuning depends on stability. |

---

## 13 · DEFINITION OF DONE

- [ ] `pip install -e packages/contracts` succeeds from a clean venv; `import interpretex_contracts` prints `CONTRACT_VERSION == "1.0.0"`.
- [ ] Every fixture loads and validates through its pydantic model. A CI-style test asserts this.
- [ ] `FixtureToolRegistry` satisfies the `ToolRegistry` protocol and returns canned results for all eight tools on all three cases.
- [ ] `list_cases()` returns at least the three demo cases as valid `CaseSummary` objects.
- [ ] `load_case(id)` round-trips through `model_dump_json()` and back for every case.
- [ ] `load_case(id).to_agent_view()` has no `label` attribute, asserted by a test.
- [ ] `generate_case(spec)` is deterministic: same spec and seed, byte-identical output, asserted by a test.
- [ ] All eight tools return valid `ToolResult`s with populated `sources` on all three cases.
- [ ] `registry.call("no_such_tool", {})` returns `ok=False` and does not raise. Same for every tool with malformed args.
- [ ] Case 1 produces no observation above `low` from any tool.
- [ ] Case 2 produces exactly one `medium`-or-above observation, in the `economic` dimension, and **both** `check_contract_or_supporting_evidence(claim="long_term_offtake")` and `check_historical_trade` return findings that support the innocent explanation.
- [ ] Case 3 produces `medium`-or-above observations in at least four distinct dimensions.
- [ ] Every `Observation.statement` is factual and quantified, with no verdict language. Grep your own output for "fraud", "suspicious", "launder", "illegal" and remove every occurrence outside a docstring.
- [ ] `network_view()` returns at least three `NetworkFinding`s across the seeded clusters.
- [ ] `attack(spec, llm=None)` returns a valid `TradeCase` where no single tool observation exceeds `medium`.
- [ ] LLM cassettes for all four demo cases committed with `git add -f`.
- [ ] `docs/10_CONTRACTS.md` documents every model and field.
- [ ] `pytest tests/contracts tests/world` is green.
- [ ] `HANDOFF_PART1.md` written (section 16).

---

## 14 · TESTS YOU MUST WRITE

`tests/contracts/test_fixtures_validate.py` — every fixture file parses into its model.
`tests/contracts/test_agent_view_has_no_label.py` — assert `"label" not in AgentCaseView.model_fields`.
`tests/contracts/test_llm_cache.py` — with `ScriptedLLM`, assert `complete_json` repairs one malformed response and succeeds on the retry.
`tests/world/test_determinism.py` — same spec and seed twice, identical `model_dump_json()`.
`tests/world/test_tools_never_raise.py` — parametrised over all eight tools with junk args; assert `ok=False`, no exception.
`tests/world/test_demo_cases.py` — the three per-case assertions in section 13, as three explicit tests. **These are your regression suite for the demo; run them before every push after T+10.**
`tests/world/test_no_verdict_language.py` — scan every `Observation.statement` and `ToolResult.summary` produced across all three cases for forbidden words.

---

## 15 · FAILURE MODES TO DESIGN AGAINST

**Anomalies visible to only one tool.** If you inject `capacity_exceeded` by editing the bill of lading's weight field alone, then `check_document_consistency` will report a quantity mismatch and `check_vessel_capacity` will not fire, or vice versa. Always mutate the underlying shipment and re-render all documents.

**Case 2 accidentally escalating.** If your Case 2 data contains any second anomalous dimension — insurance a day late, a slightly odd transit, a stray field mismatch — the policy gate will escalate and the project's central argument dies. Keep Case 2 surgically clean outside the price.

**Ground-truth leakage.** Do not name the adversarial case `case_evasive_fraud_01`; do not write "unusually low price" into `applicant_note`; do not put "known bad actor" in `Entity.notes`. Part 2's agent sees the document text and the applicant note.

**Verdict language creeping into tool output.** Review every `statement` and `summary` string by eye before T+18. This is the failure the judges are most likely to catch.

**Flat benchmark history.** A 13-month series that is the same number every month makes `check_historical_trade` and the z-score meaningless. Add plausible drift and a little noise.

**Unknown-entity crashes.** Every reference lookup must handle a missing key by returning an observation rather than raising. Missing data is a finding.

**Float noise breaking determinism.** Round monetary values to two decimals and percentages to one at construction time, not at display time.

---

## 16 · HANDOFF ARTEFACT

Before T+18, write `HANDOFF_PART1.md` on your branch containing: the exact public surface of `packages/world/api.py` with signatures; the full list of tool names with their `cost_units` and the dimensions each covers; the three demo case ids with their expected verdicts and which dimensions each triggers; how to regenerate fixtures in one command; which env vars change behaviour; where the LLM cassettes are and how to record more; the known limitations of the synthetic world in plain terms; and anything you deliberately did not build.

---

## 17 · IF YOU FINISH EARLY, OR RUN LATE

**Early**, in this order: add the two optional tools (`check_sanctions_and_entity`, `check_container_volume_consistency`); add two more demo cases (an over-invoicing case and a mostly-clean case with a single documentary typo that should release); enrich `raw_text` so the documents look convincing on a projector; widen the reference world to twelve commodities.

**Late**, cut in this order: the two optional tools first; then `networks.json` richness down to a single cluster; then the attacker's LLM path, shipping only the deterministic evasive case; then `historical_trades.json` down to the minimum that supports Cases 2 and 3. **Never cut:** the contracts package, the fixtures, the three demo cases, tools 1–5, or `check_contract_or_supporting_evidence` — that tool is what makes the innocent explanation testable, and without it the policy gate can never escalate.

---

## 18 · CLAIMS DISCIPLINE — APPLIES TO YOUR CODE, COMMENTS AND DATA FILE NAMES

Never imply the reference data is real. Never write a comment claiming other systems fail to perform these checks. Never let a tool conclude fraud. In `Decision.caveats` the standard three caveats you author in `STANDARD_CAVEATS` must state that reference data is synthetic and scoped to this prototype, that the output is investigative decision support and not a regulatory determination, and that anomalies may have legitimate explanations no available tool can observe. If a teammate asks you to make a tool return a risk score, say no and point them at this section.
