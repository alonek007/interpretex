# PROMPT — PART 2 OF 3 · THE INVESTIGATOR CORE

> Paste this entire document as the first message to your coding agent. It is self-contained: you do not need the other two prompts to do your job. Do not paraphrase or trim it.

---

## 0 · YOUR ROLE

You are the engineer building **Part 2 of 3** of a 24-hour hackathon project called **Interpretex — AI Trade Investigation Agent**. Two other engineers, each driving their own coding agent on a separate machine, are building Part 1 (the synthetic world and the investigation tools) and Part 3 (the API and dashboard) at the same time. The three parts will be integrated near the end of the build.

You own **the brain**: triage, hypothesis generation, the planner that decides what to investigate next, the evidence ledger, the corroboration analyser, the deterministic decision policy, the evidence-request generator, the evidence graph, the dossier writer, the event stream, and the evaluation harness.

Repository: **https://github.com/alonek007/interpretex**
Your branch: **`part2-agent`**
Contract version you consume: **1.0.0**

**You own the novelty of this project.** Parts 1 and 3 could each be described as competent engineering. Your layer is the part that is defensible in front of a hostile technical judge, and every one of the nine novelty claims in section 2 is implemented by you. Build accordingly.

---

## 1 · NON-NEGOTIABLE GROUND RULES

1. **You import nothing from Part 1.** Not once, not temporarily, not "just for a test". Your agent receives a `ToolRegistry` and an `LLMClient` by dependency injection, both defined as `typing.Protocol` in the shared `interpretex_contracts` package. This is the reason integration will take an hour instead of a day. If you `import world` anywhere, you have broken the build's central design decision.
2. **Never edit a file outside your ownership.** You own `packages/agent/`, `agent_prompts/`, `tests/agent/`. You do **not** touch `packages/contracts/`, `packages/world/`, `packages/app/`, `frontend/`, `stubs/`, `wiring.py`, `data/`. If you need a contract change, ask in the team channel; Part 1 owns that package and it freezes at T+2h.
3. **The LLM proposes; a deterministic policy disposes.** The final verdict is computed by fixed rules over the evidence ledger, never taken from the model's opinion. When the policy and the model disagree, the policy wins and the disagreement is recorded in `decision.rationale`. This is the single strongest answer you have when a judge asks how you stop the model hallucinating an escalation — so it must be literally true in the code.
4. **Never look at ground truth.** Your entry point takes an `AgentCaseView`, which has no `label` field. Do not add one, do not accept a `TradeCase`, do not read fixture files that contain labels anywhere in the agent package. Your eval harness may read labels — but it lives in `eval.py` and the agent must never import from it.
5. **`investigate_stream` must be a generator.** Part 3 pipes it straight into Server-Sent Events with no queue and no thread. Yield events as they happen, not in a batch at the end.
6. **The agent must never crash.** Any LLM failure, malformed JSON, tool error or unexpected state degrades into the deterministic fallback path and still yields a valid `InvestigationResult` with `meta.degraded=true`. A stack trace on stage is the worst outcome in this project.
7. **Determinism where possible.** Seed any randomness from the `seed` argument using a local `random.Random` instance. Temperature stays low: 0.1 for structured calls, at most 0.3 for prose. The team runs `LLM_CACHE_MODE=read` on stage, which replays cassettes from disk, so your call sequence must be stable for the same input.
8. **No agent framework.** No LangChain, no LangGraph, no CrewAI, no AutoGen, no OpenAI Agents SDK. Hand-roll the loop in roughly 200 lines. This is a deliberate decision, not a shortcut: the reasoning trace *is* the product, and owning the loop means the trace is a first-class output rather than something scraped out of framework callbacks. Be ready to say that out loud.
9. **No new dependencies** beyond `pydantic>=2.6`, `jsonschema>=4.21`, `pytest`. Python 3.11.
10. **Commit to `part2-agent` at least every 30 minutes.** Push.

---

## 2 · PROJECT CONTEXT (read fully — your design decisions depend on it)

### The problem

Banks financing international trade receive case files of six or more documents: letter of credit, commercial invoice, bill of lading, packing list, certificate of origin, insurance certificate. Existing compliance systems already do document matching, tampering detection, price anomaly checks, vessel checks, route checks, sanctions screening and TBML red-flag rules. **We do not claim those checks are new, and we never claim banks lack them.**

The gap is what happens *after* a signal fires. A human investigator must then connect information across documents, market data, physical constraints, timelines, counterparties and the customer's own history to decide whether the trade is actually suspicious and what to do next. That reasoning is slow, inconsistent between investigators and poorly documented. **Interpretex automates that investigation layer, and you are building it.**

### The principle that shapes everything you write

**An anomaly is a question, not a conclusion.** A price 20% below benchmark may be a bulk discount, a lower grade, a distressed sale, a long-term offtake contract, or a data-entry error — or it may be under-invoicing. The system's credibility rests on it visibly trying to talk itself out of a suspicion before escalating. An agent that escalates on every deviation is a threshold detector with a language model bolted on, and a knowledgeable judge will say so.

### The nine things that make this novel, all of which you implement

1. **The deterministic policy gate over LLM-produced evidence** — the model proposes, fixed rules dispose.
2. **Escalation is blocked unless a benign hypothesis was actually tested** — a structural, checkable anti-confirmation-bias mechanism, not a polite instruction in a prompt.
3. **Corroboration defined across independent dimensions**, with single-dimension escalation forbidden.
4. **Hypothesis-driven investigation** — rival explanations generated and discriminated between, rather than anomalies labelled.
5. **Dynamic next-step selection with rejected candidates logged** — what distinguishes an agent from a pipeline.
6. **An auditable provenance DAG** where every conclusion traces to a document field or a dated reference lookup.
7. **Automatic evidence requests** tied to the specific hypotheses they would resolve.
8. **Investigation budget with information-gain prioritisation**, measured against an exhaustive baseline.
9. **Adversarial validation** — Part 1's attacker constructs threshold-evading cases and your investigator has to catch them by correlation.

### The three demo verdicts you must hit

