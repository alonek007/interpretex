"""World-side models: entities, documents, cases, generation specs.

Every model uses ``extra="forbid"`` — validation is the contract. All dates in
world-side payloads are ISO-8601 strings ("2026-08-10") so that JSON
serialisation is byte-stable; timestamps that need a clock
(``AgentCaseView.received_at``) are timezone-aware UTC datetimes.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import AnomalyKind, CaseClass, DocType

EntityRole = Literal["buyer", "seller", "broker", "vessel_owner", "insurer", "intermediary"]
SanctionsStatus = Literal["not_listed", "match", "near_match", "unknown"]

#: Canonical, ordered names of the eight investigation tools. Part 1's registry
#: exposes exactly these (minus any disabled by feature flags); the names are
#: part of the frozen contract because they appear in AgentCaseView.
DEFAULT_TOOL_NAMES: list[str] = [
    "read_document",
    "check_document_consistency",
    "check_price_benchmark",
    "check_vessel_capacity",
    "check_transit_plausibility",
    "check_historical_trade",
    "check_counterparty_network",
    "check_contract_or_supporting_evidence",
]


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    name: str
    country: str = Field(min_length=2, max_length=2, description="ISO-2 country code")
    role: EntityRole
    incorporated_on: Optional[str] = None
    registry_id: Optional[str] = None
    ultimate_beneficial_owners: list[str]
    sanctions_status: SanctionsStatus
    notes: Optional[str] = None


class Vessel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vessel_name: str
    imo: Optional[str] = None
    dwt_tons: float  # maximum cargo capacity
    vessel_type: str
    max_speed_knots: float
    flag: Optional[str] = None
    owner_entity_id: Optional[str] = None


class Port(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port_code: str  # UN/LOCODE, e.g. SGSIN
    name: str
    country: str = Field(min_length=2, max_length=2)
    lat: float
    lon: float


class TradeDocument(BaseModel):
    """One document in the case file.

    ``fields`` keys use canonical TradeRecord names wherever the concept
    exists there, so cross-document comparison is a dict intersection rather
    than a mapping exercise. ``raw_text`` is what OCR would return. Where the
    two disagree, that disagreement is itself a documentary signal — never
    silently reconcile them.
    """

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    doc_type: DocType
    issuer: str
    issue_date: str
    fields: dict[str, Any]
    raw_text: str
    extraction_confidence: float


class TradeRecord(BaseModel):
    """Canonical normalised view of the trade.

    When documents disagree, hold the LC/invoice value here and surface the
    disagreement as an observation (never reconcile silently).
    """

    model_config = ConfigDict(extra="forbid")

    commodity: str
    commodity_grade: Optional[str] = None
    hs_code: Optional[str] = None
    quantity: float
    unit: str
    unit_price: float
    currency: str
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
    """Ground truth. Never shown to the agent."""

    model_config = ConfigDict(extra="forbid")

    case_class: CaseClass
    injected_anomalies: list[AnomalyKind]
    expected_verdict: str
    benign_explanation: Optional[str] = None
    evasion_notes: Optional[str] = None
    generator_seed: Optional[int] = None


class AgentCaseView(BaseModel):
    """The case as the agent sees it.

    This type has NO ``label`` field, by design: ground-truth leakage is a
    type error rather than a code-review question. Part 2's entry point
    accepts AgentCaseView.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    received_at: datetime
    bank_reference: Optional[str] = None
    applicant_note: Optional[str] = None
    documents: list[TradeDocument]
    record: TradeRecord
    available_tool_names: list[str]


class TradeCase(BaseModel):
    """Everything in AgentCaseView plus world-side context and the label."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    received_at: datetime
    bank_reference: Optional[str] = None
    applicant_note: Optional[str] = None
    documents: list[TradeDocument]
    record: TradeRecord
    available_tool_names: list[str]
    title: str
    entities: list[Entity]
    vessel: Optional[Vessel] = None
    label: Optional[CaseLabel] = None

    def to_agent_view(self) -> AgentCaseView:
        """Strip the label and world-side context. Call at every agent boundary."""
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
    """Case-selector row."""

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
    is_adversarial: bool


class CaseSpec(BaseModel):
    """Generation recipe. ``generate_case(spec)`` is deterministic on (spec, seed)."""

    model_config = ConfigDict(extra="forbid")

    case_class: CaseClass
    commodity: Optional[str] = None
    quantity: Optional[float] = None
    exporter_id: Optional[str] = None
    importer_id: Optional[str] = None
    anomalies: list[AnomalyKind]
    anomaly_magnitudes: dict[str, float]
    benign_explanation: Optional[str] = None
    plant_supporting_contract: bool
    seed: int


class AttackSpec(BaseModel):
    """Recipe for the attacker agent: thresholds it must stay under."""

    model_config = ConfigDict(extra="forbid")

    known_thresholds: dict[str, float]
    max_dimensions: int
    target_stealth: float
    seed: int
