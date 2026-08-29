# PROMPT — PART 3 OF 3 · API, DASHBOARD, AND INTEGRATION

> Paste this entire document as the first message to your coding agent. It is self-contained: you do not need the other two prompts to do your job. Do not paraphrase or trim it.

---

## 0 · YOUR ROLE

You are the engineer building **Part 3 of 3** of a 24-hour hackathon project called **Interpretex — AI Trade Investigation Agent**. Two other engineers, each driving their own coding agent on a separate machine, are building Part 1 (the synthetic world and the investigation tools) and Part 2 (the investigator core) at the same time. The three parts will be integrated near the end of the build.

You own **the API, the dashboard, the wiring layer, and the demo**. You have two jobs beyond your own code, and they matter more than any single component:

1. **You are the integrator.** You own `wiring.py` and the stub implementations of Parts 1 and 2. Because of that, the moment Part 1 and Part 2 land, integration is a config flip rather than a negotiation. You also own both sides of the HTTP boundary, so no cross-team API discussion is ever needed.
2. **You own the demo.** The judges will not read the code. What they see is your screen. Six minutes on stage decides how the previous twenty-four hours are valued.

Repository: **https://github.com/alonek007/interpretex**
Your branch: **`part3-app`**
Contract version you consume: **1.0.0**

---

## 1 · NON-NEGOTIABLE GROUND RULES

1. **Never edit a file outside your ownership.** You own `packages/app/`, `frontend/`, `stubs/`, `wiring.py`, `scripts/`, `Makefile`, `docs/20_DEMO_SCRIPT.md`, `tests/app/`. You do **not** touch `packages/contracts/`, `packages/world/`, `packages/agent/`, `agent_prompts/`, `data/`. If you need a contract change, ask in the team channel; Part 1 owns that package and it freezes at T+2h.
2. **Your app imports the world and the agent only through `wiring.py`.** No route handler ever imports `world` or `agent` directly. Every one depends on the `WorldAPI` and `Investigator` protocols from `interpretex_contracts`. This is what lets you build the entire UI before either of the other parts exists.
3. **The frontend never imports Python and the backend never renders HTML.** JSON and Server-Sent Events across the boundary, nothing else.
4. **The UI must never crash on unexpected data.** Every panel renders from what it has and shows a quiet placeholder for what it does not. A missing payload key must not blank the screen — Part 2 will change payload shapes during the build and you must not be blocked by that. Concretely: render the timeline from `event.narration` alone, and treat every `payload` read as optional.
5. **Ground truth is judge-only.** The label endpoint returns 409 until a run for that case has completed. The label is never sent with case data, never pre-fetched, never in the initial page load.
6. **`GET /api/health` and `GET /api/flags` must work before anything else exists.** They are the team's shared signal that the stack is alive.
7. **No new heavy dependencies.** Backend: `fastapi`, `uvicorn[standard]`, `pydantic>=2.6`, `sse-starlette` is *not* needed (use a plain generator), `pytest`, `httpx` for tests. Frontend: React 18, Vite, TypeScript, Tailwind, `@tanstack/react-query`, `reactflow`, `dagre`, `framer-motion`, `react-markdown`, `lucide-react`. Nothing else without a reason.
8. **Commit to `part3-app` at least every 30 minutes.** Push.

---

## 2 · PROJECT CONTEXT (read fully — it determines what the UI must make visible)

### The problem

Banks financing international trade receive case files of six or more documents: letter of credit, commercial invoice, bill of lading, packing list, certificate of origin, insurance certificate. Existing compliance systems already do document matching, tampering detection, price anomaly checks, vessel checks, route checks, sanctions screening and TBML red-flag rules. **We do not claim those checks are new, and the UI must never imply banks lack them.**

The gap is what happens *after* a signal fires. A human investigator must connect information across documents, market data, physical constraints, timelines, counterparties and the customer's own history to decide whether the trade is actually suspicious and what to do next. That reasoning is slow, inconsistent and poorly documented. Interpretex automates that investigation layer.

### What this means for your UI

The product is not a risk score. **The product is the visible reasoning process.** A judge who watches your screen must come away able to say: *it formed rival explanations, it chose what to check next and told me what it chose not to check, it found evidence on both sides, it checked whether its signals were actually independent, and it can trace every conclusion back to a document field.*

So the UI's job is not to look impressive in the abstract. It is to make five specific things legible: **hypotheses (including benign ones), the choice of next action with rejected alternatives, evidence for AND against, corroboration across independent dimensions, and provenance.** Anything that does not serve one of those is decoration. Given the choice between a prettier layout and one more of those five made obvious, choose the latter every time.

### The moment that sells it

Case 2 is an aluminium shipment priced 18% below benchmark that is entirely legitimate. The agent finds the anomaly, forms a bulk-discount hypothesis, spends a tool call testing it, finds it supported, finds nothing wrong in any other dimension, and declines to escalate. **Your UI has to make that restraint visible and legible as a strength**, because a system that escalates every deviation is a threshold detector and everyone in the room knows it. Design a specific affordance for this: when the decision panel renders HOLD or RELEASE despite a high-severity finding, surface the refuting evidence and the tested benign hypothesis prominently rather than burying them below the fold.