| Case | Content | Required verdict |
|---|---|---|
| `case_clean_001` | Coffee, everything consistent, price −1.8% | **RELEASE** in ≤ 3 tool calls |
| `case_explainable_002` | Aluminium at −18.0%, but a real offtake contract and six prior trades at that price; every other dimension clean | **HOLD** (RELEASE acceptable). **ESCALATE is a test failure.** |
| `case_suspicious_003` | Copper at −38.2%, cargo 2,200 t on an 1,800 t vessel, 1-day transit against a 5–8 day band, insurance 8 days after shipment, packing list says "Scrap" vs invoice "Cathodes", no contract, history $8,600–9,100/t, broker recurs in three escalated trades | **ESCALATE**, four or more dimensions |

Case 2 is the thesis. The agent must find the price anomaly, generate the bulk-discount hypothesis, **spend a tool call testing it**, find it supported by two independent sources, find no anomaly in any other dimension, and then explicitly state that a single-dimension economic anomaly with a corroborated benign explanation does not meet the escalation bar. Getting that behaviour out of the policy gate — rather than hoping the model behaves — is your most important task today.

---

## 3 · THE INVESTIGATION LOOP YOU ARE BUILDING

```
AgentCaseView + ToolRegistry + LLMClient + budget
        │
        ├─ emit run_started, case_loaded
        ▼
   TRIAGE ─────────────── 1 LLM call, structured
        │   what does this trade claim to be, in plain English?
        │   what looks unusual on the face of the documents?
        │   what cannot be judged from paper alone?
        │   which dimensions are worth probing?
        ├─ emit triage
        ▼
 HYPOTHESISE ──────────── 1 LLM call, structured
        │   for every concern, rival explanations —
        │   at least one benign AND one suspicious per concern
        ├─ emit hypotheses_updated
        ▼
  ┌── LOOP (max AGENT_MAX_STEPS, spend ≤ budget) ──────────────────┐
  │     PLAN ──────────── 1 LLM call, structured                   │
  │       score every affordable tool for expected information     │
  │       gain against the live hypotheses; choose one; record      │
  │       what you rejected and why                                │
  │       ├─ emit plan_step, budget_updated                        │
  │       ▼                                                        │
  │     ACT ───────────── tools.call(name, args)                   │
  │       ├─ emit tool_call_started, tool_call_completed           │
  │       ▼                                                        │
  │   INTERPRET ───────── 1 LLM call, structured                   │
  │       each observation → EvidenceItem:                         │
  │       dimension, stance, weight, hypotheses affected,          │
  │       provenance, one-line interpretation                      │
  │       ├─ emit evidence_added (one per item), graph_updated     │
  │       ▼                                                        │
  │    UPDATE ─────────── same LLM call as INTERPRET               │
  │       move posteriors; set status refuted / supported / …      │
  │       ├─ emit hypotheses_updated                               │
  │       ▼                                                        │
  │   STOP? ──── deterministic, no LLM ───────────────────────────  │
  │       sufficient_evidence | budget_exhausted |                  │
  │       no_informative_tool_left  → break                        │
  └────────────────────────────────────────────────────────────────┘
        ▼
 CORROBORATE ─────────── deterministic + 1 LLM call for the narrative
        ├─ emit corroboration
        ▼
   DECIDE ───────────── DETERMINISTIC POLICY GATE, no LLM
        ├─ emit decision
        ▼
 ASK FOR MORE ────────── 1 LLM call, structured
        ├─ emit evidence_requested
        ▼
  WRITE UP ───────────── 1 LLM call for prose, template for structure
        └─ emit report_ready  { result, report_markdown }
```

Budget: **7 to 9 LLM calls for a full investigation.** If you find yourself needing fifteen, you have put logic in the model that belongs in Python.

---

## 4 · YOUR SCOPE — THE COMPLETE DELIVERABLE LIST

### 4.1 `agent_prompts/*.md` — the four prompt templates, authored as files, not string literals
1. `triage.md`, `hypothesise.md`, `plan.md`, `interpret.md`, plus `corroborate.md`, `evidence_request.md`, `report.md`. Load them at import and format with `str.format`. Keeping them in files means you can iterate on wording without touching logic, and a judge can read them.

### 4.2 `packages/agent/`
2. **`api.py`** — the only public surface: `investigate_stream(...)` and `investigate(...)`. Signatures in section 5.6.
3. **`loop.py`** — the orchestrator: state, event emission through `SeqEmitter`, step cap, budget accounting, degradation on failure.
4. **`triage.py`** — one structured LLM call producing a `Triage`.
5. **`hypotheses.py`** — hypothesis generation and posterior updating, with the hard rule that every concern gets at least one `benign` and one `suspicious` hypothesis.
6. **`planner.py`** — tool selection with information-gain scoring and rejected-candidate logging. Section 7.
7. **`ledger.py`** — the evidence ledger: observations → `EvidenceItem`s with stance, weight and provenance; dedupe; partition into for/against/neutral.
8. **`corroboration.py`** — dimensional independence analysis producing a `Corroboration`. Section 8.
9. **`policy.py`** — the deterministic decision gate. Section 9. **Pure function, no LLM, no I/O, fully unit tested.**
10. **`requests.py`** — the evidence-request generator. Section 10.
11. **`graph.py`** — incremental evidence-graph construction from `SourceRef`s. Section 11.
12. **`report.py`** — the dossier writer. Section 12.
13. **`fallback.py`** — the deterministic no-LLM investigation path. Section 13.
14. **`eval.py`** — the evaluation harness. Section 14. **May read ground truth; the agent must never import it.**
15. **`schemas.py`** — the JSON Schemas passed to `complete_json`, one per structured call.

### 4.3 Advanced feature (behind `FEATURE_BUDGET`, after the T+10 MVP gate)
16. Information-gain scoring, budget enforcement, `tools_skipped` with reasons, and the exhaustive-baseline comparison that Part 3 renders as a meter.

---

## 5 · THE CONTRACT (authored by Part 1 on `main`; you consume and produce these)

`pip install -e packages/contracts` then `from interpretex_contracts import ...`. Every model has `extra="forbid"`, so a wrong field name fails immediately rather than at hour 20. Field names below are normative.

### 5.1 What you receive

**`AgentCaseView`** — `case_id`, `received_at`, `bank_reference?`, `applicant_note?`, `documents: list[TradeDocument]`, `record: TradeRecord`, `available_tool_names: list[str]`. No `label`.

