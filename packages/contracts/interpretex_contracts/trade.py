"""World-side models (frozen, section 8.2)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import AnomalyKind, CaseClass, DocType


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    name: str
    country: str  # ISO-2
    role: Literal["buyer", "seller", "broker", "vessel_owner", "insurer", "intermediary"]
    incorporated_on: Optional[date] = None
    registry_id: Optional[str] = None
    ultimate_beneficial_owners: list[str] = Field(default_factory=list)
    sanctions_status: Literal["clear", "listed", "near_match", "unknown"] = "unknown"
    notes: Optional[str] = None


class Vessel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vessel_name: str
    imo: Optional[str] = None
    dwt_tons: float  # maximum cargo capacity
    typical_speed_knots: Optional[float] = None
    flag: Optional[str] = None


class Port(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port_code: str  # UN/LOCODE, e.g. SGSIN
    name: str
    country: str
    lat: float
    lon: float


class TradeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    doc_type: DocType
    issuer: str
    issue_date: Optional[date] = None
    fields: dict[str, Any] = Field(default_factory=dict)
    raw_text: str = ""
    extraction_confidence: float = 1.0


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
    ship_date: Optional[date] = None
    arrival_date: Optional[date] = None
    lc_issue_date: Optional[date] = None
    insurance_issue_date: Optional[date] = None
    lc_number: Optional[str] = None
    bl_number: Optional[str] = None
    contract_reference: Optional[str] = None


class CaseLabel(BaseModel):
    """Ground truth. Never shown to the agent."""

    model_config = ConfigDict(extra="forbid")

    case_class: CaseClass
    injected_anomalies: list[AnomalyKind] = Field(default_factory=list)
    expected_verdict: str  # "release" | "hold" | "escalate"
    benign_explanation: Optional[str] = None
    evasion_notes: Optional[str] = None
    generator_seed: Optional[int] = None


class AgentCaseView(BaseModel):
    """The agent's view of a case. Has NO label field, by design."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    received_at: datetime
    bank_reference: Optional[str] = None
    applicant_note: Optional[str] = None
    documents: list[TradeDocument] = Field(default_factory=list)
    record: TradeRecord
    available_tool_names: list[str] = Field(default_factory=list)


class TradeCase(BaseModel):
    """Everything in AgentCaseView plus world context and ground truth."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    received_at: datetime
    title: str
    bank_reference: Optional[str] = None
    applicant_note: Optional[str] = None
    documents: list[TradeDocument] = Field(default_factory=list)
    record: TradeRecord
    available_tool_names: list[str] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    vessel: Optional[Vessel] = None
    label: Optional[CaseLabel] = None

    def to_agent_view(self) -> AgentCaseView:
        """Call at every agent boundary — strips the label."""
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
    received_at: datetime
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

    known_thresholds: dict[str, float] = Field(default_factory=dict)
    max_dimensions: int = 2
    target_stealth: float = 0.8
    seed: int = 0
