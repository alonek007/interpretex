"""Deterministic, rule-based extraction of the canonical TradeRecord.

Precedence: the letter of credit and the commercial invoice win on commercial
terms; the bill of lading wins on transport; the packing list wins on weights.
A disagreement is NEVER silently reconciled: the winning value is held here
and the conflict stays discoverable by check_document_consistency, which
compares the raw per-document fields.
"""

from __future__ import annotations

from interpretex_contracts import DocType, TradeDocument, TradeRecord

_OPTIONAL = True


def _get(docs: dict[DocType, TradeDocument], doc_type: DocType, field: str,
         default=None):
    doc = docs.get(doc_type)
    if doc is None:
        return default
    return doc.fields.get(field, default)


def _first(docs: dict[DocType, TradeDocument], field: str, *doc_types,
           default=None):
    """First document of the given types (in precedence order) that has the field."""
    for dt in doc_types:
        v = _get(docs, dt, field)
        if v is not None:
            return v
    return default


def extract(documents: list[TradeDocument]) -> TradeRecord:
    """Build the canonical TradeRecord from the case file. No LLM involved."""
    docs: dict[DocType, TradeDocument] = {}
    for d in documents:
        docs.setdefault(d.doc_type, d)  # first of each type wins

    return TradeRecord(
        # commercial terms: LC then invoice win
        commodity=_first(docs, "commodity", DocType.letter_of_credit,
                         DocType.commercial_invoice, default="unknown"),
        commodity_grade=_first(docs, "commodity_grade", DocType.letter_of_credit,
                               DocType.commercial_invoice),
        hs_code=_first(docs, "hs_code", DocType.commercial_invoice,
                       DocType.certificate_of_origin),
        quantity=float(_first(docs, "quantity", DocType.letter_of_credit,
                              DocType.commercial_invoice, default=0.0)),
        unit=str(_first(docs, "unit", DocType.letter_of_credit,
                        DocType.commercial_invoice, default="tonne")),
        unit_price=float(_first(docs, "unit_price", DocType.letter_of_credit,
                                DocType.commercial_invoice, default=0.0)),
        currency=str(_first(docs, "currency", DocType.letter_of_credit,
                            DocType.commercial_invoice, default="USD")),
        total_value=float(_first(docs, "total_value", DocType.letter_of_credit,
                                 DocType.commercial_invoice, default=0.0)),
        incoterm=_first(docs, "incoterm", DocType.letter_of_credit,
                        DocType.commercial_invoice),
        exporter_id=str(_first(docs, "exporter_id", DocType.letter_of_credit,
                               DocType.commercial_invoice, DocType.bill_of_lading,
                               default="unknown")),
        importer_id=str(_first(docs, "importer_id", DocType.letter_of_credit,
                               DocType.commercial_invoice, DocType.bill_of_lading,
                               default="unknown")),
        broker_id=None,  # brokers are reference-world context, not on documents
        insurer_id=_get(docs, DocType.insurance_certificate, "insurer_id"),
        # transport: the bill of lading wins
        vessel_name=_get(docs, DocType.bill_of_lading, "vessel_name"),
        imo=_get(docs, DocType.bill_of_lading, "imo"),
        container_count=_get(docs, DocType.bill_of_lading, "container_count"),
        origin_port=_get(docs, DocType.bill_of_lading, "origin_port"),
        destination_port=_get(docs, DocType.bill_of_lading, "destination_port"),
        ship_date=_get(docs, DocType.bill_of_lading, "ship_date"),
        arrival_date=_get(docs, DocType.bill_of_lading, "arrival_date"),
        # weights: the packing list wins
        gross_weight_tons=_first(docs, "gross_weight_tons", DocType.packing_list,
                                 DocType.bill_of_lading),
        # dates and numbers of record
        lc_issue_date=_get(docs, DocType.letter_of_credit, "issue_date"),
        insurance_issue_date=_get(docs, DocType.insurance_certificate,
                                  "insurance_issue_date"),
        lc_number=_get(docs, DocType.letter_of_credit, "lc_number"),
        bl_number=_get(docs, DocType.bill_of_lading, "bl_number"),
        contract_reference=_first(docs, "contract_reference",
                                  DocType.sales_contract,
                                  DocType.commercial_invoice),
    )