**`TradeDocument`** — `doc_id`, `doc_type`, `issuer`, `issue_date`, `fields: dict`, `raw_text: str`, `extraction_confidence: float`

**`TradeRecord`** — `commodity`, `commodity_grade?`, `hs_code?`, `quantity`, `unit`, `unit_price`, `currency`, `total_value`, `incoterm?`, `exporter_id`, `importer_id`, `broker_id?`, `insurer_id?`, `vessel_name?`, `imo?`, `container_count?`, `gross_weight_tons?`, `origin_port?`, `destination_port?`, `ship_date?`, `arrival_date?`, `lc_issue_date?`, `insurance_issue_date?`, `lc_number?`, `bl_number?`, `contract_reference?`

**`ToolRegistry`** protocol — `specs() -> list[ToolSpec]` and `call(name, args) -> ToolResult`. `call` never raises; failures come back as `ok=False` with `error` set. Handle that: a failed tool call must produce a `plan_step` that re-plans rather than a crash. **Test this path explicitly — it will happen on stage.**

**`ToolSpec`** — `name`, `description`, `dimensions: list[Dimension]`, `args_schema: dict`, `cost_units: int`, `discriminates: list[str]`. You render `name`, `description`, `dimensions`, `cost_units` and `discriminates` straight into the planner prompt.

**`ToolResult`** — `tool`, `call_id`, `args`, `ok`, `summary` (≤200 chars, read this first), `observations: list[Observation]`, `raw: dict`, `sources: list[SourceRef]`, `cost_units`, `latency_ms`, `error?`

**`Observation`** — `observation_id`, `dimension: Dimension`, `statement`, `severity: Severity`, `metrics: dict[str, float]`, `sources: list[SourceRef]`, `expected_range?`
> `severity` is deviation salience emitted by a tool. **It is not a verdict and not a stance.** A `high` severity observation can become evidence *against* suspicion once explained — that is exactly what happens in Case 2.

**`SourceRef`** — `kind: SourceKind`, `ref: str`, `value?`, `as_of?`, `label?`. `ref` formats: `"<doc_id>.<field>"`, `"<table>/<key>[/<as_of>]"`, `"<tool>:<metric>"`.

**`LLMClient`** protocol — `complete(*, system, messages, temperature, max_tokens, tag) -> str` and `complete_json(*, system, messages, schema, temperature, max_tokens, tag, retries) -> dict`. `complete_json` validates against your JSON Schema locally and re-prompts on failure, then raises `LLMJsonError`. **Always pass a distinct `tag`** (`"triage"`, `"plan.s3"`, `"interpret.TC-004"`) — cassette filenames are built from it and you will need to grep them.

Note that `complete_json` does not use provider-side structured output, because tool-calling and `response_format` support is inconsistent across OpenRouter models. Your schemas are enforced locally. Keep them small and flat; deeply nested schemas fail validation more often.

### 5.2 The eight tools you plan over

| Tool | Args | Dimensions | Cost |
|---|---|---|---|
| `read_document` | `doc_type?`, `doc_id?` | documentary | 1 |
| `check_document_consistency` | `fields?` | documentary | 1 |
| `check_price_benchmark` | `commodity`, `grade?`, `quantity`, `as_of_date`, `declared_unit_price` | economic | 1 |
| `check_vessel_capacity` | `vessel_name`, `claimed_weight_tons` | physical | 1 |
| `check_transit_plausibility` | `origin_port`, `destination_port`, `ship_date`, `arrival_date`, `vessel_name?` | temporal, physical | 1 |
| `check_historical_trade` | `entity_id`, `commodity`, `lookback_months?` | behavioural | 2 |
| `check_counterparty_network` | `entity_id`, `depth?` | network | 2 |
| `check_contract_or_supporting_evidence` | `claim` ∈ `bulk_discount`, `grade_difference`, `distressed_sale`, `long_term_offtake`, `inspection` | economic, documentary | 1 |

Exhaustive cost is **10**; default budget is **6**. Read args from `spec.args_schema` at run time rather than hardcoding — Part 1 may add the two optional tools.

`check_contract_or_supporting_evidence` is the tool through which benign hypotheses get tested, and your policy gate blocks escalation unless a benign hypothesis was tested, so the planner must be biased towards calling it once an economic anomaly appears.

### 5.3 What you produce

**`Triage`** — `trade_narrative`, `initial_concerns: list[str]`, `unknowns: list[str]`, `dimensions_to_probe: list[Dimension]`

**`Hypothesis`** — `hypothesis_id` (`H1`…), `kind: HypothesisKind` (`benign`|`suspicious`), `statement`, `explains: list[Dimension]`, `prior: float`, `posterior: float`, `status: HypothesisStatus` (`open`|`supported`|`weakened`|`refuted`|`untestable`), `discriminating_evidence_needed: list[str]`, `supporting_evidence_ids`, `contradicting_evidence_ids`, `rationale?`

**`EvidenceItem`** — `evidence_id` (`E1`…), `dimension`, `stance: Stance` (`supports_suspicion`|`refutes_suspicion`|`neutral`), `statement`, `weight: float` 0–1, `severity`, `hypotheses_affected: list[str]`, `observation_ids: list[str]`, `tool_call_id?`, `sources: list[SourceRef]`, `interpretation?`

**`PlanStep`** — `step`, `reasoning`, `chosen_tool: str|None`, `chosen_args`, `targets_hypotheses`, `expected_information_gain: float`, `considered: list[{tool, expected_information_gain, why_not}]`, `stop_reason?` (`sufficient_evidence`|`budget_exhausted`|`no_informative_tool_left`)

**`BudgetState`** — `limit`, `spent`, `remaining`, `calls_made`, `tools_skipped: list[{tool, reason}]`, `exhaustive_cost?`

**`Corroboration`** — `corroborated_dimensions`, `independent_signal_count`, `refuting_dimensions`, `strongest_benign_hypothesis?`, `strongest_benign_posterior`, `narrative`

**`Decision`** — `verdict: Verdict` (`release`|`hold`|`escalate`), `confidence`, `headline`, `rationale`, `corroboration`, `typology?`, `caveats`, `decisive_evidence_ids`

