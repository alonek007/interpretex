"""check_document_consistency — per-field agreement across the whole doc set."""

from __future__ import annotations

from datetime import date

from interpretex_contracts import (
    Dimension, DocType, Observation, Severity, ToolSpec,
)

from .base import ToolOutcome, clip, derived_source, doc_source, same_number, same_text

#: fields compared whenever two or more documents carry them
COMPARE_FIELDS = [
    "commodity", "hs_code", "quantity", "gross_weight_tons", "net_weight_tons",
    "unit_price", "total_value", "container_count", "origin_port",
    "destination_port", "vessel_name", "ship_date", "exporter_id", "importer_id",
    "currency", "incoterm", "lc_number",
]

#: fields where a textual difference is material (goods identity)
MATERIAL_TEXT_FIELDS = {"commodity"}

NUMERIC_FIELDS = {"quantity", "gross_weight_tons", "net_weight_tons", "unit_price",
                  "total_value", "container_count"}

SPEC = ToolSpec(
    name="check_document_consistency",
    description=(
        "Compares every field carried by two or more documents in the case file "
        "and reports each disagreement, naming both documents and both values. "
        "Covers description drift, quantity/weight mismatches, HS-code mismatches "
        "and conflicting dates, ports or parties. Separates clerical error from "
        "deliberate misdescription only in the sense that it shows WHICH documents "
        "disagree and by how much."
    ),
    dimensions=[Dimension.documentary],
    args_schema={
        "type": "object",
        "properties": {
            "fields": {"type": "array", "items": {"type": "string"},
                       "description": "restrict the comparison to these fields"},
        },
        "additionalProperties": True,
    },
    cost_units=1,
    discriminates=["clerical error", "deliberate misdescription",
                   "documents describe different goods"],
)


def _field_severity(field_name: str, values: list) -> tuple[Severity, bool]:
    """Returns (severity, is_numeric_comparison)."""
    if all(isinstance(v, (int, float)) for v in values):
        lo, hi = min(values), max(values)
        frac = (hi - lo) / max(abs(hi), 1.0)
        return (Severity.high if frac > 0.05 else Severity.medium), True
    if field_name in MATERIAL_TEXT_FIELDS:
        return Severity.high, False
    if field_name == "hs_code":
        return Severity.medium, False
    return Severity.medium, False


def run(reg, args: dict) -> ToolOutcome:
    restrict = args.get("fields") or None
    docs = reg.documents
    matrix: dict[str, dict[str, object]] = {}
    for field_name in (restrict or COMPARE_FIELDS):
        values: dict[str, object] = {}
        for doc in docs:
            if field_name in doc.fields:
                values[doc.doc_id] = doc.fields[field_name]
        if len(values) >= 2:
            matrix[field_name] = values

    observations: list[Observation] = []
    raw: dict = {}
    sources = [derived_source("check_document_consistency", "fields_compared",
                              float(len(matrix)))]

    for field_name, values in matrix.items():
        distinct = []
        for v in values.values():
            if not any(
                    (same_number(v, w) if isinstance(v, (int, float)) and isinstance(w, (int, float))
                     else (same_text(v, w) if isinstance(v, str) and isinstance(w, str) else v == w))
                    for w in distinct):
                distinct.append(v)
        if len(distinct) <= 1:
            continue
        # name both documents and both values (all values in raw)
        pairs = list(values.items())
        a_id, a_val = pairs[0]
        b_id, b_val = pairs[1]
        severity, _numeric = _field_severity(field_name, list(values.values()))
        fmt = (lambda v: f"{float(v):,.2f}") if all(
            isinstance(v, (int, float)) for v in values.values()) else (lambda v: f"'{v}'")
        extra = f" (and {len(pairs) - 2} more documents)" if len(pairs) > 2 else ""
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.documentary,
            statement=(f"Field '{field_name}' differs across documents: {a_id} states "
                       f"{fmt(a_val)} while {b_id} states {fmt(b_val)}{extra}."),
            severity=severity,
            metrics={"distinct_values": float(len(distinct)), "documents": float(len(pairs))},
            sources=[doc_source(a_id, field_name, a_val), doc_source(b_id, field_name, b_val)],
        ))

    # cross-document date sanity: an insurance certificate dated on or after the
    # shipment means cover began only after the risk had already passed.
    ins_doc = next((d for d in docs if d.doc_type is DocType.insurance_certificate), None)
    bl_doc = next((d for d in docs if d.doc_type is DocType.bill_of_lading), None)
    if ins_doc and bl_doc:
        ins_date = str(ins_doc.fields.get("insurance_issue_date") or "")
        ship = str(bl_doc.fields.get("ship_date") or "")
        if ins_date and ship:
            try:
                gap = (date.fromisoformat(ins_date) - date.fromisoformat(ship)).days
            except ValueError:
                gap = None
            if gap is not None and gap >= 0:
                ins_sev = (Severity.high if gap >= 7
                           else Severity.medium if gap >= 3 else Severity.low)
                observations.append(Observation(
                    observation_id="",
                    dimension=Dimension.temporal,
                    statement=(f"Insurance certificate {ins_doc.doc_id} is dated {ins_date}, "
                               f"issued {gap} day(s) after the goods were shipped on {ship} "
                               f"(bill of lading {bl_doc.doc_id}); cover would begin only after "
                               f"the goods were already in transit."),
                    severity=ins_sev,
                    metrics={"lag_days": float(gap)},
                    sources=[doc_source(ins_doc.doc_id, "insurance_issue_date", ins_date),
                             doc_source(bl_doc.doc_id, "ship_date", ship)],
                ))
                raw["insurance_lag_days"] = gap

    if not observations:
        summary = (f"All {len(matrix)} shared fields agree across the "
                   f"{len(docs)} documents in the case file.")
    else:
        worst = max(o.severity for o in observations)
        summary = clip(f"{len(observations)} field disagreement(s) found across "
                       f"{len(docs)} documents; highest salience {worst.value}.")
    raw["field_matrix"] = {f: {d: v for d, v in vals.items()}
                           for f, vals in matrix.items()}
    return ToolOutcome(ok=True, summary=summary, observations=observations,
                       raw=raw, sources=sources)