### The three demo cases

| Case | Content | Verdict |
|---|---|---|
| `case_clean_001` | Coffee, consistent, price −1.8% | **RELEASE** in ≤ 3 tool calls |
| `case_explainable_002` | Aluminium −18.0%, real offtake contract, six prior trades at that price, every other dimension clean | **HOLD** (RELEASE acceptable) |
| `case_suspicious_003` | Copper −38.2%, 2,200 t cargo on an 1,800 t vessel, 1-day transit against a 5–8 day band, insurance 8 days after shipment, packing list "Scrap" vs invoice "Cathodes", no contract, broker recurring in three escalated trades | **ESCALATE**, 4+ dimensions |

Plus `case_adv_*`, generated by Part 1's attacker agent, which sits just inside every individual threshold and must be caught by correlation rather than by any single check.

---

## 3 · THE CONTRACT YOU CONSUME

`pip install -e packages/contracts` then `from interpretex_contracts import ...`. Every model has `extra="forbid"`.

**Hand-write TypeScript mirrors in `frontend/src/types/contract.ts`** in the first two hours. Do not generate them from the Python — a code generator is a dependency and a debugging surface you do not need today, and the types are small. Keep the field names byte-identical to the Python.

### 3.1 Enums

`Dimension`: `economic`, `physical`, `temporal`, `documentary`, `behavioural`, `network`
`Severity`: `none`, `low`, `medium`, `high`
`Stance`: `supports_suspicion`, `refutes_suspicion`, `neutral`
`HypothesisKind`: `benign`, `suspicious`
`HypothesisStatus`: `open`, `supported`, `weakened`, `refuted`, `untestable`
`Verdict`: `release`, `hold`, `escalate`
`SourceKind`: `document`, `reference_db`, `derived`, `model`

Assign one colour per `Dimension` and use it everywhere — timeline chips, evidence rows, graph nodes, corroboration panel, network graph. A judge learning "orange means economic" in the first thirty seconds can then read the graph without a legend. Note the British spelling of `behavioural`; getting it wrong produces a silent lookup miss.

### 3.2 Models you render

**`CaseSummary`** — `case_id`, `title`, `commodity`, `quantity`, `unit`, `total_value`, `currency`, `exporter_name`, `importer_name`, `origin_port?`, `destination_port?`, `document_count`, `received_at`, `is_adversarial`. No label.
> `is_adversarial` is the one hint the case list carries, and it is there only so the attacker demo can find its own case. **Do not surface it as a badge on the normal case cards** — a judge seeing a marker on a card before the run will reasonably suspect the agent saw one too. Filter on it, do not render it.

**`AgentCaseView`** — `case_id`, `received_at`, `bank_reference?`, `applicant_note?`, `documents: list[TradeDocument]`, `record: TradeRecord`, `available_tool_names: list[str]`.

**`TradeDocument`** — `doc_id`, `doc_type`, `issuer`, `issue_date`, `fields: dict`, `raw_text: str`, `extraction_confidence: float`.

**`TradeRecord`** — `commodity`, `commodity_grade?`, `hs_code?`, `quantity`, `unit`, `unit_price`, `currency`, `total_value`, `incoterm?`, `exporter_id`, `importer_id`, `broker_id?`, `insurer_id?`, `vessel_name?`, `imo?`, `container_count?`, `gross_weight_tons?`, `origin_port?`, `destination_port?`, `ship_date?`, `arrival_date?`, `lc_issue_date?`, `insurance_issue_date?`, `lc_number?`, `bl_number?`, `contract_reference?`.

**`ToolSpec`** — `name`, `description`, `dimensions`, `args_schema`, `cost_units`, `discriminates`.
**`ToolResult`** — `tool`, `call_id`, `args`, `ok`, `summary`, `observations`, `raw`, `sources`, `cost_units`, `latency_ms`, `error?`.
**`Observation`** — `observation_id`, `dimension`, `statement`, `severity`, `metrics`, `sources`, `expected_range?`.
**`SourceRef`** — `kind`, `ref`, `value?`, `as_of?`, `label?`.