**`EvidenceRequest`** — `item`, `why`, `resolves_hypotheses`, `priority` 1–3

**`GraphNode`** — `id`, `kind` (`document|field|reference|tool|finding|dimension|hypothesis|decision|entity|vessel`), `label`, `dimension?`, `stance?`, `severity?`, `meta`
**`GraphEdge`** — `source`, `target`, `relation` (`states|compared_with|produced|supports|refutes|corroborates|concludes|linked_to`), `label?`
**`EvidenceGraph`** — `nodes`, `edges`

**`RunMeta`** — `run_id`, `case_id`, `started_at`, `finished_at?`, `model`, `llm_calls`, `prompt_tokens`, `completion_tokens`, `wall_ms`, `replayed`, `degraded`

**`InvestigationResult`** — `meta`, `record`, `triage`, `hypotheses`, `plan_steps`, `tool_calls`, `evidence_for`, `evidence_against`, `evidence_neutral`, `budget`, `graph`, `decision`, `evidence_requests`, `report_markdown`, `events`

### 5.4 Enums

`Dimension`: `economic`, `physical`, `temporal`, `documentary`, `behavioural`, `network`
`Severity`: `none`, `low`, `medium`, `high`
`Stance`: `supports_suspicion`, `refutes_suspicion`, `neutral`
`HypothesisKind`: `benign`, `suspicious`
`HypothesisStatus`: `open`, `supported`, `weakened`, `refuted`, `untestable`
`Verdict`: `release`, `hold`, `escalate`
`SourceKind`: `document`, `reference_db`, `derived`, `model`

### 5.5 The event stream you emit

**`InvestigationEvent`** — `seq`, `ts`, `run_id`, `type: EventType`, `narration: str`, `payload: dict`

Use `SeqEmitter` from `interpretex_contracts.helpers` so `seq` is gapless. **`narration` is mandatory on every event** — Part 3's timeline must be renderable from `narration` alone, so the UI degrades gracefully if a payload shape surprises it. Write narration in the voice of an investigator's log: *"Price is 38.2% below the August benchmark — testing whether a bulk-discount agreement explains it."*

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

Ordering guarantees you must honour: `seq` starts at 0 and increments by exactly 1; `run_started` is `seq` 0; the stream terminates with `report_ready` or `run_failed`; every `tool_call_completed` follows its matching `tool_call_started`; `decision` precedes `report_ready`. Serialise nested models with `model_dump(mode="json")` before putting them in `payload`.

If a step takes more than ten seconds, emit a `heartbeat` so Part 3's `EventSource` does not look frozen.

### 5.6 Your public surface — exactly this, nothing more

```python
def investigate_stream(case: AgentCaseView, tools: ToolRegistry, *,
                       llm: LLMClient | None = None,
                       budget: int = 6,
                       seed: int | None = None) -> Iterator[InvestigationEvent]: ...

def investigate(case: AgentCaseView, tools: ToolRegistry, *,
                llm: LLMClient | None = None,
                budget: int = 6,
                seed: int | None = None,
                emit: EmitFn | None = None) -> InvestigationResult: ...
```

The final yielded event is `report_ready`, and `payload["result"]` is the full `InvestigationResult` as `model_dump(mode="json")`. `investigate()` is a thin blocking wrapper that drains the generator. `llm=None` means run the deterministic fallback path (section 13) — that path must produce a valid result, because it is your safety net and Part 3's offline mode.

---

## 6 · THE FOUR STRUCTURED LLM CALLS

For each, keep the schema flat, the temperature at 0.1, and the instruction explicit that only a JSON object may be returned. Pass a distinct `tag`.

### 6.1 Triage — `agent_prompts/triage.md`

Input: the `TradeRecord`, a compact table of every document with its type and key fields, the `applicant_note`, and the list of available tool names with their dimensions. **Do not paste full `raw_text` for every document** — you will burn the context window; paste `fields` plus at most 400 characters of `raw_text` per document.

Ask for: a two-to-four-sentence plain-English narrative of what this trade claims to be; the concerns visible on the face of the documents; the things that genuinely cannot be judged from paper alone (this list is what motivates tool use, so insist on it); and the dimensions worth probing.

Instruct explicitly: *"Do not conclude anything. You are describing what would make a professional investigator want to look further, and what paper alone cannot settle."*

### 6.2 Hypothesise — `agent_prompts/hypothesise.md`

Input: the triage output and the tool specs including each tool's `discriminates` list.

Ask for a list of hypotheses, each with `kind`, `statement`, `explains`, `prior`, and `discriminating_evidence_needed`.

Hard requirements, enforced in Python after the call rather than trusted to the model: **every concern must be covered by at least one `benign` and at least one `suspicious` hypothesis.** If the model returns only suspicious ones, inject a benign template hypothesis for each uncovered concern from a fixed catalogue: for an economic concern, "the price reflects an agreed volume discount or a long-term contract" and "the goods are a lower grade than the benchmark assumes"; for physical, "the vessel or weight was recorded incorrectly"; for temporal, "a date was mis-keyed" and "the voyage involved a transhipment not shown on the paperwork"; for documentary, "clerical error in one document"; for behavioural, "a legitimate change in the customer's trading pattern"; for network, "an ordinary commercial group structure". Also always include the catch-all benign hypothesis "documentation or data-entry error" and the catch-all suspicious hypothesis "trade-value manipulation".

Normalise priors to sum to roughly 1 per concern. Assign ids `H1`, `H2`, … in the order returned and never renumber them afterwards — Part 3 and the report reference them by id.

### 6.3 Plan — `agent_prompts/plan.md`

Input: the triage, the live hypotheses with current posteriors and statuses, the evidence gathered so far as one line each, the tools already called with their args, the remaining budget, and the affordable tools with `description`, `dimensions`, `cost_units` and `discriminates`.

Ask for: `reasoning` (short — the current state of belief and the single open question), `chosen_tool` or `null` to stop, `chosen_args`, `targets_hypotheses`, `expected_information_gain` in 0–1, and **`considered`: every other affordable tool with its expected information gain and a one-line `why_not`.**

