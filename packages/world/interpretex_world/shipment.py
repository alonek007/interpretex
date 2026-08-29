"""The underlying shipment — the single source of truth the documents render.

Anomaly injectors mutate a Shipment and documents are re-rendered afterwards,
so every anomaly is visible to every tool that should see it (never just one
document's text).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Shipment:
    # identity
    case_id: str
    title: str
    received_at: datetime
    bank_reference: str
    applicant_note: str
    # parties
    exporter_id: str
    importer_id: str
    broker_id: str | None
    insurer_id: str
    # goods
    commodity_key: str
    commodity_display: str
    commodity_grade: str
    hs_code: str
    description: str
    packing_description: str
    quantity: float
    unit: str
    unit_price: float
    currency: str
    total_value: float
    incoterm: str
    country_of_origin: str
    # logistics
    vessel_name: str
    imo: str
    origin_port: str
    destination_port: str
    bl_destination_port: str
    coo_hs_code: str
    packing_quantity: float
    # dates (ISO strings)
    ship_date: str
    arrival_date: str
    lc_issue_date: str
    insurance_issue_date: str
    # references
    lc_number: str
    bl_number: str
    contract_reference: str | None
    contract_claims: list[str] = field(default_factory=list)
    inspect_before_shipment: bool = False
    # doc id bases (per-case, deterministic)
    doc_ids: dict[str, str] = field(default_factory=dict)
    # derived (set by _derive_weights_and_counts)
    container_count: int = 0
    net_weight_tons: float = 0.0
    gross_weight_tons: float = 0.0
    package_count: int = 0