**`Triage`** — `trade_narrative`, `initial_concerns`, `unknowns`, `dimensions_to_probe`.
**`Hypothesis`** — `hypothesis_id`, `kind`, `statement`, `explains`, `prior`, `posterior`, `status`, `discriminating_evidence_needed`, `supporting_evidence_ids`, `contradicting_evidence_ids`, `rationale?`.
**`EvidenceItem`** — `evidence_id`, `dimension`, `stance`, `statement`, `weight`, `severity`, `hypotheses_affected`, `observation_ids`, `tool_call_id?`, `sources`, `interpretation?`.
**`PlanStep`** — `step`, `reasoning`, `chosen_tool`, `chosen_args`, `targets_hypotheses`, `expected_information_gain`, `considered: [{tool, expected_information_gain, why_not}]`, `stop_reason?`.
**`BudgetState`** — `limit`, `spent`, `remaining`, `calls_made`, `tools_skipped: [{tool, reason}]`, `exhaustive_cost?`.
**`Corroboration`** — `corroborated_dimensions`, `independent_signal_count`, `refuting_dimensions`, `strongest_benign_hypothesis?`, `strongest_benign_posterior`, `narrative`.
**`Decision`** — `verdict`, `confidence`, `headline`, `rationale`, `corroboration`, `typology?`, `caveats`, `decisive_evidence_ids`.
**`EvidenceRequest`** — `item`, `why`, `resolves_hypotheses`, `priority`.
**`GraphNode`** — `id`, `kind` (`document|field|reference|tool|finding|dimension|hypothesis|decision|entity|vessel`), `label`, `dimension?`, `stance?`, `severity?`, `meta`.
**`GraphEdge`** — `source`, `target`, `relation` (`states|compared_with|produced|supports|refutes|corroborates|concludes|linked_to`), `label?`.
**`EvidenceGraph`** — `nodes`, `edges`.
**`NetworkFinding`** — `finding_id`, `pattern` (`intermediary_reuse|shared_ownership|vessel_reuse|circular_trade|price_pattern`), `statement`, `entity_ids`, `case_ids`, `severity`, `metrics`.
**`NetworkView`** — `focus_entity_id?`, `nodes`, `edges`, `findings: list[NetworkFinding]`.
**`RunMeta`** — `run_id`, `case_id`, `started_at`, `finished_at?`, `model`, `llm_calls`, `prompt_tokens`, `completion_tokens`, `wall_ms`, `replayed`, `degraded`.
**`CaseLabel`** — `case_class` (`clean|suspicious_but_legitimate|illicit|adversarial`), `injected_anomalies: list[AnomalyKind]`, `expected_verdict`, `benign_explanation?`, `evasion_notes?`, `generator_seed?`. **Judge reveal only.**
> `AnomalyKind` values you will render: `under_invoicing`, `over_invoicing`, `capacity_exceeded`, `impossible_transit`, `insurance_after_shipment`, `description_drift`, `quantity_mismatch`, `hs_code_mismatch`, `route_deviation`, `historical_deviation`, `intermediary_reuse`, `shared_ownership`, `none`. Map each to a friendly label and to the `Dimension` it belongs to, so the reveal panel can line up injected anomalies against the dimensions the agent actually found.
**`InvestigationResult`** — `meta`, `record`, `triage`, `hypotheses`, `plan_steps`, `tool_calls`, `evidence_for`, `evidence_against`, `evidence_neutral`, `budget`, `graph`, `decision`, `evidence_requests`, `report_markdown`, `events`.

### 3.3 The event stream — your primary data source

**`InvestigationEvent`** — `seq`, `ts`, `run_id`, `type`, `narration`, `payload`.

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

Guarantees Part 2 owes you, which you may rely on: `seq` starts at 0 and increments by exactly 1; `run_started` is `seq` 0; the stream terminates with `report_ready` or `run_failed`; every `tool_call_completed` follows its matching `tool_call_started`; `decision` precedes `report_ready`; **`narration` is populated on every event.**

Use `changed_ids` on `hypotheses_updated` to animate only what moved — a board where every row flashes on every update is noise, and the point is to draw the eye to the posterior that just changed.

### 3.4 The protocols you depend on

```python
class WorldAPI(Protocol):
    def list_cases(self) -> list[CaseSummary]: ...
    def load_case(self, case_id: str) -> TradeCase: ...           # raises KeyError
    def generate_case(self, spec: CaseSpec) -> TradeCase: ...
    def build_tool_registry(self, case: TradeCase) -> ToolRegistry: ...
    def network_view(self, entity_id: str | None = None, depth: int = 2) -> NetworkView: ...
    def attack(self, spec: AttackSpec, llm: LLMClient | None = None) -> TradeCase: ...

class Investigator(Protocol):
    def investigate_stream(self, case: AgentCaseView, tools: ToolRegistry, *,
                           llm=None, budget: int = 6,
                           seed: int | None = None) -> Iterator[InvestigationEvent]: ...
```

`TradeCase` carries `title`, `entities`, `vessel?` and `label: CaseLabel|None`. **Call `case.to_agent_view()` before handing it to the investigator and never serialise a `TradeCase` to the browser.** Send `AgentCaseView` on the case endpoint. This is the one mistake that would quietly destroy the demo's credibility, so put an assertion in your route that the response model has no `label` field.

---

## 4 · YOUR SCOPE — THE COMPLETE DELIVERABLE LIST