That `considered` list is what makes the demo convincing, because it shows the agent had options and reasoned about them. Insist on at least two entries whenever two or more tools are affordable. If the model omits it, fill it from your own deterministic scoring (section 7) rather than shipping an empty list.

Then validate the choice in Python: the tool must exist, must be affordable, and must not repeat an earlier call with identical args. On violation, override with your deterministic scorer's top pick and note the override in `plan_step.reasoning`.

### 6.4 Interpret and update — `agent_prompts/interpret.md`

One call per completed tool call, handling both interpretation and hypothesis updating so you spend one call rather than two.

Input: the hypotheses with current posteriors, the `ToolResult` (summary, every observation with dimension, statement, severity, metrics, expected range, and the `ok`/`error` state), and the evidence already recorded.

Ask for: a list of evidence items, each with `dimension`, `stance`, `weight`, `statement`, `interpretation` (one line on why this stance given the alternatives), `hypotheses_affected` and `observation_ids`; plus a list of hypothesis updates, each with `hypothesis_id`, new `posterior`, new `status` and a `rationale`.

The instruction that matters most: *"A large deviation is not automatically evidence of wrongdoing. If this observation is consistent with a benign hypothesis, its stance is `refutes_suspicion` even when the underlying deviation is large. State which alternative explanation you weighed."* This single instruction is what makes Case 2 work.

Copy `sources` onto each `EvidenceItem` from the observations it derives from — do not ask the model to reproduce provenance, because it will hallucinate a `ref`. **Provenance is assembled in Python from the tool output, always.**

### 6.5 Prose calls

`corroborate.md` produces the `Corroboration.narrative` only, after you have computed the dimensional facts deterministically. `evidence_request.md` produces the `EvidenceRequest` list. `report.md` produces the executive summary and the key-findings prose for the dossier; everything else in the report is templated from the result object. Temperature up to 0.3 for these; keep the rest at 0.1.

---

## 7 · THE PLANNER, AND INFORMATION GAIN

The planner is what makes this an agent rather than a pipeline. Three properties are mandatory: the sequence differs by case; the rejected candidates are recorded with reasons; and the loop stops early when there is nothing informative left to do.

Implement a **deterministic scorer** alongside the LLM's judgement. It serves three purposes: it fills `considered` when the model is lazy, it overrides an invalid model choice, and it is the whole planner in the fallback path. Score each affordable tool as:

```
score(tool) = ( dimension_novelty        # 1.0 if no evidence yet in any of the tool's
              +                          #   dimensions, 0.35 if some, 0.1 if well covered
                hypothesis_relevance     # 0..1 — how many live, non-refuted hypotheses
              +                          #   this tool's `discriminates` list speaks to,
                benign_test_bonus        #   weighted by their posteriors
              +                          # +0.5 if it can test a live benign hypothesis
                triage_priority          #   and no benign hypothesis has been tested yet
              ) / cost_units             # +0.2 if its dimension is in triage.dimensions_to_probe
```

Zero the score for any tool already called with identical args. That `benign_test_bonus` is not cosmetic: it is what makes the agent reliably spend a call on `check_contract_or_supporting_evidence` once an economic anomaly appears, which is what unblocks escalation later and what produces the correct Case 2 behaviour.

**Stop conditions**, all deterministic, all producing a final `PlanStep` with `chosen_tool=None` and a `stop_reason`:

- `sufficient_evidence` — suspicion-supporting evidence at `severity >= medium` in two or more distinct dimensions **and** at least one benign hypothesis has been tested; or no suspicion-supporting evidence above `low` after probing every dimension the triage flagged.
- `budget_exhausted` — no affordable tool remains.
- `no_informative_tool_left` — every remaining tool scores below a floor (0.15 is a reasonable start).

Also enforce a hard `AGENT_MAX_STEPS` cap (default 10) independent of budget, so a pathological loop terminates.

**On Case 1 the agent should stop after two or three calls.** That short trace is a feature, not a bug — it is the visible proof that the agent is not walking a checklist, so do not add a minimum-calls rule.

When `FEATURE_BUDGET` is off, set `limit` to a number large enough not to bind and skip the skipped-tool accounting; everything else stays identical.

---

## 8 · CORROBORATION

Compute the facts in Python, then ask the LLM only for the narrative sentence.

Deterministically: the set of distinct dimensions holding `supports_suspicion` evidence at `severity >= medium`; the count of such items; the set of dimensions holding `refutes_suspicion` evidence; the highest-posterior benign hypothesis and its posterior.

Then apply an **independence penalty**, which is the part a sharp judge will probe. Two signals are not independent if one mechanically implies the other. If a quantity mismatch between documents is the same underlying discrepancy that causes the capacity excess, they are one finding seen twice, not two dimensions corroborating. Maintain a small explicit table of known-dependent pairs — `(documentary quantity_mismatch, physical capacity_exceeded)` when the tonnage figures are the same number, and `(temporal impossible_transit, physical vessel_substitution)` when they trace to the same date field — and when a pair is dependent, count it once and say so in the narrative. Detect it by comparing the `SourceRef.ref` sets behind the two evidence items: substantial overlap means shared cause.

The narrative must answer, in two or three sentences, whether these signals are genuinely independent of one another or one cause observed several times. In Case 3, the correct narrative notes that the price deviation, the capacity excess, the transit impossibility and the description drift arise from four different source fields checked against three different reference sources, which is what makes them mutually reinforcing.

---

## 9 · THE DECISION POLICY GATE — THE MOST IMPORTANT CODE YOU WRITE

`policy.py`. **A pure function of the ledger. No LLM call, no I/O, no randomness, fully unit tested.** The LLM may suggest a verdict elsewhere; this function decides, and if they disagree the policy wins and the disagreement is recorded in `decision.rationale`.

```python
def decide(evidence: list[EvidenceItem],
           hypotheses: list[Hypothesis],
           corroboration: Corroboration,
           tool_calls: list[ToolResult],
           plan_steps: list[PlanStep]) -> Decision
```

**ESCALATE** requires all three of:
- suspicion-supporting evidence at `severity >= medium` in **two or more distinct dimensions**, after the independence penalty;
- **no** benign hypothesis with `posterior >= 0.6`;
- **at least one tool call whose `targets_hypotheses` included a benign hypothesis** — the agent must have actually tried to find the innocent explanation.

