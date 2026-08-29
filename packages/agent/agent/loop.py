"""The investigation loop: hand-rolled orchestrator (~200 lines, no framework).

State, event emission through SeqEmitter, step cap, budget accounting, and
per-stage degradation on failure. The stream is a generator: events are
yielded as they happen, not batched at the end.

Ordering guarantees honoured: seq gapless from 0; run_started is seq 0;
terminates with report_ready (or run_failed if even the fallback path fails);
every tool_call_completed follows its matching tool_call_started; decision
precedes report_ready.
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Iterator

from interpretex_contracts import (
    CONTRACT_VERSION,
    STANDARD_CAVEATS,
    AgentCaseView,
    Decision,
    Dimension,
    EvidenceRequest,
    EventType,
    InvestigationEvent,
    InvestigationResult,
    RunMeta,
    SeqEmitter,
    ToolResult,
    canonical_json,
    new_run_id,
    utcnow,
)

from . import corroboration as corr_mod
from . import fallback as fb
from . import hypotheses as hyp_mod
from . import ledger as ledger_mod
from . import planner as planner_mod
from . import policy as policy_mod
from . import report as report_mod
from . import requests as req_mod
from . import triage as triage_mod
from .graph import EvidenceGraphBuilder, provenance_warnings

HEARTBEAT_AFTER_S = 10.0
DEGRADED_CAVEAT = (
    "Part of the reasoning was produced by the deterministic fallback path without model inference."
)


def _env_flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no")


def _max_steps() -> int:
    try:
        return max(3, int(os.environ.get("AGENT_MAX_STEPS", "10")))
    except ValueError:
        return 10


class _RunState:
    def __init__(self, case: AgentCaseView, tools: Any, llm: Any, budget: int, seed: int | None) -> None:
        self.case = case
        self.tools = tools
        self.llm = llm
        self.seed = seed
        self.rng_seed = seed if seed is not None else 0
        self.budget_limit = budget if _env_flag("FEATURE_BUDGET") else 10**6
        self.budget_spent = 0
        self.calls_made = 0
        self.degraded = False
        self.degraded_stages: list[str] = []
        self.caveat = DEGRADED_CAVEAT
        self.hypotheses: list[Any] = []
        self.evidence: list[Any] = []
        self.evidence_next_id = 1
        self.plan_steps: list[Any] = []
        self.tool_calls: list[Any] = []
        self.called_keys: set[str] = set()
        self.probed_dims: set[str] = set()
        self.model = getattr(llm, "model", None) or "deterministic-fallback"
        self.started_at = utcnow()

    @property
    def remaining(self) -> int:
        return max(0, self.budget_limit - self.budget_spent)

    def note_degraded(self, stage: str) -> None:
        self.degraded = True
        if stage not in self.degraded_stages:
            self.degraded_stages.append(stage)


def run_investigation(
    case: AgentCaseView,
    tools: Any,
    llm: Any = None,
    budget: int = 6,
    seed: int | None = None,
) -> Iterator[InvestigationEvent]:
    try:
        yield from _run(case, tools, llm, budget, seed)
    except Exception as exc:  # last-resort: never crash on stage
        emitter = SeqEmitter(new_run_id())
        yield emitter.emit(
            EventType.run_failed,
            f"The investigation failed and could not be recovered: {exc}",
            {"error": str(exc), "stage": "unknown", "degraded": True},
        )


def _run(case: AgentCaseView, tools: Any, llm: Any, budget: int, seed: int | None) -> Iterator[InvestigationEvent]:
    specs = list(tools.specs())
    run_id = f"run-{case.case_id}-{seed}" if seed is not None else new_run_id()
    emitter = SeqEmitter(run_id)
    state = _RunState(case, tools, llm, budget, seed)
    graph = EvidenceGraphBuilder(case)
    events: list[InvestigationEvent] = []

    def emit(ev_type: EventType, narration: str, payload: dict[str, Any] | None = None,
             t0: float | None = None) -> Iterator[InvestigationEvent]:
        if t0 is not None and time.monotonic() - t0 > HEARTBEAT_AFTER_S:
            hb = emitter.emit(EventType.heartbeat, "Long-running step in progress…", {})
            events.append(hb)
            yield hb
        ev = emitter.emit(ev_type, narration, payload or {})
        events.append(ev)
        yield ev

    # ---------------------------------------------------------------- start
    flags = {
        "FEATURE_BUDGET": _env_flag("FEATURE_BUDGET"),
        "degraded_llm": llm is None,
    }
    t0 = time.monotonic()
    yield from emit(
        EventType.run_started,
        f"Investigation of case {case.case_id} starting with budget {state.budget_limit} units.",
        {
            "case_id": case.case_id,
            "budget": state.budget_limit,
            "model": state.model,
            "flags": flags,
            "contract_version": CONTRACT_VERSION,
        },
        t0,
    )
    yield from emit(
        EventType.case_loaded,
        f"Loaded {len(case.documents)} documents covering {case.record.commodity} "
        f"({case.record.quantity} {case.record.unit}).",
        {
            "record": case.record.model_dump(mode="json"),
            "document_ids": [d.doc_id for d in case.documents],
            "applicant_note": case.applicant_note,
        },
    )

    # ---------------------------------------------------------------- triage
    t0 = time.monotonic()
    try:
        if llm is None:
            raise RuntimeError("no llm configured")
        triage = triage_mod.run_triage(case, specs, llm, tag="triage")
        note = "Triage complete."
    except Exception as exc:
        state.note_degraded("triage")
        triage = fb.fallback_triage(case, specs)
        note = f"Triage fell back to the deterministic path ({type(exc).__name__})."
    if not triage.dimensions_to_probe:
        triage.dimensions_to_probe = [Dimension.economic]
    yield from emit(
        EventType.triage,
        f"{note} {triage.trade_narrative}",
        {"triage": triage.model_dump(mode="json")},
        t0,
    )

    # ------------------------------------------------------------ hypothesise
    t0 = time.monotonic()
    try:
        if llm is None:
            raise RuntimeError("no llm configured")
        raw_hyps = hyp_mod.run_hypothesise(triage, specs, llm, tag="hypothesise")
        hypotheses, injected = hyp_mod.ensure_balance(raw_hyps, triage)
        note = (
            f"{len(hypotheses)} rival hypotheses generated"
            + (f"; {len(injected)} benign/suspicious templates injected to keep balance" if injected else "")
            + "."
        )
    except Exception as exc:
        state.note_degraded("hypothesise")
        hypotheses, injected = fb.fallback_hypotheses(triage)
        note = f"Hypotheses fell back to the deterministic catalogue ({type(exc).__name__})."
    state.hypotheses = hypotheses
    for h in hypotheses:
        graph.add_hypothesis(h.hypothesis_id, h.statement)
    yield from emit(
        EventType.hypotheses_updated,
        f"{note} {len(hypotheses)} benign, {len([h for h in hypotheses if h.kind.value == 'suspicious'])} suspicious.",
        {
            "hypotheses": [h.model_dump(mode="json") for h in hypotheses],
            "changed_ids": [h.hypothesis_id for h in hypotheses],
        },
        t0,
    )

    # ------------------------------------------------------------- main loop
    max_steps = _max_steps()
    step_no = 0
    while step_no < max_steps:
        step_no += 1
        benign_tested = policy_mod.benign_tested(hypotheses, state.plan_steps, state.tool_calls)
        tag = f"plan.s{step_no}"

        # deterministic stop conditions are enforced in Python, never left to the model
        stop = planner_mod.evaluate_stop(specs, hypotheses, state.evidence, triage,
                                         state.remaining, benign_tested, state.probed_dims)
        if stop:
            args_for = {s.name: planner_mod.build_args(s, case, hypotheses) for s in specs}
            step = planner_mod.deterministic_plan_step(
                step_no, stop, specs, hypotheses, state.evidence, triage, state.remaining,
                state.called_keys, benign_tested, args_for, state.probed_dims,
            )
            state.plan_steps.append(step)
            yield from emit(
                EventType.plan_step,
                f"Investigation complete after {state.calls_made} check(s): {stop.replace('_', ' ')}. "
                f"{len(state.evidence)} evidence items recorded.",
                {"plan_step": step.model_dump(mode="json")},
            )
            yield from emit(
                EventType.budget_updated,
                f"Budget: {state.remaining} of {state.budget_limit} units remaining "
                f"({state.calls_made} calls made).",
                {"budget": _budget_payload(state, specs)},
            )
            break

        t0 = time.monotonic()
        if llm is not None:
            step, _ok = planner_mod.llm_plan_step(
                step_no, triage, hypotheses, state.evidence, specs, state.remaining,
                state.called_keys, benign_tested, case, llm, tag, state.probed_dims,
            )
        else:
            step = fb.fallback_plan(step_no, specs, case, hypotheses, state.evidence, triage,
                                    state.remaining, state.called_keys, benign_tested,
                                    state.probed_dims)
        state.plan_steps.append(step)
        stop_txt = f" Stopping: {step.stop_reason}." if step.chosen_tool is None else ""
        yield from emit(
            EventType.plan_step,
            f"Plan step {step_no}: {step.reasoning[:180]}{stop_txt}",
            {"plan_step": step.model_dump(mode="json")},
            t0,
        )
        yield from emit(
            EventType.budget_updated,
            f"Budget: {state.remaining} of {state.budget_limit} units remaining "
            f"({state.calls_made} calls made).",
            {"budget": _budget_payload(state, specs)},
        )
        if step.chosen_tool is None:
            break

        # ---------------------------------------------------------------- ACT
        spec = next((s for s in specs if s.name == step.chosen_tool), None)
        call_id = f"{run_id}-c{step_no}"
        t0 = time.monotonic()
        yield from emit(
            EventType.tool_call_started,
            f"Calling {step.chosen_tool} — {step.reasoning[:140]}",
            {
                "call_id": call_id,
                "tool": step.chosen_tool,
                "args": step.chosen_args,
                "targets_hypotheses": step.targets_hypotheses,
            },
        )
        try:
            result: ToolResult = tools.call(step.chosen_tool, dict(step.chosen_args))
        except Exception as exc:  # ToolRegistry.call must never raise, but belt and braces
            result = ToolResult(
                tool=step.chosen_tool, call_id=call_id, args=dict(step.chosen_args), ok=False,
                summary=f"Tool call failed: {exc}", observations=[], raw={}, sources=[],
                cost_units=spec.cost_units if spec else 1, latency_ms=0, error=str(exc),
            )
        state.tool_calls.append(result)
        state.called_keys.add(canonical_json([result.tool, dict(result.args)]))
        if spec:
            state.probed_dims.update(d.value for d in spec.dimensions)
        yield from emit(
            EventType.tool_call_completed,
            f"{result.tool} returned ({'ok' if result.ok else 'failed'}): {result.summary[:160]}",
            {"tool_result": result.model_dump(mode="json")},
            t0,
        )
        state.budget_spent += result.cost_units
        state.calls_made += 1
        yield from emit(
            EventType.budget_updated,
            f"Spent {state.budget_spent} of {state.budget_limit} units; "
            f"{state.remaining} remaining.",
            {"budget": _budget_payload(state, specs)},
        )

        # --------------------------------------------------- INTERPRET + UPDATE
        t0 = time.monotonic()
        try:
            if llm is not None:
                new_items, updates = ledger_mod.run_interpret(
                    hypotheses, result, state.evidence, llm, state.evidence_next_id,
                    tag=f"interpret.{result.call_id}",
                )
            else:
                raise RuntimeError("no llm")
        except Exception as exc:
            state.note_degraded(f"interpret:{result.tool}")
            new_items, updates = fb.fallback_interpret(
                hypotheses, result, state.evidence, state.evidence_next_id
            )
        _, hyp_changed = hyp_mod.apply_updates(hypotheses, new_items, updates)
        state.evidence.extend(new_items)
        state.evidence_next_id += len(new_items)

        for item in new_items:
            graph.add_evidence(item, result)
            yield from emit(
                EventType.evidence_added,
                f"Evidence {item.evidence_id} [{item.dimension.value}/{item.stance.value}]: "
                f"{item.statement[:150]}",
                {"evidence": item.model_dump(mode="json")},
            )
        if new_items:
            snap, new_nodes, new_edges = graph.snapshot()
            yield from emit(
                EventType.graph_updated,
                f"Evidence graph grew by {len(new_nodes)} nodes and {len(new_edges)} edges.",
                {
                    "nodes_added": [n.model_dump(mode="json") for n in new_nodes],
                    "edges_added": [e.model_dump(mode="json") for e in new_edges],
                },
            )
        yield from emit(
            EventType.hypotheses_updated,
            "Posteriors updated: "
            + "; ".join(
                f"{h.hypothesis_id}={h.posterior:.2f} ({h.status.value})" for h in hypotheses
            ),
            {
                "hypotheses": [h.model_dump(mode="json") for h in hypotheses],
                "changed_ids": hyp_changed or [h.hypothesis_id for h in hypotheses],
            },
            t0,
        )

    # ---------------------------------------------------------- corroborate
    t0 = time.monotonic()
    corr = corr_mod.compute_facts(state.evidence, hypotheses)
    corr.narrative = corr_mod.run_narrative(corr, state.evidence, llm, tag="corroborate") if llm is not None \
        else corr_mod.default_narrative(corr, state.evidence)
    yield from emit(
        EventType.corroboration,
        f"Corroboration: {corr.independent_signal_count} independent supporting signals across "
        f"{[d.value for d in corr.corroborated_dimensions] or ['none']}.",
        {"corroboration": corr.model_dump(mode="json")},
        t0,
    )

    # --------------------------------------------------------------- decide
    decision: Decision = policy_mod.decide(
        state.evidence, hypotheses, corr, state.tool_calls, state.plan_steps,
        degraded=state.degraded,
    )
    if state.degraded and DEGRADED_CAVEAT not in decision.caveats:
        decision.caveats.append(DEGRADED_CAVEAT)
    yield from emit(
        EventType.decision,
        f"Decision: {decision.verdict.value.upper()} — {decision.headline[:160]}",
        {"decision": decision.model_dump(mode="json")},
    )

    # --------------------------------------------------------------- ask for more
    t0 = time.monotonic()
    requests = (
        req_mod.run_requests(decision.verdict, hypotheses, llm, tag="requests")
        if llm is not None
        else req_mod.deterministic_requests(hypotheses, decision.verdict)
    )
    if decision.verdict.value == "hold" and not requests:
        requests = req_mod.deterministic_requests(hypotheses, decision.verdict) or [
            EvidenceRequest(
                item="The original purchase or sale contract including the pricing schedule",
                why="to close the remaining uncertainty on the live hypotheses",
                resolves_hypotheses=[h.hypothesis_id for h in hypotheses if h.status in ("open", "weakened")][:2],
                priority=1,
            )
        ]
    yield from emit(
        EventType.evidence_requested,
        f"{len(requests)} documentation request(s) prepared for the customer."
        if requests
        else "No further documentation required.",
        {"requests": [r.model_dump(mode="json") for r in requests]},
        t0,
    )

    # ------------------------------------------------------------- write up
    t0 = time.monotonic()
    prose = report_mod.run_report_prose(
        decision, case,
        [e for e in state.evidence if e.stance.value == "supports_suspicion"],
        [e for e in state.evidence if e.stance.value == "refutes_suspicion"],
        hypotheses, llm, tag="report",
    )
    finished_at = utcnow()
    final_graph, _, _ = graph.snapshot()
    warnings = provenance_warnings(final_graph)
    budget_payload = _budget_payload(state, specs)
    if _env_flag("FEATURE_BUDGET"):
        budget_payload["tools_skipped"] = [
            sk.model_dump(mode="json")
            for sk in planner_mod.skipped_tools(specs, [t.tool for t in state.tool_calls],
                                                state.remaining,
                                                planner_mod.score_tools(
                                                    specs, hypotheses, state.evidence, triage,
                                                    state.called_keys, True,
                                                    {s.name: planner_mod.build_args(s, case, hypotheses)
                                                     for s in specs}))
        ]
    meta = RunMeta(
        run_id=run_id,
        case_id=case.case_id,
        started_at=state.started_at,
        finished_at=finished_at,
        model=state.model,
        llm_calls=int(getattr(llm, "usage", {}).get("calls", 0)) if llm is not None else 0,
        prompt_tokens=int(getattr(llm, "usage", {}).get("prompt_tokens", 0)) if llm is not None else 0,
        completion_tokens=int(getattr(llm, "usage", {}).get("completion_tokens", 0)) if llm is not None else 0,
        wall_ms=int((finished_at - state.started_at).total_seconds() * 1000),
        replayed=bool(getattr(llm, "replayed", False)),
        degraded=state.degraded,
    )
    result = InvestigationResult(
        meta=meta,
        record=case.record.model_dump(mode="json"),
        triage=triage,
        hypotheses=hypotheses,
        plan_steps=state.plan_steps,
        tool_calls=state.tool_calls,
        evidence_for=[e for e in state.evidence if e.stance.value == "supports_suspicion"],
        evidence_against=[e for e in state.evidence if e.stance.value == "refutes_suspicion"],
        evidence_neutral=[e for e in state.evidence if e.stance.value == "neutral"],
        budget=budget_payload,
        graph=final_graph,
        decision=decision,
        evidence_requests=requests,
        report_markdown="",
        events=[ev.model_dump(mode="json") for ev in events],
    )
    result.report_markdown = report_mod.render_report(
        case=case, run_id=run_id, model=state.model, decision=decision, prose=prose,
        record=result.record, hypotheses=hypotheses, plan_steps=state.plan_steps,
        tool_calls=state.tool_calls,
        evidence_for=result.evidence_for, evidence_against=result.evidence_against,
        evidence_neutral=result.evidence_neutral, requests=requests, events=events,
        graph=final_graph,
        started_at=state.started_at.isoformat(), finished_at=finished_at.isoformat(),
    )
    if warnings:
        result.report_markdown += "\n> Provenance warnings: " + "; ".join(warnings) + "\n"
    yield from emit(
        EventType.report_ready,
        f"Investigation complete: {decision.verdict.value.upper()}. Dossier ready.",
        {
            "result": result.model_dump(mode="json"),
            "report_markdown": result.report_markdown,
        },
        t0,
    )


def _budget_payload(state: _RunState, specs: list | None = None) -> dict[str, Any]:
    return {
        "limit": state.budget_limit,
        "spent": state.budget_spent,
        "remaining": state.remaining,
        "calls_made": state.calls_made,
        "tools_skipped": [],
        "exhaustive_cost": sum(s.cost_units for s in specs) if specs else None,
    }