### 4.1 The integration layer — your highest-value output, due by T+5h
1. **`stubs/fake_world.py`** — a `WorldAPI` implementation over Part 1's golden fixtures if they exist, or over two hand-written JSON cases if they do not yet. Its `build_tool_registry` returns canned `ToolResult`s.
2. **`stubs/fake_agent.py`** — an `Investigator` that replays `runs/case_suspicious_003.events.jsonl` (published by Part 1 at T+3h) with a configurable delay per event, then yields `report_ready`. **This is what lets you build and rehearse the entire UI before Part 2 exists.**
3. **`wiring.py`** — reads `INTERPRETEX_WORLD` and `INTERPRETEX_AGENT` (`stub` | `real`) and returns the chosen implementations. Log which was selected at startup. **Push this to `main` by T+5h**; the other two engineers use it to verify their own components in a browser.

### 4.2 `packages/app/` — FastAPI
4. **`main.py`** — app factory, CORS, startup log line with `CONTRACT_VERSION`, world/agent mode, model, feature flags.
5. **`routes/`** — the surface in section 5, split into `cases.py`, `runs.py`, `network.py`, `meta.py`.
6. **`sse.py`** — the `sse_frame` helper and the streaming response. Section 6.
7. **`runs.py`** — the in-memory run registry: run id, case id, status, every event in order, the final result. Retains completed runs for the session so `/runs/{id}` and the report endpoint work after the stream closes. A dict is the right implementation; no database.
8. **`report.py`** — serves `report_markdown` as `text/markdown` with a filename, so a judge can download the dossier.

### 4.3 `frontend/` — React + Vite + TypeScript + Tailwind
9. Vite scaffold with the dev proxy, Tailwind, the dimension colour scale.
10. `types/contract.ts` — hand-written mirrors.
11. `hooks/useRunStream.ts` — `EventSource` plus a `useReducer` that folds events into run state. Section 7.
12. `api/client.ts` — thin typed fetch wrappers; TanStack Query for the REST reads.
13. The panels in section 8.
14. `pages/Investigation.tsx` — the layout that composes them.

