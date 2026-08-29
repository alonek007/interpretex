# Part 2 (Agent / Investigator Core) — Progress README

> Living status document for the Interpretex AI Trade Investigation Agent, Part 2.
> Updated as work proceeds. Last updated: this session.

## Status: ✅ Part 2 complete and verified

All three seeded demo cases resolve to the correct verdict with the deterministic
fallback path, the policy gate, stream, graph, and eval harness all green.

| Demo case | Expected | Actual | Tool calls | Result |
|---|---|---|---|---|
| `case_clean_001` | release | **release** | 3 | ✅ |
| `case_explainable_002` | hold / release | **release** | 3 | ✅ (release acceptable) |
| `case_suspicious_003` | escalate | **escalate** | 3 | ✅ 2+ corroborated dims |

Eval: **100% accuracy, 0% false-escalation, 100% stability, ~70% efficiency vs
exhaustive** (3 calls vs 10). `pytest tests/agent` → **34 passed**.

## What was built (Part 2 scope)

1. **Contract-driven architecture** — the agent imports *only*
   `interpretex_contracts` (the frozen §8 interface). The `ToolRegistry` and
   `LLMClient` arrive by dependency injection; the agent never touches a Part 1
   world. (`test_no_world_import.py` enforces this.)
2. **Prompt templates** — `agent_prompts/`: `triage, hypothesise, plan, interpret,
   corroborate, evidence_request, report` (§7/§8).
3. **Hand-rolled investigation loop** — `agent/loop.py`: a generator
   (`investigate_stream`) with a `SeqEmitter`, per-stage degradation, budget
   accounting, and deterministic stop conditions enforced in Python (never the
   model).
4. **Planner** — `agent/planner.py`: deterministic scorer + benign-test forcing +
   dimension-priority ranking; fills `considered`, overrides invalid LLM choices,
   and is the whole planner on the fallback path.
5. **Evidence ledger & interpretation** — `ledger.py`, `fallback.py`: rule-based
   stance assignment (supports / refutes / neutral) and posterior moves; the agent
   degrades per stage instead of crashing.
6. **Deterministic policy gate** — `policy.py`: pure function; the LLM proposes,
   the gate disposes. Escalation requires ≥2 corroborated dims, no benign
   posterior ≥ 0.6, and a tested benign hypothesis.
7. **Corroboration & requests** — `corroboration.py`, `requests.py`: independence
   penalty, typology (compliance language only), and documentation requests on HOLD.
8. **Evidence graph** — `graph.py`: provenance tracking; `provenance_warnings`
   flags orphan evidence.
9. **Fallback path** — `fallback.py`: deterministic triage/hypotheses/interpret/
   plan so the no-LLM path is fully valid (`meta.degraded = True`).
10. **Eval harness** — `eval.py` (`python -m agent.eval`) with accuracy,
    false-escalation, efficiency, stability, and degraded metrics.
11. **Test suite** — `tests/agent/` (8 test files + `conftest.py` + `fakes.py`).
12. **Handoff doc** — `HANDOFF_PART2.md` (signatures, event contract, policy
    table, eval how-to, prompt list, fragile-tuning notes).

## Important note on Part 1 / Part 3 files

Part 2 depends on the shared contract package `packages/contracts/`
(`interpretex_contracts`, frozen §8). Because the upstream Part 1 repository was
empty at the time of writing, this folder currently holds a **minimal bootstrap
shim** — just enough of the interface (enums, trade/case records, investigation
events/result, the `ToolRegistry`/`LLMClient` protocols, a cassette-cached
OpenRouter adapter, and a `fixtures` helper) for Part 2 to run, test, and be
evaluated. It is **not** Part 1's application logic and contains **no** Part 3
(orchestrator/UI) code.

Action required when Part 1 lands: replace `packages/contracts/` with the
authoritative Part 1 package. No change is needed anywhere inside
`packages/agent/` — it imports only `interpretex_contracts`. A `README.md` inside
`packages/contracts/` flags this.

There were **no** stray Part 3 files in the workspace to remove.

## How to run

```bash
# from repo root, with the venv active
.venv/bin/python -m agent.eval --cases all --runs 3
.venv/bin/python -m pytest tests/agent -q
```

## Open items / next steps (post-handoff)

* Wire a real LLM (`OpenRouterLLM` exists in the contracts package; set
  `OPENROUTER_API_KEY` + `LLM_MODEL`, or `LLM_CACHE_MODE=read` to replay cassettes).
* Replace `packages/contracts/` with Part 1's real registry/fixtures.
* Expand demo cases (network/behavioural anomalies, multi-invoice, transhipment)
  and tune the planner's dimension-priority constants if the case mix changes.
