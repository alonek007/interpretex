# Part 2 — Investigator Core: Handoff Document (§20)

This file is the contract between Part 2 (this package) and the rest of the
system. If you change anything below, you change the interface.

## 1. Public surface (only these two functions)

```python
from agent import investigate, investigate_stream

investigate_stream(case, tools, *, llm=None, budget=6, seed=None)
    -> Iterator[InvestigationEvent]          # generator; last event is report_ready

investigate(case, tools, *, llm=None, budget=6, seed=None, emit=None)
    -> InvestigationResult                   # blocking wrapper over the stream
```

* `case: AgentCaseView` — the redacted view of the trade (NO ground-truth label;
  the agent never sees labels).
* `tools: ToolRegistry` — dependency-injected against `interpretex_contracts`.
  The agent NEVER imports a Part 1 world/registry; it only calls `tools.specs()`
  and `tools.call(name, args)`.
* `llm: LLMClient | None` — if `None`, the agent runs the **fully deterministic
  fallback** (`meta.degraded = True`); every stage is replaced by a rule-based
  equivalent. This is the path used by the eval and the tests.
* `budget` — cost units; `FEATURE_BUDGET=1` enforces it, `FEATURE_BUDGET=0`
  disables it.

## 2. Event stream contract (§5.4)

Events are emitted in strict order. Verified by `test_stream_contract.py`:

| property | rule |
|---|---|
| sequence | gapless `seq` starting at `0` |
| first | `run_started` |
| last | `report_ready` (its payload holds the full `InvestigationResult` and `report_markdown`) |
| pairing | every `tool_call_completed` is preceded by its `tool_call_started` |
| ordering | `decision` strictly precedes `report_ready` |

Event types used: `run_started, case_loaded, triage, hypotheses_updated,
plan_step, tool_call_started, tool_call_completed, evidence_added, graph_updated,
budget_updated, corroboration, decision, evidence_requested, report_ready`
(+ `heartbeat`, and `run_failed` only if even the fallback path throws).

## 3. Decision policy gate (the most important code — `agent/policy.py`)

Pure function `decide(evidence, hypotheses, corroboration, tool_calls,
plan_steps, *, llm_suggested_verdict=None, degraded=False) -> Decision`.
The LLM **proposes**; the gate **disposes**. If the model's verdict disagrees,
the policy wins and the disagreement is recorded in `rationale`.

| condition | verdict |
|---|---|
| no support ≥ medium, OR every medium+ support matched by a refuter (weight ≥ 0.6) in its own dimension | **RELEASE** |
| support ≥ medium in ≥ 2 independent dims **and** strongest benign posterior < 0.6 **and** a benign hypothesis was actually tested (contract tool called) | **ESCALATE** |
| otherwise | **HOLD** (+ `evidence_requests` non-empty) |

Hard rules: a single dimension can never escalate; no escalation without a
tested benign hypothesis. Typology is compliance-language only — never
"confirmed / proven / fraud / money laundering".

## 4. The planner (`agent/planner.py`)

A deterministic scorer runs **alongside** the LLM: it fills `considered` when
the model is lazy, overrides an invalid model choice, and is the whole planner
on the fallback path.

* Tools are ranked first by the **highest-priority unprobed flagged dimension**
  (economic > documentary > physical > temporal > behavioural > network), then by
  how much that dimension's competing hypotheses the tool discriminates, then by
  how many remaining dimensions it clears at once, then cost.
* **Benign-test forcing**: if a medium+ support signal appears in a dimension
  whose benign hypothesis the *contract* tool can test, and the contract has not
  yet been called, the planner **forces** `check_contract_or_supporting_evidence`
  next. This is what unblocks RELEASE on explainable cases and satisfies the
  "tested benign hypothesis" precondition for escalation.
* Stop conditions (enforced in Python before each plan step, never left to the
  model): sufficient evidence, budget exhausted, or no informative tool left.

## 5. Prompts (`agent_prompts/`, loaded by `agent/prompts.py`)

`triage.md, hypothesise.md, plan.md, interpret.md, corroborate.md,
evidence_request.md, report.md` — all `str.format` templates (no literal braces
outside the `{placeholders}`). They are used only in the LLM path; the fallback
path has rule-based equivalents.

## 6. Eval harness (`python -m agent.eval`)

```
python -m agent.eval --cases all --runs 3      # all three demo cases
python -m agent.eval --case case_suspicious_003 --runs 5
```

Metrics printed: accuracy (class-aware — clean→release, explainable→hold/release,
illicit→escalate), false-escalation rate on clean/explainable, mean tool
calls & cost vs the exhaustive baseline (10), efficiency, benign-tested rate,
stability (mode share of verdicts), and degraded-run count. Overall line is
`PASS` when accuracy holds and false-escalations = 0.

Demo cases live in `agent/demo_cases.py` as `case_clean_001`,
`case_explainable_002`, `case_suspicious_003`. Their ground-truth labels
(`TradeCase.label`) are read **only** by the eval/tests, never by the agent.

## 7. Tests (`tests/agent/`)

`test_policy_gate, test_no_world_import, test_stream_contract, test_fallback,
test_tool_failure_recovery, test_demo_cases, test_graph_provenance,
test_hypothesis_balance` (+ `conftest.py`, `fakes.py` with `ScriptedLLM` and
`FakeToolRegistry`). Run with `pytest tests/agent -q`.

`test_no_world_import.py` is an architectural guard: it fails if the `agent`
package imports anything outside `interpretex_contracts`, the stdlib, or itself.

## 8. Fragile / tuning notes (read before "improving" the planner)

* The planner's tool-ranking is **deliberately deterministic**, not learned. The
  dimension-priority order and the benign-test forcing are load-bearing; the
  demo verdicts depend on them. If you change relevance scoring, re-run the eval
  and the 8 test files.
* `packages/contracts/` is the **frozen §8 interface** (`interpretex_contracts`)
  that Part 2 is specified to import. It currently contains a minimal bootstrap
  shim so Part 2 runs and tests without Part 1's real registry. When Part 1
  lands, replace `packages/contracts/` with the authoritative package — Part 2
  imports only `interpretex_contracts`, so nothing else changes.
* LLM path: `complete_json` responses are validated against local JSON Schemas
  and re-prompted on failure. Cassettes are cached under `.llm_cache/` when
  `LLM_CACHE_MODE=write`/`read`; `LLM_CACHE_MODE=read` replays with zero network
  (useful for reproducible evals).
