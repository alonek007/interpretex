"""The four demo blueprints, pinned to the exact figures in the project brief.

The three demo cases are built by ``build_case_from_blueprint``: every value is
explicit (CaseSpec cannot carry ports/vessel/dates by contract), so the cases
are stable by construction and byte-reproducible from their seeds. The generic
``generate_case(spec)`` path shares the same anomaly-injection and document
rendering pipeline.

Case 1 ``case_clean_001``  — coffee, RELEASE expected, clean in every dimension.
Case 2 ``case_explainable_002`` — aluminium −18% under benchmark, but a genuine
  three-year offtake contract with volume tiers is IN the file and the
  importer's own history sits at $1,940–$2,010/t. HOLD expected, never ESCALATE.
Case 3 ``case_suspicious_003`` — copper: under-invoicing −38.2%, capacity 122%,
  one-day transit, insurance 8 days after shipment, packing list describes
  Copper Scrap, recurring broker. ESCALATE expected on 4+ dimensions.
Case 4 ``case_adv_004`` — the attacker's deterministic fallback: every single
  signal low or medium (zinc −17%, 96% capacity, fast-edge transit, same-day
  insurance, one fresh intermediary shared with one prior case).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .generator import build_case_from_blueprint

SEED_1, SEED_2, SEED_3, SEED_ADV = 1001, 2002, 3003, 4004

DEMO_CASE_1 = {
    "case_id": "case_clean_001",
    "case_class": "clean",
    "seed": SEED_1,
    "commodity_key": "coffee_arabica",
    "exporter_id": "ENT-006",
    "importer_id": "ENT-007",
    "broker_id": "ENT-008",
    "quantity": 480.0,
    "unit_price": 4420.0,  # 2026-08 benchmark 4500 -> -1.8%, inside the band
    "grade": "Washed arabica, screen 17/18",
    "origin_port": "BRSSZ",
    "destination_port": "NLRTM",
    "vessel_name": "MV Pacific Dawn",  # dwt 2500; util ~20%
    "ship_date": "2026-07-02",
    "arrival_date": "2026-07-19",  # 17 days, inside the expected band
    "insurance_issue_date": "2026-07-01",  # before shipment
    "lc_issue_date": "2026-06-26",
    "incoterm": "CIF",
    "title": "Coffee arabica shipment — Santos → Rotterdam (LC-2026-2260)",
    "received_at": datetime(2026, 6, 28, 9, 0, tzinfo=timezone.utc),
    "bank_reference": "TRF/LC-2026-2260",
    "applicant_note": ("Documentary presentation received under the above LC; "
                       "please examine documents and advise."),
    "doc_ids": {
        "letter_of_credit": "LC-2026-2260",
        "commercial_invoice": "INV-2026-2261",
        "bill_of_lading": "BL-2262",
        "packing_list": "PL-2263",
        "certificate_of_origin": "COO-2264",
        "insurance_certificate": "INS-2265",
    },
    "anomalies": [],
    "anomaly_magnitudes": {},
}

DEMO_CASE_2 = {
    "case_id": "case_explainable_002",
    "case_class": "suspicious_but_legitimate",
    "seed": SEED_2,
    "commodity_key": "aluminium_ingot",
    "exporter_id": "ENT-005",
    "importer_id": "ENT-001",
    "broker_id": "ENT-008",
    "quantity": 1600.0,
    "unit_price": 1968.0,  # 2026-08 benchmark 2400 -> exactly -18.0%
    "grade": "P1020A standard",
    "origin_port": "AEJEA",
    "destination_port": "INNSA",
    "vessel_name": "MV Gulf Trader",  # dwt 2800; util ~58%
    "ship_date": "2026-08-03",
    "arrival_date": "2026-08-09",  # 6 days, inside the 4-7 day band
    "insurance_issue_date": "2026-08-01",  # before shipment
    "lc_issue_date": "2026-07-28",
    "incoterm": "CFR",
    "title": "Aluminium ingots shipment — Jebel Ali → Nhava Sheva (LC-2026-2270)",
    "received_at": datetime(2026, 7, 31, 9, 0, tzinfo=timezone.utc),
    "bank_reference": "TRF/LC-2026-2270",
    "applicant_note": ("Long-standing supply relationship; presentation received "
                       "under the above LC for examination."),
    "doc_ids": {
        "letter_of_credit": "LC-2026-2270",
        "commercial_invoice": "INV-2026-2271",
        "bill_of_lading": "BL-2272",
        "packing_list": "PL-2273",
        "certificate_of_origin": "COO-2274",
        "insurance_certificate": "INS-2275",
        "sales_contract": "SC-2024-2276",
    },
    "contract_claims": ["long_term_offtake", "bulk_discount"],
    "anomalies": ["under_invoicing"],
    "anomaly_magnitudes": {"under_invoicing": 0.18},
    "benign_explanation": ("Tiered pricing under a three-year offtake agreement; "
                           "consistent with the importer's own six-trade history."),
}

DEMO_CASE_3 = {
    "case_id": "case_suspicious_003",
    "case_class": "illicit",
    "seed": SEED_3,
    "commodity_key": "copper_cathode",
    "exporter_id": "ENT-002",
    "importer_id": "ENT-004",
    "broker_id": "ENT-003",  # reused across three previously escalated trades
    "quantity": 2200.0,
    "unit_price": 5500.0,  # 2026-08 benchmark 8900 -> -38.2%
    "grade": "LME Grade A standard",
    "origin_port": "SGSIN",
    "destination_port": "INNSA",
    "vessel_name": "MV Ocean Star",  # dwt 1800; cargo 2200 t -> 122% utilisation
    "ship_date": "2026-08-10",
    "arrival_date": "2026-08-11",  # one day against a 5-8 day band
    "insurance_issue_date": "2026-08-18",  # eight days AFTER shipment
    "lc_issue_date": "2026-08-05",
    "incoterm": "FOB",
    "title": "Copper cathodes shipment — Singapore → Nhava Sheva (LC-2026-2280)",
    "received_at": datetime(2026, 8, 6, 9, 0, tzinfo=timezone.utc),
    "bank_reference": "TRF/LC-2026-2280",
    "applicant_note": ("Urgent request from the applicant to release documents at "
                       "earliest against the above LC."),
    "doc_ids": {
        "letter_of_credit": "LC-2026-2280",
        "commercial_invoice": "INV-2026-2281",
        "bill_of_lading": "BL-2282",
        "packing_list": "PL-2283",
        "certificate_of_origin": "COO-2284",
        "insurance_certificate": "INS-2285",
    },
    "anomalies": [
        "under_invoicing",
        "capacity_exceeded",
        "impossible_transit",
        "insurance_after_shipment",
        "description_drift",
        "intermediary_reuse",
    ],
    "anomaly_magnitudes": {
        "under_invoicing": 0.382,
        "capacity_exceeded": 0.222,
        "impossible_transit": 1,
        "insurance_after_shipment": 8,
    },
}

#: deterministic fallback for the attacker (FEATURE_ATTACKER): every individual
#: signal lands low or medium.
ATTACK_FALLBACK = {
    "case_id": "case_adv_004",
    "case_class": "adversarial",
    "seed": SEED_ADV,
    "commodity_key": "zinc",
    "exporter_id": "ENT-013",
    "importer_id": "ENT-019",
    "broker_id": "ENT-018",  # fresh intermediary, one prior held case (HT-044)
    "quantity": 2635.0,      # gross 2687.7 t on 2800 dwt -> 96.0% utilisation
    "unit_price": 2750.0,    # benchmark; under_invoicing 0.17 sets 2282.50 (-17.0%)
    "grade": "SHG Zn 99.995",
    "origin_port": "AEJEA",
    "destination_port": "INNSA",
    "vessel_name": "MV Gulf Trader",
    "ship_date": "2026-08-04",
    "arrival_date": "2026-08-08",       # 4 days = fast edge of the 4-7 day band
    "insurance_issue_date": "2026-08-04",  # same-day insurance
    "lc_issue_date": "2026-07-30",
    "incoterm": "CFR",
    "title": "Zinc ingots shipment — Jebel Ali → Nhava Sheva (LC-2026-2290)",
    "received_at": datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
    "bank_reference": "TRF/LC-2026-2290",
    "applicant_note": ("Presentation received under the above LC for examination; "
                       "applicant requests prompt processing."),
    "doc_ids": {
        "letter_of_credit": "LC-2026-2290",
        "commercial_invoice": "INV-2026-2291",
        "bill_of_lading": "BL-2292",
        "packing_list": "PL-2293",
        "certificate_of_origin": "COO-2294",
        "insurance_certificate": "INS-2295",
    },
    "anomalies": ["under_invoicing"],
    "anomaly_magnitudes": {"under_invoicing": 0.17},
    "evasion_notes": (
        "Declared price held 17.0% below benchmark (under the 30% threshold); "
        "capacity utilisation kept at 96.0% (under the 1.00 limit); transit at "
        "the fast edge of the plausible band but not impossible; same-day "
        "insurance (lag 0 days, under the 3-day threshold); one fresh "
        "intermediary shared with a single prior held case. Every individual "
        "signal is low or medium; only their correlation is informative."),
}

DEMO_BLUEPRINTS = [DEMO_CASE_1, DEMO_CASE_2, DEMO_CASE_3]
DEMO_CASE_IDS = [bp["case_id"] for bp in DEMO_BLUEPRINTS]


def build_demo_cases() -> list:
    return [build_case_from_blueprint(bp) for bp in DEMO_BLUEPRINTS]


def build_attacker_fallback():
    return build_case_from_blueprint(ATTACK_FALLBACK)
