"""read_document — return one document's structured fields and raw text."""

from __future__ import annotations

from interpretex_contracts import Dimension, DocType, Observation, Severity, ToolSpec

from .base import ToolOutcome, clip, derived_source, doc_source, same_number

SPEC = ToolSpec(
    name="read_document",
    description=(
        "Returns the structured fields and the raw text of ONE case document. "
        "Use first to see what the paperwork actually claims; separates "
        "'what the paperwork states' from 'documentation or data-entry error' "
        "when a document contradicts itself."
    ),
    dimensions=[Dimension.documentary],
    args_schema={
        "type": "object",
        "properties": {
            "doc_type": {"type": "string", "enum": [d.value for d in DocType]},
            "doc_id": {"type": "string"},
        },
        "additionalProperties": True,
    },
    cost_units=1,
    discriminates=["what the paperwork actually claims", "documentation or data-entry error"],
)


def _line_items_total(fields: dict) -> float | None:
    items = fields.get("line_items")
    if not items:
        return None
    return round(sum(float(i.get("amount", 0.0)) for i in items), 2)


def run(reg, args: dict) -> ToolOutcome:
    doc = None
    if args.get("doc_id"):
        doc = reg.doc_by_id(str(args["doc_id"]))
        if doc is None:
            return ToolOutcome(ok=False,
                               error=f"no document with id {args['doc_id']!r} in this case")
    else:
        dt_raw = str(args.get("doc_type") or DocType.commercial_invoice.value)
        try:
            dt = DocType(dt_raw)
        except ValueError:
            return ToolOutcome(ok=False, error=f"unknown doc_type {dt_raw!r}")
        doc = reg.doc_by_type(dt)
        if doc is None:
            return ToolOutcome(ok=False,
                               error=f"this case file contains no {dt.value} document")

    raw = {"document": doc.model_dump(mode="json")}
    sources = [derived_source("read_document", "fields_present", float(len(doc.fields)))]
    observations: list[Observation] = []

    # internal inconsistency check: invoice line items vs stated total
    if doc.doc_type is DocType.commercial_invoice:
        items_total = _line_items_total(doc.fields)
        stated = doc.fields.get("total_value")
        if items_total is not None and stated is not None:
            try:
                stated_f = float(stated)
            except (TypeError, ValueError):
                stated_f = None
            if stated_f is not None and abs(items_total - stated_f) > 0.01:
                observations.append(Observation(
                    observation_id="",
                    dimension=Dimension.documentary,
                    statement=(f"Invoice {doc.doc_id}: line items sum to "
                               f"{items_total:,.2f} {doc.fields.get('currency', '')} but the "
                               f"document states a total of {stated_f:,.2f}."),
                    severity=Severity.high,
                    metrics={"line_items_total": items_total, "stated_total": stated_f},
                    sources=[doc_source(doc.doc_id, "total_value", stated),
                             doc_source(doc.doc_id, "line_items", items_total)],
                ))
                sources.append(derived_source("read_document", "line_items_total", items_total))

    summary = clip(f"Read {doc.doc_type.value} {doc.doc_id} issued {doc.issue_date} "
                   f"by {doc.issuer}; {len(doc.fields)} fields extracted.")
    return ToolOutcome(ok=True, summary=summary, observations=observations,
                       raw=raw, sources=sources)
