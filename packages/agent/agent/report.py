"""The dossier writer: structure is templated from the result object; only the
executive summary and key-findings prose come from the LLM. Must read like
something a bank investigator wrote.
"""
from __future__ import annotations

from typing import Any

from interpretex_contracts import (
    AgentCaseView,
    Decision,
    EvidenceGraph,
    EvidenceItem,
    EvidenceRequest,
    Hypothesis,
    InvestigationEvent,
    PlanStep,
    ToolResult,
    Verdict,
)

from .prompts import load_template
from .schemas import REPORT_SCHEMA

_VERDICT_TITLE = {
    Verdict.release: "RELEASE",
    Verdict.hold: "HOLD — REQUEST DOCUMENTATION",
    Verdict.escalate: "ESCALATE / BLOCK",
}


def _esc(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def build_messages(
    decision: Decision,
    case: AgentCaseView,
    evidence_for: list[EvidenceItem],
    evidence_against: list[EvidenceItem],
    hypotheses: list[Hypothesis],
) -> tuple[str, list[dict[str, str]]]:
    system = load_template("report")
    ev_lines = "\n".join(
        f"- {e.evidence_id} [{e.dimension.value}/{e.stance.value}] {e.statement}" for e in evidence_for
    ) or "(none)"
    ev_against_lines = "\n".join(
        f"- {e.evidence_id} [{e.dimension.value}/{e.stance.value}] {e.statement}" for e in evidence_against
    ) or "(none)"
    hyp_lines = "\n".join(
        f"- {h.hypothesis_id} [{h.kind.value}] post={h.posterior:.2f} {h.status.value}: {h.statement}"
        for h in hypotheses
    )
    user = (
        f"DECISION: {decision.verdict.value}; headline: {decision.headline}; rationale: {decision.rationale}\n\n"
        f"TRADE: {case.record.commodity} {case.record.quantity}{case.record.unit} at "
        f"{case.record.unit_price} {case.record.currency}; exporter {case.record.exporter_id}; "
        f"importer {case.record.importer_id}; vessel {case.record.vessel_name or 'n/a'}.\n\n"
        f"EVIDENCE FOR:\n{ev_lines}\n\nEVIDENCE AGAINST:\n{ev_against_lines}\n\nHYPOTHESES:\n{hyp_lines}\n\n"
        "Return the report prose JSON object now."
    )
    return system, [{"role": "user", "content": user}]


def run_report_prose(
    decision: Decision,
    case: AgentCaseView,
    evidence_for: list[EvidenceItem],
    evidence_against: list[EvidenceItem],
    hypotheses: list[Hypothesis],
    llm: Any,
    tag: str = "report",
) -> dict[str, Any]:
    """Returns {'executive_summary': str, 'key_findings': [str]} — template on failure."""
    fallback = {
        "executive_summary": (
            f"The trade presents itself as a {case.record.commodity} shipment of {case.record.quantity} "
            f"{case.record.unit} at {case.record.unit_price} {case.record.currency} per {case.record.unit}. "
            f"The investigation examined the documentary, economic, physical, temporal, behavioural and "
            f"network dimensions within budget. {decision.headline} "
            f"The recommendation is {decision.verdict.value.upper()}; a human investigator should review "
            f"the evidence ledger before acting."
        ),
        "key_findings": [
            f"{e.evidence_id} [{e.dimension.value}] {e.statement}" for e in evidence_for[:4]
        ] or ["No significant supporting findings were identified in the dimensions examined."],
    }
    system, messages = build_messages(decision, case, evidence_for, evidence_against, hypotheses)
    try:
        data = llm.complete_json(
            system=system, messages=messages, schema=REPORT_SCHEMA, temperature=0.3,
            max_tokens=900, tag=tag,
        )
        summary = str(data.get("executive_summary", "")).strip()
        findings = [str(f) for f in (data.get("key_findings") or []) if str(f).strip()]
        if not summary:
            return fallback
        return {"executive_summary": summary, "key_findings": findings or fallback["key_findings"]}
    except Exception:
        return fallback


def render_report(
    *,
    case: AgentCaseView,
    run_id: str,
    model: str,
    decision: Decision,
    prose: dict[str, Any],
    record: dict[str, Any],
    hypotheses: list[Hypothesis],
    plan_steps: list[PlanStep],
    tool_calls: list[ToolResult],
    evidence_for: list[EvidenceItem],
    evidence_against: list[EvidenceItem],
    evidence_neutral: list[EvidenceItem],
    requests: list[EvidenceRequest],
    events: list[InvestigationEvent],
    graph: EvidenceGraph,
    started_at: str,
    finished_at: str,
) -> str:
    r = record
    lines: list[str] = []
    add = lines.append

    add("# TRADE INVESTIGATION REPORT")
    add(f"Case {case.case_id} · Run {run_id} · {finished_at} · Model {model}")
    add("")
    add(f"## DECISION: {_VERDICT_TITLE[decision.verdict]}")
    add(f"{decision.headline}  ")
    add(f"Confidence {int(round(decision.confidence * 100))}%")
    add("")
    add("## EXECUTIVE SUMMARY")
    add(prose["executive_summary"])
    add("")
    add("## TRADE OVERVIEW")
    add(
        f"Buyer: {_esc(r.get('importer_id', 'n/a'))} · Seller: {_esc(r.get('exporter_id', 'n/a'))} · "
        f"Broker: {_esc(r.get('broker_id') or 'n/a')} · Commodity: {_esc(r.get('commodity'))} "
        f"{_esc(r.get('commodity_grade') or '')} · HS code: {_esc(r.get('hs_code') or 'n/a')} · "
        f"Quantity: {_esc(r.get('quantity'))} {_esc(r.get('unit'))} · "
        f"Unit price: {_esc(r.get('unit_price'))} {_esc(r.get('currency'))} · "
        f"Total value: {_esc(r.get('total_value'))} {_esc(r.get('currency'))} · "
        f"Incoterm: {_esc(r.get('incoterm') or 'n/a')} · Vessel: {_esc(r.get('vessel_name') or 'n/a')} · "
        f"Route: {_esc(r.get('origin_port') or '?')} → {_esc(r.get('destination_port') or '?')} · "
        f"Shipped: {_esc(r.get('ship_date') or 'n/a')} · Arrived: {_esc(r.get('arrival_date') or 'n/a')} · "
        f"LC reference: {_esc(r.get('lc_number') or 'n/a')}"
    )
    add("")
    add("## KEY FINDINGS")
    for finding in prose.get("key_findings", []):
        add(f"- {finding}")
    add("")
    add("## EVIDENCE SUPPORTING CONCERN")
    if evidence_for:
        add("| Id | Dimension | Finding | Severity | Weight | Source |")
        add("|---|---|---|---|---|---|")
        for e in evidence_for:
            src = "; ".join(s.ref for s in e.sources[:2]) or "derived"
            add(f"| {e.evidence_id} | {e.dimension.value} | {_esc(e.statement)} | {e.severity.value} | "
                f"{e.weight:.2f} | {_esc(src)} |")
    else:
        add("_None. The checks performed found no evidence supporting concern._")
    add("")
    add("## EVIDENCE AGAINST CONCERN")
    if evidence_against:
        add("| Id | Dimension | Finding | Weight | Source |")
        add("|---|---|---|---|---|")
        for e in evidence_against:
            src = "; ".join(s.ref for s in e.sources[:2]) or "derived"
            add(f"| {e.evidence_id} | {e.dimension.value} | {_esc(e.statement)} | {e.weight:.2f} | {_esc(src)} |")
    else:
        add(
            "_No evidence against the concern was found. The investigation specifically looked for "
            "supporting contracts, offtake agreements, price-consistent customer history and documentary "
            "consistency that would account for the anomalies; none of these was found for this case._"
        )
    add("")
    add("## HYPOTHESES CONSIDERED")
    add("| Id | Kind | Statement | Prior → Posterior | Status | Why it moved |")
    add("|---|---|---|---|---|---|")
    for h in hypotheses:
        add(f"| {h.hypothesis_id} | {h.kind.value} | {_esc(h.statement)} | {h.prior:.2f} → {h.posterior:.2f} | "
            f"{h.status.value} | {_esc(h.rationale or 'unchanged')} |")
    add("")
    add("## INVESTIGATIONS PERFORMED")
    add("| # | Tool | Why chosen | Cost | What it returned |")
    add("|---|---|---|---|---|")
    for step in plan_steps:
        if not step.chosen_tool:
            add(f"| {step.step} | — (stop) | {_esc(step.reasoning)} | 0 | stop_reason: {step.stop_reason} |")
            continue
        tr = next((t for t in tool_calls if t.tool == step.chosen_tool and t.args == step.chosen_args), None)
        summary = tr.summary if tr else "no result recorded"
        add(f"| {step.step} | {step.chosen_tool} | {_esc(step.reasoning)} | "
            f"{tr.cost_units if tr else '?'} | {_esc(summary)} |")
    rejected = [
        f"- {c.tool}: {c.why_not} (expected gain {c.expected_information_gain:.2f})"
        for step in plan_steps for c in step.considered
    ]
    if rejected:
        add("")
        add("Tools considered and NOT chosen:")
        lines.extend(dict.fromkeys(rejected))
    add("")
    add("## CORROBORATION ANALYSIS")
    add(decision.corroboration.narrative or "No corroboration analysis was performed.")
    add("")
    add("## TIMELINE OF AGENT ACTIONS")
    t0 = events[0].ts if events else None
    for ev in events:
        delta = f"+{(ev.ts - t0).total_seconds():.1f}s" if t0 else "-"
        add(f"- `{delta}` [{ev.seq}] {ev.type.value}: {_esc(ev.narration)}")
    add("")
    add("## RISK TYPOLOGY")
    add(decision.typology or "None identified")
    add("")
    add("## RECOMMENDED ACTION")
    if decision.verdict == Verdict.release:
        add("Release the case. No significant corroborated anomaly was identified in the dimensions examined.")
    elif decision.verdict == Verdict.hold:
        add("Hold the case and request the documentation below before releasing. Do not escalate on the "
            "current record: the outstanding uncertainty is resolvable with customer documentation.")
    else:
        add("Escalate to the trade-based money laundering review team with the evidence dossier attached. "
            "Recommend blocking further disbursements pending human review.")
    add("")
    add("## ADDITIONAL DOCUMENTATION REQUESTED")
    if requests:
        add("| Priority | Item | Why | Resolves |")
        add("|---|---|---|---|")
        for req in requests:
            add(f"| {req.priority} | {_esc(req.item)} | {_esc(req.why)} | {_esc(', '.join(req.resolves_hypotheses))} |")
    else:
        add("_None._")
    add("")
    add("## LIMITATIONS AND CAVEATS")
    for caveat in decision.caveats:
        add(f"- {caveat}")
    add("")
    add("## PROVENANCE")
    for e in [*evidence_for, *evidence_against, *evidence_neutral]:
        chain = " → ".join(s.ref for s in e.sources) or "derived (no source refs on tool output)"
        add(f"- {e.evidence_id} [{e.dimension.value}]: {chain}")
    reach_ok = "yes" if not _graph_warnings(graph) else "WARNINGS PRESENT"
    add("")
    add(f"Graph provenance check (every finding reachable from a source node): {reach_ok}.")
    add("")
    return "\n".join(lines)


def _graph_warnings(graph: EvidenceGraph) -> list[str]:
    from .graph import provenance_warnings

    return provenance_warnings(graph)
