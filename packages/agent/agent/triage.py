"""Triage stage: one structured LLM call describing what the trade claims to be.

Do not conclude anything here — triage names concerns, unknowns and the
dimensions worth probing. Degrades via fallback.py when the LLM fails.
"""
from __future__ import annotations

from typing import Any

from interpretex_contracts import AgentCaseView, Dimension, ToolSpec, Triage

from .schemas import TRIAGE_SCHEMA

_MAX_RAW = 400
_MAX_DOCS = 8
_MAX_CONCERNS = 8
_MAX_UNKNOWNS = 8


def _record_line(case: AgentCaseView) -> str:
    r = case.record
    parts = [
        f"commodity={r.commodity}",
        f"quantity={r.quantity}{r.unit}",
        f"unit_price={r.unit_price} {r.currency}",
        f"total_value={r.total_value} {r.currency}",
        f"exporter={r.exporter_id}",
        f"importer={r.importer_id}",
    ]
    optional = {
        "grade": r.commodity_grade,
        "hs_code": r.hs_code,
        "incoterm": r.incoterm,
        "broker": r.broker_id,
        "vessel": r.vessel_name,
        "imo": r.imo,
        "containers": r.container_count,
        "gross_weight_tons": r.gross_weight_tons,
        "route": f"{r.origin_port}->{r.destination_port}" if r.origin_port or r.destination_port else None,
        "ship_date": r.ship_date,
        "arrival_date": r.arrival_date,
        "insurance_issue_date": r.insurance_issue_date,
        "lc_number": r.lc_number,
    }
    parts += [f"{k}={v}" for k, v in optional.items() if v not in (None, "")]
    return "; ".join(parts)


def _document_lines(case: AgentCaseView) -> str:
    lines = []
    for doc in case.documents[:_MAX_DOCS]:
        fields = "; ".join(f"{k}={v}" for k, v in list(doc.fields.items())[:12])
        raw = " ".join(doc.raw_text.split())[:_MAX_RAW]
        lines.append(
            f"- {doc.doc_id} [{doc.doc_type.value}] issuer={doc.issuer} "
            f"issue_date={doc.issue_date or 'n/a'}\n  fields: {fields or '(none)'}\n"
            f"  raw_text (<= {_MAX_RAW} chars): {raw or '(none)'}"
        )
    return "\n".join(lines) or "(no documents)"


def build_messages(case: AgentCaseView, tool_specs: list[ToolSpec]) -> tuple[str, list[dict[str, str]]]:
    from .prompts import load_template

    system = load_template("triage")
    tools = "; ".join(
        f"{s.name} ({'/'.join(d.value for d in s.dimensions)}, cost {s.cost_units})" for s in tool_specs
    )
    user = (
        f"RECORD: {_record_line(case)}\n\n"
        f"DOCUMENTS:\n{_document_lines(case)}\n\n"
        f"APPLICANT_NOTE: {case.applicant_note or '(none)'}\n\n"
        f"TOOLS: {tools}\n\n"
        "Return the triage JSON object now."
    )
    return system, [{"role": "user", "content": user}]


def _clean_dimensions(raw: Any) -> list[Dimension]:
    out: list[Dimension] = []
    for item in raw or []:
        try:
            dim = Dimension(str(item))
        except ValueError:
            continue
        if dim not in out:
            out.append(dim)
    return out


def run_triage(case: AgentCaseView, tool_specs: list[ToolSpec], llm: Any, tag: str = "triage") -> Triage:
    """LLM triage. Raises on LLM failure — the loop degrades per stage."""
    system, messages = build_messages(case, tool_specs)
    data = llm.complete_json(
        system=system,
        messages=messages,
        schema=TRIAGE_SCHEMA,
        temperature=0.1,
        max_tokens=1024,
        tag=tag,
    )
    return Triage(
        trade_narrative=str(data.get("trade_narrative", "")).strip() or "Trade narrative unavailable.",
        initial_concerns=[str(c) for c in (data.get("initial_concerns") or [])][:_MAX_CONCERNS],
        unknowns=[str(u) for u in (data.get("unknowns") or [])][:_MAX_UNKNOWNS],
        dimensions_to_probe=_clean_dimensions(data.get("dimensions_to_probe")),
    )