### 4.4 Ops and demo
15. **`Makefile`** — `make dev`, `make api`, `make web`, `make demo`, `make test`, `make replay CASE=...`.
16. **`scripts/`** — `record_run.py` (persist a run's events and result to `runs/`), `check_health.py` (one command that verifies the whole stack), `seed_demo.py` (pre-warm the demo cases so nothing is cold on stage).
17. **`docs/20_DEMO_SCRIPT.md`** — the six-minute narrative with exact clicks, spoken lines, timings, and the fallback ladder. Section 12.
18. **`tests/app/`** — section 15.

---

## 5 · THE HTTP SURFACE — NORMATIVE, YOU OWN BOTH SIDES

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{status, contract_version, model, flags, world, agent}` |
| GET | `/api/flags` | `{budget: bool, attacker: bool, network: bool, history: bool, replay: bool}` |
| GET | `/api/tools` | `ToolSpec[]` — populated from `build_tool_registry(...).specs()` |
| GET | `/api/cases` | `CaseSummary[]` |
| GET | `/api/cases/{case_id}` | `AgentCaseView` — **no label, ever** |
| GET | `/api/cases/{case_id}/documents/{doc_id}` | `TradeDocument` including `raw_text` |
| GET | `/api/cases/{case_id}/label` | `CaseLabel` · **409 until a run for this case has completed** |
| POST | `/api/runs` | body `{case_id, budget?, mode: live\|replay, seed?}` → `{run_id}` |
| GET | `/api/runs/{run_id}/events` | **SSE stream** of `InvestigationEvent` |
| GET | `/api/runs/{run_id}` | `InvestigationResult` (404 while still running) |
| GET | `/api/runs/{run_id}/report.md` | `text/markdown` |
| GET | `/api/runs/{run_id}/baseline` | `{agent_cost, exhaustive_cost, agent_verdict, baseline_verdict, tools_skipped}` |
| POST | `/api/attack` | body `{max_dimensions, target_stealth, seed}` → `{case_id}` |
| GET | `/api/network` | `NetworkView` · query `entity_id`, `depth` |

`POST /api/runs` returns immediately with a run id; the work happens when the client opens the events stream. That split is deliberate — it keeps the SSE handler simple and makes the run resumable.

Errors: `404` unknown case or run, `409` label requested before a completed run, `503` when `wiring.py` cannot supply a real implementation, `500` with a JSON body `{detail, stage}` — never a bare HTML traceback, because a judge might see it.

---

## 6 · SERVER-SENT EVENTS

Use a plain FastAPI `StreamingResponse` over a generator. No websockets, no extra library.

```
id: <seq>
event: <type value>
data: <event.model_dump_json()>

```

Blank line terminates each frame. Headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`.

Setting `id:` to `seq` gives you `Last-Event-ID` resume for free — a browser reconnect can be served from the run registry rather than restarting the investigation. Implement that: read the `Last-Event-ID` request header, and if present replay the retained events after it before continuing. It costs ten lines and it means an accidental refresh on stage is survivable.

Also: append every event to the run registry as you yield it, so the registry is the source of truth for `/runs/{id}` and for resume. Emit a comment line (`: keepalive`) if more than fifteen seconds pass with nothing to send, in case Part 2's heartbeats do not arrive.

**Test the stream with `curl -N http://localhost:8000/api/runs/<id>/events` and confirm frames arrive incrementally before you write a single line of UI code.** Debugging a buffering problem through React is miserable; debugging it through curl takes two minutes. If frames arrive all at once, something in the chain is buffering — check that your generator is not accidentally a list comprehension and that no middleware is collecting the body.

Wrap the generator body in a try/except that yields a `run_failed` frame and closes cleanly. A stream that dies without a terminal frame leaves the UI spinning forever, which looks far worse than a visible error.

---

## 7 · FRONTEND STATE

One `useReducer` folding the event stream into:

```ts
{ runId, status: 'idle'|'streaming'|'done'|'failed',
  events: InvestigationEvent[],
  record, triage, hypotheses: Hypothesis[],
  planSteps: PlanStep[], toolCalls: ToolResult[],
  evidence: EvidenceItem[], budget, corroboration, decision,
  requests: EvidenceRequest[], graph: EvidenceGraph,
  report: string|null, degraded: boolean }
```

Every event appends to `events` and, if recognised, updates the derived slice. **An unrecognised event type appends to `events` and is otherwise ignored.** Never throw on an unknown type or a missing payload key — Part 2 will add and reshape things during the build and your UI must keep working.

Merge `hypotheses_updated` by `hypothesis_id` rather than replacing the array, so the list order stays stable and React does not remount rows. Append `evidence_added` (Part 2 dedupes upstream). Fold `graph_updated` by concatenating `nodes_added` and `edges_added`, deduping by id.

Guard the `EventSource` against React 18 StrictMode double-mounting — an effect that opens a stream will run twice in development and you will see duplicated events and wonder if Part 2 is broken. Use a ref guard and close the source in the cleanup function.

Drive **every** panel from this one state object. Do not let panels fetch independently mid-run; that is how the timeline and the graph end up disagreeing on stage.

---

## 8 · THE PANELS

Layout: a case rail on the left, the live timeline in the centre, and a tabbed inspector on the right (Hypotheses · Evidence · Graph · Network · Dossier), with the decision panel pinned across the bottom.

**Case selector.** Cards from `/api/cases` showing `title`, commodity, quantity and unit, total value, exporter and importer names, route, and document count. No label, no `is_adversarial` badge, no hint of the expected verdict. A prominent "Investigate" button and a budget selector.

**Live timeline — the centrepiece.** One row per event, newest at the bottom, auto-scrolled. **Render `narration` as the row's text and nothing else as required**, then enrich per type: a tool chip for `tool_call_started`, a dimension-coloured severity badge for `evidence_added`, an elapsed-time gutter. Rows expand to show the payload. This ordering matters — because the row is built from `narration`, the timeline still reads correctly even if a payload shape changes underneath you.

Type a visible latency into it. Events arriving instantly read as a canned animation; events arriving as the work happens read as real. Do not fake delay on a real run, but on replay use 400–900 ms per event so it is watchable.

**Hypothesis board.** One card per hypothesis, grouped by `kind` with **benign explicitly labelled and visually equal to suspicious** — this is a substantive point, not a styling one: the board is the visible proof the system considers innocent explanations. Show `prior → posterior` as a small bar that animates on change, a status pill (`open`, `supported`, `weakened`, `refuted`, `untestable`), the `rationale`, and links to the evidence ids that moved it. Animate only ids in `changed_ids`.

**Evidence ledger.** Two columns, FOR and AGAINST, dimension-coloured, sorted by weight. Each row: statement, dimension, severity, weight, `interpretation`, and expandable `sources` showing each `SourceRef` as `kind · ref · value · as_of`. **If AGAINST is empty, render an explicit "no refuting evidence found — the following benign explanations were tested and not supported" block listing them.** An empty column with no explanation reads as confirmation bias to exactly the kind of judge you are trying to convince.

**Evidence graph.** React Flow with a dagre left-to-right layered layout. Node shapes by `kind`, colours by `dimension`, red/green ring by `stance`. Nodes fade in with framer-motion as `graph_updated` arrives — **this single effect will carry the demo**, so spend real time on it. Clicking a finding node highlights its ancestor path back to the document field it came from, which is your provenance story made interactive. Add a "fit view" control and re-run layout on each batch, but debounce it so the graph does not thrash.

**Network graph** (`FEATURE_NETWORK`). A separate React Flow view from `/api/network`, centred on `focus_entity_id`, entity nodes with edges labelled by relation, a depth control, and each `NetworkFinding` listed beside the graph with its `pattern`, `statement`, `severity` and the `entity_ids` it implicates — clicking a finding highlights those nodes. Do not overstate this in the UI copy: it is a synthetic network, and a `near_match` sanctions status must read "name similar to a screening-list entry — requires manual review", never "sanctioned".

**Budget meter** (`FEATURE_BUDGET`). Spent versus limit, cost per call, `exhaustive_cost` as a ghost bar, and `tools_skipped` with each reason. The line that lands is "it reached the same verdict spending 6 units instead of 10, and here is what it decided not to check and why."

**Plan / rejected-alternatives panel.** For each `PlanStep`, the chosen tool with its expected information gain, and the `considered` list with each rejected tool's gain and `why_not`. This is small and easy to skip, and it is one of the two panels that most distinguishes this from a pipeline. Do not skip it.

**Decision panel.** Verdict as a large coloured banner (green RELEASE, amber HOLD, red ESCALATE), `headline`, confidence, `rationale` with evidence ids as clickable chips that jump to the ledger row, corroborated dimensions as chips, `typology` when present, the caveats always visible, and the evidence requests as a prioritised table. When `meta.degraded` is true, show a quiet "reasoning produced without model inference" badge rather than hiding it.

**Dossier viewer.** `report_markdown` via `react-markdown` with Tailwind typography, plus a download button hitting `/api/runs/{run_id}/report.md`.

**Judge reveal.** A single button, enabled only after `report_ready`, that fetches `/api/cases/{id}/label` and lays the label's `injected_anomalies` against what the agent actually found, with a match indicator per anomaly, plus `case_class`, `expected_verdict` versus the agent's verdict, `benign_explanation` on the legitimate case and `evasion_notes` on the adversarial one. This is the highest-impact ten lines of UI in the project: it converts "nice demo" into "measurably correct". Keep it disabled and visually locked until the run completes so nobody can suspect the agent saw it.

**Attacker panel** (`FEATURE_ATTACKER`). A form over `AttackSpec` — `max_dimensions`, `target_stealth`, `seed`, with `known_thresholds` shown read-only so the audience can see what the attacker was told — posting to `/api/attack`, then an automatic run on the returned `case_id`, displayed beside a table of the individual threshold checks that all pass. The story is "every single check passes; the correlation does not."

**Replay mode.** A run selector over `runs/*.events.jsonl` that streams a recorded run through the same reducer. Same UI, no network, no API key. This is your stage insurance and it must work by T+14, not T+23.

---

## 9 · ENVIRONMENT AND FLAGS

```
OPENROUTER_API_KEY=          # shared team key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=                   # exact "Ox Alpha" slug, confirmed by Part 1 at T+0.25
LLM_CACHE_MODE=off           # off | write | read   ← read on stage
LLM_CACHE_DIR=.llm_cache
INTERPRETEX_WORLD=stub       # stub | real
INTERPRETEX_AGENT=stub       # stub | real
FEATURE_BUDGET=1
FEATURE_ATTACKER=1
FEATURE_NETWORK=1
FEATURE_HISTORY=1
FEATURE_REPLAY=1
AGENT_BUDGET_DEFAULT=6
```

Every flag is readable at `/api/flags` and the UI hides unavailable panels rather than rendering broken ones. Vite dev proxy `/api` → `http://localhost:8000` so CORS never appears in development; keep permissive CORS in the app anyway for the stage laptop.

---

## 10 · GIT WORKFLOW

```bash
git clone https://github.com/alonek007/interpretex.git
cd interpretex
git checkout part3-app            # branch off main, created at kickoff
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e packages/contracts # available on main from T+1.5h
pip install "fastapi" "uvicorn[standard]" pytest httpx python-dotenv
cd frontend && npm create vite@latest . -- --template react-ts && npm install
cp .env.example .env              # paste the shared key and LLM_MODEL
```

Commit every 30 minutes and push. Before each integration window (T+5, T+10, T+14): `git fetch origin && git rebase origin/main`, then PR into `main`, merge `--no-ff`. **Never merge `part1-world` or `part2-agent` into your branch** — integrate only through `main`. `stubs/` and `wiring.py` go to `main` at T+5h because the other two need them.

Commit prefixes: `feat(app)`, `feat(web)`, `feat(wiring)`, `fix(app)`, `fix(web)`, `test(app)`, `docs(demo)`.

**Until `packages/contracts` lands on `main` at T+1.5h, do not idle and do not write your own copy of it.** Scaffold Vite, Tailwind and the layout shell, which need nothing from anyone.

---

## 11 · ORDER OF WORK WITH HOUR GATES

| Hours | Deliverable |
|---|---|
| **0 – 1.5** | Vite + React + TS + Tailwind scaffold. Layout shell with all panel positions as empty cards. Dimension colour scale. FastAPI app with `/api/health` and `/api/flags` returning static values. `make dev` running both. |
| **1.5 – 2.5** | `pip install -e packages/contracts`; verify `CONTRACT_VERSION == "1.0.0"`. Hand-write `types/contract.ts`. `stubs/fake_world.py` over two hand-written cases. |
| **2.5 – 4** | `stubs/fake_agent.py` replaying Part 1's `case_suspicious_003.events.jsonl` (on `main` from T+3h). `sse.py`. `POST /api/runs` and `GET /api/runs/{id}/events`. **Verify with `curl -N` before touching React.** |
| **4 – 5** | `wiring.py`. `useRunStream` + reducer. Live timeline rendering the replayed trace end to end. |
| **T+5** | **Integration window 1.** Push `stubs/` and `wiring.py` to `main`. Announce it — the other two now have a browser to verify against. |
| **5 – 7** | Hypothesis board, evidence ledger, decision panel, dossier viewer. All driven by the replayed trace. |
| **7 – 9** | Evidence graph with React Flow + dagre + framer-motion fade-in. The single highest-value visual in the project. |
| **9 – 10** | Case selector, `/api/cases`, `/api/cases/{id}`, document viewer, `/api/tools`. Flip `INTERPRETEX_WORLD=real` when Part 1's world lands. |
| **T+10** | **Integration window 2 — MVP GATE.** `INTERPRETEX_WORLD=real`, `INTERPRETEX_AGENT=real`, Case 3 run live in the browser, escalation rendered. If this fails, all advanced features are cancelled. |
| **10 – 12** | Budget meter, plan/rejected-alternatives panel, baseline endpoint. |
| **12 – 14** | Network graph, attacker panel, judge reveal, replay mode. Record runs for all four cases with `record_run.py`. |
| **T+14** | **Integration window 3.** Everything on `main`. |
| **14 – 18** | Visual polish: transitions, empty states, loading skeletons, the verdict banner, typography. Write `docs/20_DEMO_SCRIPT.md`. Rehearse twice with a timer. |
| **T+18** | **Freeze.** `LLM_CACHE_MODE=read`. Three clean dry runs on the actual stage laptop and the actual browser. **Record a screen capture of a perfect run as the last-resort fallback.** |
| **18 – 24** | Rehearse. Fix only demo-path bugs. No refactors. |

---

## 12 · THE DEMO SCRIPT

`docs/20_DEMO_SCRIPT.md`, six minutes, with exact clicks and spoken lines. Structure:

**0:00–0:30 · The gap.** "Banks already have these checks. What they do not have is the investigation that happens after a check fires — and that is what we built." Say this first and explicitly. It pre-empts the single most dangerous question in the room.

**0:30–1:45 · Case 3, live.** Click Investigate and narrate the timeline as it streams: the triage, the rival hypotheses appearing, the plan step choosing the vessel check *and listing what it chose not to check*, the evidence landing on both sides, the graph growing.

**1:45–2:30 · Corroboration and verdict.** Four independent dimensions from four different source fields against three reference sources. ESCALATE with careful typology wording. Show the caveats. Open the dossier.

**2:30–3:30 · Case 2 — the restraint.** The −18% anomaly, the bulk-discount hypothesis, the tool call spent testing it, the supporting contract and history, and the refusal to escalate. Say the line: "a single-dimension anomaly with a corroborated benign explanation does not meet the escalation bar — and that rule is deterministic code, not a model's opinion."

**3:30–4:15 · The judge reveal.** Press it on both cases. Planted signals versus found signals.

**4:15–5:00 · The adversarial case.** Every individual check passes; the correlation does not.

**5:00–5:30 · Budget and provenance.** Six units against ten, same verdict; click a finding node and walk the chain back to the invoice field.

**5:30–6:00 · Honest close.** Synthetic environment, controlled reference data, decision-support for a human reviewer, and what production integration would require.

Then a **Q&A crib sheet** with one-line answers to: how do you stop the model hallucinating a verdict (the deterministic gate, and the model's suggestion never reaches `Decision.verdict`); how is this different from a rules engine (rules do not generate rival hypotheses, choose what to check next, or record what they chose not to check); what if the data is real (the tool interface is the seam — swap the implementations, the investigation layer is unchanged); what is your false positive rate (here is the eval harness, on N runs of the synthetic suite, and here is why we will not extrapolate that to production); does this replace compliance officers (no — it produces the investigation packet a human reviews and signs).

And a **fallback ladder**: live with the real LLM → cassette replay with `LLM_CACHE_MODE=read` → recorded event replay with no network → screen capture. Know the exact keystrokes for each transition and rehearse the second one at least once, because it is the one you will actually need.

---

## 13 · DEFINITION OF DONE

- [ ] `make dev` starts API and web together; `/api/health` returns `contract_version`, both modes, the model and the flags.
- [ ] With `INTERPRETEX_WORLD=stub INTERPRETEX_AGENT=stub`, the whole UI works with no API key and no network.
- [ ] With both `real`, all four demo cases run end to end in the browser.
- [ ] SSE verified with `curl -N`: frames arrive incrementally, each has `id`, `event` and `data`, and the stream terminates with `report_ready` or `run_failed`.
- [ ] A browser refresh mid-run resumes from `Last-Event-ID` without restarting the investigation.
- [ ] An unknown event type or a missing payload key does not break any panel; there is a test.
- [ ] `/api/cases/{id}` response contains no `label` key, asserted by a test.
- [ ] `/api/cases/{id}/label` returns 409 before a completed run and the `CaseLabel` after.
- [ ] The judge reveal button is disabled until `report_ready`.
- [ ] Timeline, hypothesis board, evidence ledger, graph, decision panel and dossier all render from a single replayed trace with no live LLM.
- [ ] The evidence graph animates new nodes and highlights the ancestor path of a clicked finding.
- [ ] The empty-AGAINST case renders the explicit "benign explanations tested" block.
- [ ] `considered` alternatives are visible in the UI for at least one step of the Case 3 run.
- [ ] Budget meter shows spent, limit, `exhaustive_cost` and every `tools_skipped` reason.
- [ ] `/api/runs/{id}/report.md` downloads as markdown.
- [ ] Replay mode works with no network and no API key.
- [ ] `docs/20_DEMO_SCRIPT.md` complete with the Q&A crib sheet and the fallback ladder.
- [ ] A screen capture of a perfect run exists.
- [ ] `pytest tests/app` is green.
- [ ] `HANDOFF_PART3.md` written (section 17).

---

## 14 · FAILURE MODES TO DESIGN AGAINST

**Building the UI last.** The most common way hackathon projects with strong backends lose. Your timeline and graph must be working against a replayed trace by T+5, long before the real agent exists. That is the whole point of `fake_agent.py`.

**SSE buffered somewhere in the chain.** Events arrive in one burst at the end and the "live reasoning" story collapses. Catch it early with `curl -N`, not through React.

**React 18 StrictMode double-opening the EventSource.** You will see duplicated events in development and blame Part 2. Ref-guard the effect.

**A panel crashing on a missing payload key.** One `undefined.map` blanks the screen mid-demo. Optional-chain every payload read and give every list a default.

**The label leaking.** Serialising a `TradeCase` instead of an `AgentCaseView` puts ground truth in a network response a judge could open. Assert against it in a test.

**Waiting on Part 1 or Part 2.** You never need to. Stubs first, real second, and the flip is one environment variable.

**Live LLM on stage.** Rate limits, latency spikes, a stealth model deprecated mid-event. Cassettes from T+18, and rehearse the fallback.

**Cold start on stage.** The first run of the session is always the slowest. Run `seed_demo.py` before you walk up.

**Too many panels, none legible.** Six half-finished panels are worse than four excellent ones. If you are behind at T+16, cut the network graph and the attacker panel and make the timeline, graph, hypothesis board and decision panel beautiful.

**Untested browser.** Test in whatever browser the demo laptop will actually use, on the actual screen resolution, with the actual projector aspect ratio if you can. Check the font sizes from three metres away.

---

## 15 · TESTS YOU MUST WRITE

`tests/app/test_health.py` — health and flags shapes.
`tests/app/test_no_label_leak.py` — `/api/cases/{id}` has no `label` key anywhere in the JSON, recursively.
`tests/app/test_label_gate.py` — 409 before a completed run, 200 after.
`tests/app/test_sse_frames.py` — parse the raw stream with `httpx`, assert frame format, gapless `id`s from 0, and a terminal `report_ready`.
`tests/app/test_run_registry.py` — `/runs/{id}` 404 while running, full result after; `Last-Event-ID` resume returns only later events.
`tests/app/test_wiring.py` — both modes construct without error; `503` when a real implementation is missing.
`frontend` reducer tests — unknown event type is appended and ignored; missing payload keys do not throw; `hypotheses_updated` merges by id rather than replacing; `graph_updated` dedupes by node id.

---

## 16 · IF YOU FINISH EARLY, OR RUN LATE

**Early**, in this order: a side-by-side comparison view running two budgets on the same case so the information-gain claim becomes visual; a document viewer that highlights the exact field a `SourceRef` points at, which makes provenance tangible; a keyboard-driven demo mode so you never fumble a click on stage; a print stylesheet for the dossier; a case-generation form exposing Part 1's `CaseSpec`.

**Late**, cut in this order: the attacker panel (run it from the terminal and show the resulting case instead); the network graph; the document viewer; the baseline comparison. **Never cut:** the live timeline, the evidence graph, the decision panel, the dossier, replay mode, or the judge reveal.

---

## 17 · HANDOFF ARTEFACT

Before T+18, write `HANDOFF_PART3.md` containing: every endpoint with its request and response shape; the exact SSE frame format and the resume behaviour; how to switch stub and real modes; how to record and replay runs; every environment variable and flag; the demo click path in one screen; the fallback ladder with exact keystrokes; and anything fragile that must not be touched.

---

## 18 · CLAIMS DISCIPLINE — YOUR UI COPY IS THE MOST VISIBLE SURFACE OF ALL

Every string a judge can read is a claim the team has to defend. Yours are the strings they will read most.

Never write, in any label, tooltip, heading or empty state: "fraud detected", "money laundering confirmed", "proven", "guaranteed", "real-time market data", "sanctioned entity" (use "name similar to a screening-list entry — requires manual review"), "replaces compliance review", or any implication that banks lack these checks today.

Do write: "Indicators consistent with potential under-invoicing / trade-value manipulation"; "recommendation for human review"; "synthetic reference data"; "no significant corroborated anomaly identified in the dimensions examined" rather than "legitimate". Put a persistent, small, honest footer on the dashboard: **"Prototype. Synthetic trade data and controlled reference sources. Decision support for a human reviewer, not an automated compliance determination."** It costs one line, it is true, and it earns more credit with a knowledgeable judge than any feature you could add in the same minute.