**RELEASE** requires either no suspicion-supporting evidence above `low`, or every `medium`-or-above suspicion-supporting item matched by a `refutes_suspicion` item in the same dimension with `weight >= 0.6`.

**Otherwise HOLD**, and `evidence_requests` must be non-empty.

Two hard rules, and they are the credibility of the entire project:

1. **Single-dimension anomalies can never escalate.** One anomalous dimension caps the verdict at HOLD however extreme the deviation. This is what produces Case 2's behaviour and it is the direct answer to "isn't this just a threshold with extra steps".
2. **No escalation without a tested benign hypothesis.** If no tool call ever targeted a benign hypothesis, cap at HOLD regardless of the evidence.

Confidence is computed, not invented: base it on the number of corroborating dimensions, the mean weight of the decisive evidence, the margin against the strongest benign posterior, and the fraction of triage-flagged dimensions actually probed. Cap it at 0.9 — nothing here justifies more. Reduce it when `meta.degraded` is true.

`typology` is populated only on ESCALATE, and only with careful wording: **"Indicators consistent with potential under-invoicing / trade-value manipulation"**, or the analogous phrasing for over-invoicing, phantom shipment, or misdescription of goods. **Never** "money laundering confirmed", "fraud detected", or "proven". This is a real compliance-language constraint and a knowledgeable judge will notice if you get it wrong.

`caveats` always includes the three strings from `STANDARD_CAVEATS` in the contracts package, on every verdict without exception, including RELEASE.

`headline` is one line an investigator can read in two seconds. `rationale` is three to six sentences citing evidence ids explicitly (`E3`, `E7`), and on HOLD it must state what would change the verdict in either direction.

---

## 10 · EVIDENCE REQUESTS

Mandatory and non-empty on HOLD; useful on ESCALATE (what the investigation packet still needs); may be empty on RELEASE.

Each `EvidenceRequest` names a concrete document or record, states what uncertainty it closes, lists the `hypothesis_id`s it would resolve, and carries a priority. Derive them from the hypotheses still `open` or `weakened` — walk each one's `discriminating_evidence_needed` and turn it into a document ask. Generic requests are worthless; "the original purchase contract including the pricing schedule, to test whether the −18% deviation reflects agreed tiered pricing (resolves H2)" is the standard.

Draw from: original purchase or offtake contract with pricing schedule; independent inspection or assay certificate for grade and quantity; warehouse or terminal loading records; vessel loading confirmation or stowage plan; corrected insurance certificate with an explanation of the issue date; ultimate beneficial ownership declaration for the intermediary; prior invoices for the same commodity from the same counterparty; transhipment documentation if the route involved one.

---

## 11 · THE EVIDENCE GRAPH

Build it incrementally so `graph_updated` events stream as findings appear — Part 3 animates nodes fading in and that single effect carries the demo.

Node kinds and the shape of the DAG:

```
document ─states→ field ─compared_with→ reference ─produced→ finding
                                                        │
                                     finding ─supports/refutes→ hypothesis
                                     finding ─corroborates→ dimension
                                    dimension ─concludes→ decision
```

Ids must be stable and derivable: `doc:INV-2026-0912`, `field:INV-2026-0912.unit_price`, `ref:benchmarks/copper_cathode/2026-08`, `tool:check_price_benchmark`, `find:E3`, `dim:economic`, `hyp:H2`, `dec:final`. Derive `field` and `reference` nodes from the `SourceRef.ref` strings on each observation, which is why Part 1 was required to populate them properly — if a `SourceRef` is missing, create a `kind="derived"` node labelled with the tool name rather than dropping the edge, so provenance is never silently broken.

Carry `dimension`, `stance` and `severity` onto finding nodes so Part 3 can colour them without re-deriving anything. The acceptance test: **every finding node is reachable from at least one document or reference node, and the decision node is reachable from every corroborating dimension.** Assert it.

---

## 12 · THE DOSSIER

`report.py` produces `report_markdown`. Structure is templated from the result object; only the executive summary and the key-findings prose come from the LLM. It must read like something a bank investigator wrote.

```
# TRADE INVESTIGATION REPORT
Case <id> · Run <id> · <timestamp> · Model <model>

## DECISION: <RELEASE | HOLD — REQUEST DOCUMENTATION | ESCALATE / BLOCK>
<headline>            Confidence <n>%

## EXECUTIVE SUMMARY
<3-5 sentences: what the trade claims, what was checked, what was found, what
 was ruled out, and what the bank should do next.>

## TRADE OVERVIEW
Buyer · Seller · Broker · Commodity and grade · HS code · Quantity ·
Unit price · Total value · Incoterm · Vessel · Route · Ship and arrival dates ·
LC reference

## KEY FINDINGS
<one line per decisive evidence item, with its id and dimension>

## EVIDENCE SUPPORTING CONCERN
| Id | Dimension | Finding | Severity | Weight | Source |

## EVIDENCE AGAINST CONCERN
| Id | Dimension | Finding | Weight | Source |
<If this table is empty, say so explicitly and say what was looked for and
 not found. An empty section without explanation reads as confirmation bias.>

## HYPOTHESES CONSIDERED
| Id | Kind | Statement | Prior → Posterior | Status | Why it moved |

## INVESTIGATIONS PERFORMED
| # | Tool | Why chosen | Cost | What it returned |
<Include the tools NOT chosen and why — this is where the agentic behaviour
 becomes legible to a reader who did not watch the live run.>

## CORROBORATION ANALYSIS
<narrative: are these signals independent, or one cause seen repeatedly?>

## TIMELINE OF AGENT ACTIONS
<one line per event with elapsed time>

## RISK TYPOLOGY
<careful wording, or "None identified">

## RECOMMENDED ACTION
## ADDITIONAL DOCUMENTATION REQUESTED
| Priority | Item | Why | Resolves |

## LIMITATIONS AND CAVEATS
<the three standard caveats, verbatim, always>

## PROVENANCE
<every finding with its full source chain>
```

---

## 13 · THE DETERMINISTIC FALLBACK

