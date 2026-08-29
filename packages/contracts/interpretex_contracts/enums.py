"""Interpretex shared contracts — closed vocabularies (frozen, section 8.1)."""
from __future__ import annotations

from enum import Enum

CONTRACT_VERSION = "1.0.0"


class DocType(str, Enum):
    letter_of_credit = "letter_of_credit"
    commercial_invoice = "commercial_invoice"
    bill_of_lading = "bill_of_lading"
    packing_list = "packing_list"
    certificate_of_origin = "certificate_of_origin"
    insurance_certificate = "insurance_certificate"
    inspection_certificate = "inspection_certificate"
    sales_contract = "sales_contract"


class Dimension(str, Enum):
    economic = "economic"
    physical = "physical"
    temporal = "temporal"
    documentary = "documentary"
    behavioural = "behavioural"
    network = "network"


class Severity(str, Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


class Stance(str, Enum):
    supports_suspicion = "supports_suspicion"
    refutes_suspicion = "refutes_suspicion"
    neutral = "neutral"


class HypothesisKind(str, Enum):
    benign = "benign"
    suspicious = "suspicious"


class HypothesisStatus(str, Enum):
    open = "open"
    supported = "supported"
    weakened = "weakened"
    refuted = "refuted"
    untestable = "untestable"


class Verdict(str, Enum):
    release = "release"
    hold = "hold"
    escalate = "escalate"


class CaseClass(str, Enum):
    clean = "clean"
    suspicious_but_legitimate = "suspicious_but_legitimate"
    illicit = "illicit"
    adversarial = "adversarial"


class AnomalyKind(str, Enum):
    under_invoicing = "under_invoicing"
    over_invoicing = "over_invoicing"
    capacity_exceeded = "capacity_exceeded"
    impossible_transit = "impossible_transit"
    insurance_after_shipment = "insurance_after_shipment"
    description_drift = "description_drift"
    quantity_mismatch = "quantity_mismatch"
    hs_code_mismatch = "hs_code_mismatch"
    route_deviation = "route_deviation"
    historical_deviation = "historical_deviation"
    intermediary_reuse = "intermediary_reuse"
    shared_ownership = "shared_ownership"
    none = "none"


class SourceKind(str, Enum):
    document = "document"
    reference_db = "reference_db"
    derived = "derived"
    model = "model"


class EventType(str, Enum):
    run_started = "run_started"
    case_loaded = "case_loaded"
    triage = "triage"
    hypotheses_updated = "hypotheses_updated"
    plan_step = "plan_step"
    tool_call_started = "tool_call_started"
    tool_call_completed = "tool_call_completed"
    evidence_added = "evidence_added"
    graph_updated = "graph_updated"
    budget_updated = "budget_updated"
    corroboration = "corroboration"
    decision = "decision"
    evidence_requested = "evidence_requested"
    report_ready = "report_ready"
    run_failed = "run_failed"
    heartbeat = "heartbeat"
