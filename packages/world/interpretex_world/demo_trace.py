"""Scripted demo-trace fixture for case_suspicious_003.

Builds a complete, replayable :class:`InvestigationResult` (events + result)
using the REAL tools so Part 2 can develop its loop against shaped data and
Part 3 can render a finished report before the agent exists. The trace is
deterministic and never uses verdict language in observations or narrations;
the *verdict* lives only in the final Decision, exactly as the contract allows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from interpretex_contracts import (
    BudgetState, Corroboration, Decision, Dimension, EvidenceGraph, EvidenceItem,
    EvidenceRequest, EventType, GraphEdge, GraphNode, Hypothesis, HypothesisKind,
    HypothesisStatus, InvestigationEvent, InvestigationResult, PlanStep, RunMeta,
    Severity, SourceRef, SourceKind, Stance, ToolResult, Triage, Verdict,
)
from interpretex_contracts.helpers import STANDARD_CAVEATS, new_run_id, utcnow

from .api import load_case, build_tool_registry

CASE_ID = "case_suspicious_003"
MODEL = "scripted-demo-trace/1.0"


def _severity_to_stance(sev: Severity) -> Stance:
    if sev in (Severity.high, Severity.medium):
        return Stance.supports_suspicion
    if sev is Severity.low:
        return Stance.neutral
    return Stance.refutes_suspicion


def _severity_to_weight(sev: Severity) -> float:
    return {Severity.high: 0.9, Severity.medium: 0.6,
            Severity.low: 0.3, Severity.none: 0.1}[sev]


def build() -> InvestigationResult:
    case = load_case(CASE_ID)
    reg = build_tool_registry(case)
    run_id = new_run_id()
    started = utcnow()

    events: list[InvestigationEvent] = []
    seq = 0

    def emit(etype: EventType, narration: str, payload: dict) -> None:
        nonlocal seq
        events.append(InvestigationEvent(
            seq=seq, ts=utcnow(), run_id=run_id, type=etype,
            narration=narration, payload=payload))
        seq += 1

    emit(EventType.run_started, f"Investigation started for {CASE_ID}.",
         {"case_id": CASE_ID, "model": MODEL})
    emit(EventType.case_loaded,
         f"Case {CASE_ID} loaded: copper cathodes, Singapore -> Nhava Sheva.",
         {"case_id": CASE_ID, "document_count": len(case.documents)})

    triage = Triage(
        trade_narrative=("Copper cathodes shipped from Singapore to Nhava Sheva under a "
                         "letter of credit; declared value is well below the reference "
                         "benchmark and several transport facts look inconsistent."),
        initial_concerns=[
            "declared unit price far below the reference benchmark",
            "claimed cargo weight exceeds the vessel's capacity",
            "claimed transit time is far shorter than physically possible",
            "insurance dated after the shipment",
        ],
        unknowns=[
            "whether the price gap is explained by a contract or grade difference",
            "whether the parties share beneficial ownership off the paperwork",
        ],
        dimensions_to_probe=[Dimension.economic, Dimension.physical,
                             Dimension.temporal, Dimension.documentary,
                             Dimension.behavioural, Dimension.network],
    )
    emit(EventType.triage, "Triage recorded initial concerns and dimensions to probe.",
         triage.model_dump())

    hypotheses = [
        Hypothesis(
            hypothesis_id="H1", kind=HypothesisKind.suspicious,
            statement=("The trade understates value and relies on physically impossible "
                       "or inflated documents to move value across the border."),
            explains=[Dimension.economic, Dimension.physical, Dimension.temporal,
                      Dimension.documentary],
            prior=0.5, posterior=0.85, status=HypothesisStatus.supported,
            discriminating_evidence_needed=[
                "price benchmark", "vessel capacity", "transit time",
                "document consistency", "broker history"],
            supporting_evidence_ids=[], contradicting_evidence_ids=[],
            rationale="Multiple independent high-severity signals across dimensions."),
        Hypothesis(
            hypothesis_id="H2", kind=HypothesisKind.benign,
            statement=("The price gap is explained by a genuine contract, grade or volume "
                       "arrangement and the transit/insurance issues are clerical."),
            explains=[Dimension.economic, Dimension.documentary],
            prior=0.5, posterior=0.15, status=HypothesisStatus.weakened,
            discriminating_evidence_needed=["price benchmark", "contract", "historical trade"],
            supporting_evidence_ids=[], contradicting_evidence_ids=[],
            rationale="No contract or grade difference in the file explains a 38% gap."),
    ]
    emit(EventType.hypotheses_updated, "Two hypotheses framed: mispricing vs benign.",
         {"hypotheses": [h.model_dump() for h in hypotheses]})

    tool_results: list[ToolResult] = []
    evidence_items: list[EvidenceItem] = []
    evidence_for: list[EvidenceItem] = []
    evidence_against: list[EvidenceItem] = []
    evidence_neutral: list[EvidenceItem] = []
    plan_steps: list[PlanStep] = []
    graph_nodes: dict[str, GraphNode] = {}
    graph_edges: list[GraphEdge] = []

    tool_order = [s.name for s in reg.specs()]
    claim_for = {"check_contract_or_supporting_evidence": "grade LME Grade A standard"}
    for i, name in enumerate(tool_order, start=1):
        args = {"claim": claim_for[name]} if name in claim_for else {}
        emit(EventType.plan_step, f"Plan: call {name}.", {"step": i, "tool": name})
        plan_steps.append(PlanStep(
            step=i, reasoning=f"Probe dimension(s) covered by {name}.",
            chosen_tool=name, chosen_args=args,
            targets_hypotheses=["H1", "H2"],
            expected_information_gain=0.5,
            considered=[{"tool": "read_document", "expected_information_gain": 0.2,
                         "why_not": "already have the raw fields"}],
        ))
        res = reg.call(name, args)
        tool_results.append(res)
        emit(EventType.tool_call_started, f"Calling {name}.", {"tool": name, "args": args})
        emit(EventType.tool_call_completed,
             f"{name} returned {len(res.observations)} observation(s); {res.summary}",
             {"tool": name, "call_id": res.call_id,
              "observations": len(res.observations), "summary": res.summary})
        emit(EventType.budget_updated, f"Budget: {i}/{8} tools used.",
             {"spent": i, "limit": 8})

        for o in res.observations:
            eid_local = len(evidence_items) + 1
            e = EvidenceItem(
                evidence_id=f"E{eid_local:02d}",
                dimension=o.dimension,
                stance=_severity_to_stance(o.severity),
                statement=o.statement,
                weight=_severity_to_weight(o.severity),
                severity=o.severity,
                hypotheses_affected=["H1"] if o.severity in (Severity.high, Severity.medium)
                else ["H2"],
                observation_ids=[o.observation_id],
                tool_call_id=res.call_id,
                sources=o.sources or [SourceRef(kind=SourceKind.document, ref="case_file")],
                interpretation=("high-severity signal, independent of the others"
                                if o.severity is Severity.high else None),
            )
            evidence_items.append(e)
            if e.stance is Stance.supports_suspicion:
                evidence_against.append(e)
            elif e.stance is Stance.refutes_suspicion:
                evidence_for.append(e)
            else:
                evidence_neutral.append(e)
            graph_nodes[f"tool:{name}"] = GraphNode(
                id=f"tool:{name}", kind="tool", label=name, dimension=o.dimension, meta={})
            graph_nodes[o.observation_id] = GraphNode(
                id=o.observation_id, kind="finding", label=o.statement[:60],
                dimension=o.dimension, severity=o.severity, meta={})
            graph_edges.append(GraphEdge(
                source=f"tool:{name}", target=o.observation_id,
                relation="produced", label=o.severity.value))
            emit(EventType.evidence_added,
                 f"Evidence E{eid_local:02d} ({o.severity.value}): {o.statement[:80]}",
                 {"evidence_id": e.evidence_id, "observation_id": o.observation_id})

    high_dims = sorted({o.dimension.value for r in tool_results for o in r.observations
                        if o.severity is Severity.high})
    corroboration = Corroboration(
        corroborated_dimensions=[Dimension(d) for d in high_dims],
        independent_signal_count=len(high_dims),
        refuting_dimensions=[],
        strongest_benign_hypothesis="H2",
        strongest_benign_posterior=0.15,
        narrative=("Price, capacity, transit, document-description and broker-history "
                   "signals are independent of one another (different documents, different "
                   "reference tables); a single clerical error cannot explain all of them."),
    )
    emit(EventType.corroboration,
         f"Corroboration: {len(high_dims)} independent high-severity dimension(s).",
         corroboration.model_dump())

    decision = Decision(
        verdict=Verdict.escalate,
        confidence=0.9,
        headline=("Multiple independent high-severity signals (under-pricing, impossible "
                  "transit, over-capacity, description drift, recurring broker); escalate "
                  "for human review."),
        rationale=("Seven high-severity observations span five independent dimensions. No "
                   "contract, grade difference or benign prior explains the 38% price gap; "
                   "the broker recurs across previously escalated trades. " +
                   "; ".join(e.evidence_id for e in evidence_against
                             if e.severity is Severity.high) + " are decisive."),
        corroboration=corroboration,
        typology="trade-based misinvoicing (value understatement + document fabrication)",
        caveats=STANDARD_CAVEATS,
        decisive_evidence_ids=[e.evidence_id for e in evidence_against
                               if e.severity is Severity.high],
    )
    emit(EventType.decision,
         f"Decision: ESCALATE (confidence {decision.confidence:.2f}).",
         decision.model_dump())

    requests = [
        EvidenceRequest(item="Pre-shipment inspection report from an independent surveyor",
                        why="Confirm actual cargo weight and grade against the papers.",
                        resolves_hypotheses=["H1", "H2"], priority=1),
        EvidenceRequest(item="Beneficial-ownership register filings for the exporter and broker",
                        why="Test the shared-ownership hypothesis beyond the reference world.",
                        resolves_hypotheses=["H1"], priority=2),
    ]
    emit(EventType.evidence_requested,
         "Evidence requested: independent inspection and UBO filings.",
         {"requests": [r.model_dump() for r in requests]})

    report = (
        f"# Investigation report — {CASE_ID}\n\n"
        f"**Verdict: ESCALATE** (confidence {decision.confidence:.2f})\n\n"
        f"{decision.headline}\n\n"
        f"## Evidence\n" +
        "\n".join(f"- **{e.evidence_id}** ({e.severity.value}): {e.statement}"
                  for e in evidence_items if e.severity in (Severity.high, Severity.medium))
        + "\n\n## Caveats\n" + "\n".join(f"- {c}" for c in STANDARD_CAVEATS)
    )
    emit(EventType.report_ready, "Report ready.", {"verdict": "escalate"})

    finished = utcnow()
    meta = RunMeta(
        run_id=run_id, case_id=CASE_ID, started_at=started, finished_at=finished,
        model=MODEL, llm_calls=0, prompt_tokens=0, completion_tokens=0,
        wall_ms=int((finished - started).total_seconds() * 1000) or 1,
        replayed=True, degraded=False,
    )
    budget = BudgetState(
        limit=8, spent=len(tool_results), remaining=8 - len(tool_results),
        calls_made=len(tool_results), tools_skipped=[],
        exhaustive_cost=sum(r.cost_units for r in tool_results),
    )
    result = InvestigationResult(
        meta=meta, record=case.record, triage=triage, hypotheses=hypotheses,
        plan_steps=plan_steps, tool_calls=tool_results,
        evidence_for=evidence_for, evidence_against=evidence_against,
        evidence_neutral=evidence_neutral, budget=budget,
        graph=EvidenceGraph(nodes=list(graph_nodes.values()), edges=graph_edges),
        decision=decision, evidence_requests=requests,
        report_markdown=report, events=events,
    )
    return result


def write_fixtures(fixtures_dir: str) -> None:
    from pathlib import Path
    d = Path(fixtures_dir) / "runs"
    d.mkdir(parents=True, exist_ok=True)
    result = build()
    (d / f"{CASE_ID}.events.jsonl").write_text(
        "\n".join(e.model_dump_json() for e in result.events) + "\n", encoding="utf-8")
    (d / f"{CASE_ID}.result.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8")
    print(f"wrote {len(result.events)} events + result for {CASE_ID}")


if __name__ == "__main__":
    import os
    here = Path(os.path.abspath(__file__)).resolve().parents[3]
    out = os.path.join(here, "packages", "contracts", "interpretex_contracts", "fixtures")
    write_fixtures(out)