`fallback.py`. Runs when `llm=None`, when `LLMError`/`LLMJsonError` escapes the repair loop, or when any structured call returns something unusable. It must produce a **valid `InvestigationResult`** with `meta.degraded=true` and a caveat saying reasoning was produced without model inference.

It uses the deterministic scorer as its planner, a fixed hypothesis catalogue keyed by the dimensions present, a rule-based stance assignment (`supports_suspicion` when `severity >= medium` and no supporting benign finding exists in the same dimension, `refutes_suspicion` when a tool explicitly found supporting evidence for a benign claim, else `neutral`), the same policy gate, and a template-only report.

**Degrade per stage, not globally.** If triage fails, fall back for triage and continue with the model for the rest. Wrap every LLM call site in a helper that returns a typed fallback on exception and records the degradation in `meta` and as a caveat. Build this early — it is your insurance policy for hours 10 through 24, and it is also Part 3's offline mode.

---

## 14 · THE EVALUATION HARNESS

`eval.py`, a CLI: `python -m agent.eval --cases all --runs 3`. It may read `CaseLabel` ground truth; **the agent must never import it.**

Report: verdict accuracy against `expected_verdict` per case; the false-escalation rate on `clean` and `suspicious_but_legitimate` cases, which is the metric that matters most for the pitch; mean tool calls and mean cost per case versus the exhaustive cost of 10; the proportion of runs in which a benign hypothesis was tested before escalation, which should be 100%; verdict stability across repeated runs of the same case; and the count of degraded runs.

Two things this gives you. First, a regression suite: run it before every push after T+10 and never let Case 2's escalation rate rise above zero. Second, a slide — "the agent reached the same verdict as an exhaustive check while spending 6 units instead of 10, and never escalated a legitimate case across N runs" is a far better claim than any architecture diagram.

---

## 15 · GIT WORKFLOW

```bash
git clone https://github.com/alonek007/interpretex.git
cd interpretex
git checkout part2-agent          # branch off main, created at kickoff
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e packages/contracts   # available on main from T+1.5h
pip install pytest python-dotenv
cp .env.example .env              # paste the shared OPENROUTER_API_KEY and LLM_MODEL
```

Commit every 30 minutes and push. Before each integration window (T+5, T+10, T+14): `git fetch origin && git rebase origin/main`, then PR into `main`, merge `--no-ff`. **Never merge `part1-world` or `part3-app` into your branch** — integrate only through `main`.

Commit prefixes: `feat(agent)`, `feat(policy)`, `feat(planner)`, `fix(agent)`, `test(agent)`, `prompt(...)` for template edits.

**Until `packages/contracts` lands on `main` at T+1.5h, do not idle and do not write your own copy of it.** Spend that time on `agent_prompts/*.md` and on the policy-gate specification and its unit tests, both of which are pure logic and depend on nothing.

---

## 16 · ORDER OF WORK WITH HOUR GATES

| Hours | Deliverable |
|---|---|
| **0 – 1.5** | All seven prompt templates in `agent_prompts/`. `policy.py` written against the spec in section 9 plus its full unit-test suite, using hand-built `EvidenceItem` lists. No dependency on anything else. |
| **1.5 – 2** | `pip install -e packages/contracts`. Verify `CONTRACT_VERSION == "1.0.0"`. Write a 20-line fake `ToolRegistry` in `tests/agent/fakes.py` returning two or three canned `ToolResult`s so you are not blocked on fixtures. |
| **2 – 3.5** | `loop.py` skeleton with `SeqEmitter`, plus `triage.py` and `hypotheses.py` working against the real LLM. Verify the benign-hypothesis injection rule fires when the model returns only suspicious ones. |
| **3.5 – 5** | `planner.py`: deterministic scorer, LLM plan call, choice validation, `considered` population, all three stop conditions. Switch to `FixtureToolRegistry` from the contracts package once Part 1's fixtures land at T+3. |
| **T+5** | **Integration window 1.** Push. Confirm your event stream renders in Part 3's timeline. |
| **5 – 7** | `ledger.py` and `interpret.md` working: observations become evidence with stance, weight and provenance. Verify on the Case 2 fixture that the historical and contract findings come back as `refutes_suspicion`. |
| **7 – 8.5** | `corroboration.py` including the independence penalty; wire `policy.py` in; `requests.py`. |
| **8.5 – 10** | `graph.py` streaming `graph_updated`; `report.py`; `fallback.py`; `investigate()` wrapper. End-to-end on all three fixture cases. |
| **T+10** | **Integration window 2 — MVP GATE.** Your agent plus Part 1's real world must run Case 3 live in Part 3's browser and escalate. If this fails, all advanced features are cancelled. |
| **10 – 12** | `FEATURE_BUDGET`: information-gain scoring exposed in `PlanStep`, `tools_skipped` with reasons, `exhaustive_cost`, and the baseline comparison Part 3 renders. |
| **12 – 14** | `eval.py`. Run all three cases three times. Fix whatever the numbers expose — most likely Case 2 escalating or Case 1 over-investigating. |
| **T+14** | **Integration window 3.** |
| **14 – 18** | Tune prompt wording until all three verdicts are stable across three consecutive runs. Record cassettes for every demo case. Tighten report prose. Handle the adversarial case Part 1 generates. |
| **T+18** | **Freeze.** `LLM_CACHE_MODE=read`. Three clean dry runs. No prompt edits after this — a prompt edit invalidates every cassette. |

---

## 17 · DEFINITION OF DONE

