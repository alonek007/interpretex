"""Adversarial case generator (Part 3 stub for Part 1 attacker agent).

Deterministic fallback used when no LLM is supplied. Crafts an evasive case
that sits inside every individual threshold (price < 30%, capacity < 100%,
insurance lag <= 3 days) but is meant to be caught by correlation, not by any
single check. This is what the attacker panel demonstrates.
"""
from __future__ import annotations

from typing import Any

from interpretex_contracts import AttackSpec, CaseLabel, TradeCase


def attack(spec: AttackSpec, llm: Any = None) -> TradeCase:
    th = dict(getattr(spec, "known_thresholds", {}) or {})
    seed = spec.seed or 1

    return TradeCase(
        case_id=f"case_adv_{seed:03d}",
        title="Zinc ingots — Penang to Mundra (evasive)",
        documents=[],
        record={
            "commodity": "Zinc ingots",
            "quantity": 1900,
            "unit": "t",
            "unit_price": 2450,  # vs 2950 benchmark => -17%
            "currency": "USD",
            "total_value": 1900 * 2450,
            "incoterm": "CIF",
            "exporter_id": "E-SAHABAT-ZN",
            "importer_id": "E-GUJARAT-ZN",
            "broker_id": "E-NUSANTARA-BR",
            "insurer_id": "E-SINDO-MARINE",
            "vessel_name": "MV Sunda Pearl",
            "imo": "9377012",
            "container_count": 76,
            "gross_weight_tons": 1903.4,
            "origin_port": "MYPEN",
            "destination_port": "INMUN",
            "ship_date": "2026-09-05",
            "arrival_date": "2026-09-10",  # 5 days, fast but plausible edge
            "insurance_issue_date": "2026-09-05",  # same-day
        },
        entities=[
            {"entity_id": "E-SAHABAT-ZN", "name": "Sahabat Zinc Sdn Bhd", "country": "MY", "role": "seller",
             "sanctions_status": "not_listed", "ultimate_beneficial_owners": ["R. Iskandar"]},
            {"entity_id": "E-GUJARAT-ZN", "name": "Gujarat Zinc Traders Pvt Ltd", "country": "IN", "role": "buyer",
             "sanctions_status": "not_listed", "ultimate_beneficial_owners": ["M. Patel"]},
            {"entity_id": "E-NUSANTARA-BR", "name": "Nusantara Bridge Brokers", "country": "ID", "role": "broker",
             "sanctions_status": "not_listed", "ultimate_beneficial_owners": ["B. Santoso"]},
            {"entity_id": "E-SINDO-MARINE", "name": "Sindo Marine Assurance", "country": "SG", "role": "insurer",
             "sanctions_status": "not_listed", "ultimate_beneficial_owners": ["Sindo Holdings"]},
        ],
        vessel={"vessel_name": "MV Sunda Pearl", "imo": "9377012", "dwt_tons": 1980, "max_speed_knots": 14.0,
                "flag": "SG", "owner_entity_id": "E-SINDO-MARINE"},
        available_tool_names=[
            "read_document", "check_document_consistency", "check_price_benchmark",
            "check_vessel_capacity", "check_transit_plausibility", "check_historical_trade",
            "check_counterparty_network", "check_contract_or_supporting_evidence",
        ],
        label=CaseLabel(
            case_class="adversarial",
            injected_anomalies=["under_invoicing", "capacity_exceeded", "intermediary_reuse"],
            expected_verdict="escalate",
            evasion_notes=(
                "Every individual signal is below threshold: price -17% (<30%), "
                "capacity 96% (<100%), insurance same-day (<=3d), transit at the fast edge "
                "but not impossible, one fresh intermediary shared with a single prior case. "
                "The investigator is expected to escalate on correlation (economic + behavioural + network), "
                "not on any single check."
            ),
            generator_seed=seed,
        ),
    )
