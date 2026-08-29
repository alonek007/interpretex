"""World-side models (contract 1.0.0)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import AnomalyKind, CaseClass, DocType, Verdict


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str
    name: str
    country: str
    role: Literal["buyer", "seller", "broker", "vessel_owner", "insurer", "intermediary"]
    incorporated_on: Optional[str] = None
    registry_id: Optional[str] = None
    ultimate_beneficial_owners: list[str] = Field(default_factory=list)
    sanctions_status: Literal["not_listed", "match", "near_match", "unknown"] = "not_listed"
    notes: Optional[str] = None


class Vessel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vessel_name: str
    imo: Optional[str] = None
    dwt_tons: float
    vessel_type: str = "bulk_carrier"
    max_speed_knots: float = 14.0
    flag: Optional[str] = None
    owner_entity_id: Optional[str] = None


class Port(BaseModel):
    model_config = ConfigDict(extra="forbid")
    port_code: str
    name: str
    country: str
    lat: float
    lon: float


class TradeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_id: str
    doc_type: DocType
    issuer: str
    issue_date: str
    fields: dict[str, Any] = Field(default_factory=dict)
    raw_text: str = ""
    extraction_confidence: float = 0.95


class TradeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commodity: str
    commodity_grade: Optional[str] = None
    hs_code: Optional[str] = None
    quantity: float
    unit: str
    unit_price: float
    currency: str = "USD"
    total_value: float
    incoterm: Optional[str] = None
    exporter_id: str
    importer_id: str
    broker_id: Optional[str] = None
    insurer_id: Optional[str] = None
    vessel_name: Optional[str] = None
    imo: Optional[str] = None
    container_count: Optional[int] = None
    gross_weight_tons: Optional[float] = None
    origin_port: Optional[str] = None
    destination_port: Optional[str] = None
    ship_date: Optional[str] = None
    arrival_date: Optional[str] = None
    lc_issue_date: Optional[str] = None
    insurance_issue_date: Optional[str] = None
    lc_number: Optional[str] = None
    bl_number: Optional[str] = None
    contract_reference: Optional[str] = None


class CaseLabel(BaseModel):
    """Ground truth. Never serialise to the agent or the browser before a completed run."""
    model_config = ConfigDict(extra="forbid")
    case_class: CaseClass
    injected_anomalies: list[AnomalyKind] = Field(default_factory=list)
    expected_verdict: Verdict
    benign_explanation: Optional[str] = None
    evasion_notes: Optional[str] = None
    generator_seed: Optional[int] = None


class AgentCaseView(BaseModel):
    """Label-stripped view handed to the investigator."""
    model_config = ConfigDict(extra="forbid")
    case_id: str
    received_at: datetime = Field(default_factory=_now)
    bank_reference: Optional[str] = None
    applicant_note: Optional[str] = None
    documents: list[TradeDocument] = Field(default_factory=list)
    record: TradeRecord
    available_tool_names: list[str] = Field(default_factory=list)


class TradeCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    title: str
    received_at: datetime = Field(default_factory=_now)
    bank_reference: Optional[str] = None
    applicant_note: Optional[str] = None
    documents: list[TradeDocument] = Field(default_factory=list)
    record: TradeRecord
    entities: list[Entity] = Field(default_factory=list)
    vessel: Optional[Vessel] = None
    available_tool_names: list[str] = Field(default_factory=list)
    label: Optional[CaseLabel] = None

    def to_agent_view(self) -> AgentCaseView:
        return AgentCaseView(
            case_id=self.case_id,
            received_at=self.received_at,
            bank_reference=self.bank_reference,
            applicant_note=self.applicant_note,
            documents=self.documents,
            record=self.record,
            available_tool_names=self.available_tool_names,
        )


class CaseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    title: str
    commodity: str
    quantity: float
    unit: str
    total_value: float
    currency: str
    exporter_name: str
    importer_name: str
    origin_port: Optional[str] = None
    destination_port: Optional[str] = None
    document_count: int
    received_at: datetime = Field(default_factory=_now)
    is_adversarial: bool = False


class CaseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_class: CaseClass
    commodity: Optional[str] = None
    quantity: Optional[float] = None
    exporter_id: Optional[str] = None
    importer_id: Optional[str] = None
    anomalies: list[AnomalyKind] = Field(default_factory=list)
    anomaly_magnitudes: dict[str, float] = Field(default_factory=dict)
    benign_explanation: Optional[str] = None
    plant_supporting_contract: bool = False
    seed: int = 0


class AttackSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    known_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "price_deviation_pct": 0.30,
            "capacity_utilisation": 1.00,
            "insurance_lag_days": 3,
        }
    )
    max_dimensions: int = 2
    target_stealth: float = 0.8
    seed: int = 0
