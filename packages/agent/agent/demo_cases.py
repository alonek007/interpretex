"""The three demo cases with ground-truth labels, exact numbers from master
plan section 13. LABELS ARE GROUND TRUTH: only eval.py and the tests may read
them. The agent always receives `to_agent_view()` (label-stripped).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from interpretex_contracts import (
    AgentCaseView,
    AnomalyKind,
    CaseClass,
    CaseLabel,
    TradeCase,
    TradeDocument,
    TradeRecord,
)

from .miniregistry import TOOL_SPECS, MiniWorld


def _doc(doc_id: str, doc_type: str, issuer: str, issue_date: str, fields: dict, raw: str) -> TradeDocument:
    from interpretex_contracts import DocType

    return TradeDocument(
        doc_id=doc_id, doc_type=DocType(doc_type), issuer=issuer, issue_date=date.fromisoformat(issue_date),
        fields=fields, raw_text=raw, extraction_confidence=0.98,
    )


def _record(**kw) -> TradeRecord:
    base = dict(
        commodity="Coffee", quantity=480.0, unit="t", unit_price=4420.0, currency="USD",
        total_value=4420.0 * 480.0, exporter_id="ENT-EXP-001", importer_id="ENT-IMP-001",
    )
    base.update(kw)
    return TradeRecord(**base)


# ------------------------------------------------------------------- case 1

def case_clean_001() -> TradeCase:
    record = _record(
        commodity_grade="Arabica grade A", hs_code="0901.11", incoterm="CIF",
        vessel_name="MV Pacific Dawn", imo="9123456", container_count=20,
        gross_weight_tons=480.0, origin_port="BRSSZ", destination_port="NLRTM",
        ship_date=date(2026, 7, 2), arrival_date=date(2026, 7, 19),
        lc_issue_date=date(2026, 6, 20), insurance_issue_date=date(2026, 7, 1),
        lc_number="LC-2026-0441", bl_number="BL-2026-0441", contract_reference="CT-2026-009",
    )
    docs = [
        _doc("LC-2026-0441", "letter_of_credit", "Bank of Rotterdam", "2026-06-20",
             {"applicant": record.importer_id, "beneficiary": record.exporter_id,
              "total_value": record.total_value, "currency": "USD"},
             "Letter of credit 4441 covering 480 t coffee, CIF Rotterdam."),
        _doc("INV-2026-0441", "commercial_invoice", record.exporter_id, "2026-07-01",
             {"commodity": "Coffee", "quantity": 480, "unit": "t", "unit_price": 4420.0,
              "total_value": 2121600.0, "currency": "USD"},
             "Commercial invoice for 480 t Arabica grade A at USD 4,420/t."),
        _doc("BL-2026-0441", "bill_of_lading", "OceanLines SA", "2026-07-02",
             {"vessel_name": "MV Pacific Dawn", "gross_weight_tons": 480, "ship_date": "2026-07-02",
              "arrival_date": "2026-07-19", "origin_port": "BRSSZ", "destination_port": "NLRTM"},
             "Bill of lading: shipped on board MV Pacific Dawn 2 July 2026."),
        _doc("PL-2026-0441", "packing_list", record.exporter_id, "2026-07-01",
             {"commodity": "Coffee", "quantity": 480, "unit": "t", "container_count": 20},
             "Packing list: 480 t coffee in 20 containers."),
        _doc("COO-2026-0441", "certificate_of_origin", "CCIA Santos", "2026-06-30",
             {"commodity": "Coffee", "origin": "BR"},
             "Certificate of origin: Brazilian coffee."),
        _doc("INS-2026-0441", "insurance_certificate", "Meridian Marine Ins.", "2026-07-01",
             {"insurance_issue_date": "2026-07-01", "insured_value": 2121600.0},
             "Marine insurance certificate issued 1 July 2026, before shipment."),
    ]
    return TradeCase(
        case_id="case_clean_001",
        received_at=datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc),
        title="Clean coffee shipment Santos to Rotterdam",
        bank_reference="TF-2026-0441",
        applicant_note="Repeat customer; documents presented under LC-2026-0441.",
        documents=docs, record=record,
        available_tool_names=[s.name for s in TOOL_SPECS],
        label=CaseLabel(
            case_class=CaseClass.clean, injected_anomalies=[AnomalyKind.none],
            expected_verdict="release",
            benign_explanation="Everything consistent; price within 2% of benchmark.",
        ),
    )


WORLD_CLEAN = MiniWorld(
    benchmark_price=4500.0, benchmark_month="2026-07",
    transit_band_days=(15, 19), vessel_dwt=2500.0,
    history_prices=[4400.0, 4450.0, 4500.0, 4550.0, 4480.0, 4520.0],
    network_shared_escalated=0, contract_found=False,
)


# ------------------------------------------------------------------- case 2

def case_explainable_002() -> TradeCase:
    record = _record(
        commodity="Aluminium ingots", commodity_grade="P1020A", hs_code="7601.10",
        quantity=1600.0, unit_price=1968.0, total_value=1968.0 * 1600.0,
        exporter_id="ENT-EXP-002", importer_id="ENT-IMP-002",
        incoterm="CIF", vessel_name="MV Gulf Trader", imo="9234567", container_count=64,
        gross_weight_tons=1600.0, origin_port="AEJEA", destination_port="INNSA",
        ship_date=date(2026, 8, 3), arrival_date=date(2026, 8, 9),
        lc_issue_date=date(2026, 7, 25), insurance_issue_date=date(2026, 8, 1),
        lc_number="LC-2026-0771", bl_number="BL-2026-0771", contract_reference="CT-2023-115",
    )
    docs = [
        _doc("LC-2026-0771", "letter_of_credit", "Gulf Commercial Bank", "2026-07-25",
             {"applicant": record.importer_id, "beneficiary": record.exporter_id,
              "total_value": record.total_value},
             "Letter of credit 0771 covering 1,600 t aluminium ingots CIF Nhava Sheva."),
        _doc("INV-2026-0771", "commercial_invoice", record.exporter_id, "2026-08-02",
             {"commodity": "Aluminium ingots", "quantity": 1600, "unit": "t",
              "unit_price": 1968.0, "total_value": 3148800.0, "currency": "USD"},
             "Commercial invoice: 1,600 t P1020A aluminium ingots at USD 1,968/t."),
        _doc("BL-2026-0771", "bill_of_lading", "GulfBulk Shipping", "2026-08-03",
             {"vessel_name": "MV Gulf Trader", "gross_weight_tons": 1600,
              "ship_date": "2026-08-03", "arrival_date": "2026-08-09"},
             "Bill of lading: shipped on board MV Gulf Trader 3 August 2026."),
        _doc("PL-2026-0771", "packing_list", record.exporter_id, "2026-08-02",
             {"commodity": "Aluminium ingots", "quantity": 1600, "unit": "t", "container_count": 64},
             "Packing list: 1,600 t aluminium ingots in 64 containers."),
        _doc("COO-2026-0771", "certificate_of_origin", "Abu Dhabi Chamber", "2026-07-30",
             {"commodity": "Aluminium ingots", "origin": "AE"},
             "Certificate of origin: UAE aluminium."),
        _doc("INS-2026-0771", "insurance_certificate", "Gulf Marine Underwriters", "2026-08-01",
             {"insurance_issue_date": "2026-08-01", "insured_value": 3148800.0},
             "Marine insurance certificate issued 1 August 2026."),
        _doc("SC-2023-115", "sales_contract", record.exporter_id, "2023-10-05",
             {"contract_reference": "CT-2023-115", "pricing_schedule": "volume tiers: 1,600 t/yr at USD 1,950-2,010/t for three years",
              "commodity": "Aluminium ingots"},
             "Three-year offtake contract with volume-tiered pricing of USD 1,950-2,010/t."),
    ]
    return TradeCase(
        case_id="case_explainable_002",
        received_at=datetime(2026, 8, 11, 9, 0, tzinfo=timezone.utc),
        title="Aluminium ingots with three-year offtake contract",
        bank_reference="TF-2026-0771",
        applicant_note="Long-standing customer; pricing per 2023 offtake agreement.",
        documents=docs, record=record,
        available_tool_names=[s.name for s in TOOL_SPECS],
        label=CaseLabel(
            case_class=CaseClass.suspicious_but_legitimate,
            injected_anomalies=[AnomalyKind.historical_deviation],
            expected_verdict="hold",
            benign_explanation="Genuine three-year offtake contract with volume tiers; own history "
                               "shows 1,940-2,010/t across six prior trades.",
        ),
    )


WORLD_EXPLAINABLE = MiniWorld(
    benchmark_price=2400.0, benchmark_month="2026-08",
    transit_band_days=(4, 7), vessel_dwt=2800.0,
    history_prices=[1950.0, 1960.0, 1975.0, 1985.0, 2000.0, 2010.0],
    network_shared_escalated=0,
    contract_found=True, contract_claim="long_term_offtake",
    contract_clause="volume tiers: 1,600 t/yr at USD 1,950-2,010/t for three years (2023 offtake)",
)


# ------------------------------------------------------------------- case 3

def case_suspicious_003() -> TradeCase:
    record = _record(
        commodity="Copper cathodes", commodity_grade="LME grade A", hs_code="7403.11",
        quantity=2200.0, unit_price=5500.0, total_value=5500.0 * 2200.0,
        exporter_id="ENT-EXP-003", importer_id="ENT-IMP-003", broker_id="BROKER-7",
        incoterm="FOB", vessel_name="MV Ocean Star", imo="9345678", container_count=88,
        gross_weight_tons=2200.0, origin_port="SGSIN", destination_port="INNSA",
        ship_date=date(2026, 8, 10), arrival_date=date(2026, 8, 11),
        lc_issue_date=date(2026, 8, 5), insurance_issue_date=date(2026, 8, 18),
        lc_number="LC-2026-0912", bl_number="BL-2026-0912",
    )
    docs = [
        _doc("LC-2026-0912", "letter_of_credit", "Straits Trade Bank", "2026-08-05",
             {"applicant": record.importer_id, "beneficiary": record.exporter_id,
              "total_value": record.total_value},
             "Letter of credit 0912 covering 2,200 t copper cathodes FOB Singapore."),
        _doc("INV-2026-0912", "commercial_invoice", record.exporter_id, "2026-08-09",
             {"commodity": "Copper cathodes", "quantity": 2200, "unit": "t",
              "unit_price": 5500.0, "total_value": 12100000.0, "currency": "USD"},
             "Commercial invoice: 2,200 t LME grade A copper cathodes at USD 5,500/t."),
        _doc("BL-2026-0912", "bill_of_lading", "StarMarine Lines", "2026-08-10",
             {"vessel_name": "MV Ocean Star", "gross_weight_tons": 2200,
              "ship_date": "2026-08-10", "arrival_date": "2026-08-11"},
             "Bill of lading: shipped on board MV Ocean Star 10 August 2026."),
        _doc("PL-2026-0912", "packing_list", record.exporter_id, "2026-08-09",
             {"commodity": "Copper Scrap", "quantity": 2200, "unit": "t", "container_count": 88},
             "Packing list: 2,200 t Copper Scrap in 88 containers."),
        _doc("COO-2026-0912", "certificate_of_origin", "Singapore Customs", "2026-08-08",
             {"commodity": "Copper cathodes", "origin": "SG"},
             "Certificate of origin: copper cathodes, Singapore."),
        _doc("INS-2026-0912", "insurance_certificate", "Andaman Marine Ins.", "2026-08-18",
             {"insurance_issue_date": "2026-08-18", "insured_value": 12100000.0},
             "Marine insurance certificate issued 18 August 2026 — after shipment."),
    ]
    return TradeCase(
        case_id="case_suspicious_003",
        received_at=datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc),
        title="Copper cathodes below market on a vessel too small for the cargo",
        bank_reference="TF-2026-0912",
        applicant_note="Urgent release requested; funds needed this week.",
        documents=docs, record=record,
        available_tool_names=[s.name for s in TOOL_SPECS],
        label=CaseLabel(
            case_class=CaseClass.illicit,
            injected_anomalies=[
                AnomalyKind.under_invoicing, AnomalyKind.capacity_exceeded,
                AnomalyKind.impossible_transit, AnomalyKind.insurance_after_shipment,
                AnomalyKind.description_drift, AnomalyKind.historical_deviation,
                AnomalyKind.intermediary_reuse,
            ],
            expected_verdict="escalate",
        ),
    )


WORLD_SUSPICIOUS = MiniWorld(
    benchmark_price=8900.0, benchmark_month="2026-08",
    transit_band_days=(5, 8), vessel_dwt=1800.0,
    history_prices=[8600.0, 8700.0, 8800.0, 8900.0, 9000.0, 9100.0],
    network_shared_escalated=3, contract_found=False,
    description_drift="Copper Scrap",
    insurance_lag_days=8,
)


# ------------------------------------------------------------------ registry

ALL_CASES = {
    "case_clean_001": (case_clean_001, WORLD_CLEAN),
    "case_explainable_002": (case_explainable_002, WORLD_EXPLAINABLE),
    "case_suspicious_003": (case_suspicious_003, WORLD_SUSPICIOUS),
}


def build(case_id: str) -> tuple[AgentCaseView, MiniWorld, TradeCase]:
    builder, world = ALL_CASES[case_id]
    trade_case = builder()
    return trade_case.to_agent_view(), world, trade_case