- [ ] `investigate(case, tools)` returns a valid `InvestigationResult` for all three fixture cases.
- [ ] `investigate_stream` is a generator; the first event is `run_started` at `seq` 0 and the last is `report_ready`; `seq` is gapless.
- [ ] `packages/agent/` contains no import of `world` or `app`, asserted by a grep test.
- [ ] `AgentCaseView` is the only case type in the agent's signatures; nothing reads `label`.
- [ ] `case_clean_001` → **RELEASE** in ≤ 3 tool calls.
- [ ] `case_explainable_002` → **HOLD or RELEASE, never ESCALATE**, across three consecutive runs.
- [ ] `case_suspicious_003` → **ESCALATE** with four or more corroborated dimensions, across three consecutive runs.
- [ ] Every escalation in the suite was preceded by a tool call that targeted a benign hypothesis.
- [ ] `policy.py` is a pure function with no LLM or I/O, and has unit tests covering every branch including both hard rules.
- [ ] Single-dimension escalation is impossible, proven by a unit test with one `high` economic item and nothing else.
- [ ] Escalation without a tested benign hypothesis is impossible, proven by a unit test.
- [ ] Every `PlanStep` where two or more tools were affordable has a non-empty `considered` list.
- [ ] Every `EvidenceItem` has at least one `SourceRef`, and every finding node in the graph is reachable from a document or reference node.
- [ ] `evidence_requests` is non-empty on every HOLD.
- [ ] `decision.caveats` contains all three standard caveats on every verdict, including RELEASE.
- [ ] `typology` never contains "confirmed", "proven", "fraud" or "money laundering" as a conclusion. Grep for it.
- [ ] `investigate(case, tools, llm=None)` produces a valid result with `meta.degraded=true`.
- [ ] A tool returning `ok=False` mid-run does not crash the investigation; there is a test.
- [ ] `python -m agent.eval --cases all --runs 3` runs and prints the metrics in section 14.
- [ ] `report_markdown` contains every section in section 12, including a non-empty EVIDENCE AGAINST section or an explicit statement of what was looked for and not found.
- [ ] `pytest tests/agent` is green.
- [ ] `HANDOFF_PART2.md` written (section 20).

---

## 18 · TESTS YOU MUST WRITE

`tests/agent/test_policy_gate.py` — the priority test file in the whole repo. Cover: two dimensions plus a tested benign hypothesis → escalate; one dimension at `high` → hold, never escalate; two dimensions but a benign posterior of 0.7 → hold; two dimensions but no benign hypothesis tested → hold; no evidence above `low` → release; a `medium` item fully refuted in the same dimension → release; hold always yields non-empty requests.
`tests/agent/test_no_world_import.py` — grep the agent package for `import world` and `from world`.
`tests/agent/test_stream_contract.py` — `seq` gapless from 0, terminates with `report_ready`, every `tool_call_completed` has a preceding `tool_call_started`, `decision` precedes `report_ready`.
`tests/agent/test_fallback.py` — with `llm=None` and with a `ScriptedLLM` returning garbage, assert a valid result with `degraded=true`.
`tests/agent/test_tool_failure_recovery.py` — a registry whose second call returns `ok=False`; assert the run completes and a re-plan occurred.
`tests/agent/test_demo_cases.py` — the three verdict assertions, run three times each. **This is your regression gate; run it before every push after T+10.**
`tests/agent/test_graph_provenance.py` — every finding node reachable from a source node.
`tests/agent/test_hypothesis_balance.py` — with a `ScriptedLLM` returning only suspicious hypotheses, assert benign ones were injected.

---

## 19 · FAILURE MODES TO DESIGN AGAINST

**Case 2 escalating.** The most likely way this project fails. It happens when the interpreter marks the historical-price finding as `supports_suspicion` because the price is low, rather than `refutes_suspicion` because the price matches this customer's own history. Fix it in the interpret prompt with the explicit instruction from section 6.4, and let the policy gate's single-dimension rule catch it regardless. Do not rely on the prompt alone.

**The agent running every tool.** If the trace on Case 1 is eight calls, the "dynamic investigation" claim is dead. Enforce the stop conditions deterministically and check the Case 1 trace length in the eval harness.

**An empty `considered` list.** Then there is no visible evidence of deliberation, and the demo's central claim is unsupported on screen. Fill it from your own scorer whenever the model omits it.

**Provenance invented by the model.** Never let the LLM produce a `SourceRef.ref`. Assemble provenance in Python from the tool output.

**Context-window blowout.** Do not paste full document `raw_text` into every prompt. Summarise prior evidence to one line each. By step five your prompt should be smaller than it was at step two, not larger.

**Prompt edits after cassettes are recorded.** Any change to a prompt template changes the hash and invalidates every cassette. Freeze prompts at T+18 and re-record if you must change one.

**Hypothesis ids drifting.** Assign `H1`, `H2`, … once and never renumber. The report, the graph and Part 3's hypothesis board all reference them by id.

**Verdict from the model rather than the gate.** Easy to do accidentally if you ask the model for a suggested verdict in the interpret call. If you do ask, use it only as a diagnostic recorded in the rationale, and make it structurally impossible for it to reach `Decision.verdict`.

**Overconfidence.** Confidence above 0.9 is not defensible with synthetic reference data. Cap it and say why.

---

## 20 · HANDOFF ARTEFACT

Before T+18, write `HANDOFF_PART2.md` on your branch containing: the exact signatures of `investigate` and `investigate_stream`; the event types you emit and, for each, which payload keys are populated; the full decision-policy rule set as a table, since Part 3 displays it and you will be asked about it on stage; how to run the eval harness and what its current numbers are; which prompt templates exist and what each does; where the cassettes are; the tuning that is fragile and must not be touched; and anything you deliberately did not build.

---

## 21 · IF YOU FINISH EARLY, OR RUN LATE

**Early**, in this order: add a genuine Bayesian posterior update with explicit likelihood ratios per evidence item, replacing the model's free-hand posterior — this is a strong interview talking point; add a self-critique pass in which the agent is shown its own draft decision and asked what would most weaken it, then records that as a caveat; add a second-opinion mode that re-runs the interpret step at a higher temperature and flags disagreements; add per-dimension confidence intervals.

**Late**, cut in this order: the self-critique pass; the independence penalty (fall back to counting distinct dimensions naively, and say so); the eval harness down to a single assertion per case; the LLM-authored corroboration narrative (template it). **Never cut:** the policy gate, the benign-hypothesis injection, the `considered` list, provenance on evidence items, or the fallback path.

---

## 22 · CLAIMS DISCIPLINE

Every string your agent can emit is a claim the team has to defend. Never let the agent state that money laundering occurred, that fraud is proven, or that a determination has been made. The vocabulary is "indicators consistent with", "the evidence does not support", "unresolved", "requires further documentation". The verdict is a recommendation to a human reviewer, not a finding. On RELEASE, say "no significant corroborated anomaly was identified in the dimensions examined" rather than "this trade is legitimate" — you checked six dimensions in a synthetic world, and that is all you can honestly claim.
