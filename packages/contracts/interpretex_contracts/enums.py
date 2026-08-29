"""Closed vocabularies for Interpretex.

These enums are part of the frozen contract (v1.0.0). Field and member names
are normative: Parts 2 and 3 code against these exact strings. Do not rename
or reorder members after the contract freeze.
"""

from enum import Enum


class DocType(str, Enum):
    """Document types found in a trade-finance case file."""

    letter_of_credit = "letter_of_credit"
    commercial_invoice = "commercial_invoice"
    bill_of_lading = "bill_of_lading"
    packing_list = "packing_list"
    certificate_of_origin = "certificate_of_origin"
    insurance_certificate = "insurance_certificate"
    inspection_certificate = "inspection_certificate"
    sales_contract = "sales_contract"


class Dimension(str, Enum):
    """Independent axes of evidence.

    Load-bearing: corroboration is *defined* as suspicion-supporting evidence
    appearing in two or more distinct dimensions, and a single-dimension
    anomaly can never escalate under the policy gate.
    """

    economic = "economic"
    physical = "physical"
    temporal = "temporal"
    documentary = "documentary"
    behavioural = "behavioural"
    network = "network"


class Severity(str, Enum):
    """Deviation salience emitted by a tool.

    This is explicitly NOT a fraud verdict and NOT a risk score: it maps the
    magnitude of a deviation against fixed, documented thresholds. Assigning
    meaning (stance, weight, verdict) is the agent's job, never the tool's.
    """

    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


class Stance(str, Enum):
    """Evidence stance in the for/against ledger.

    Assigned by the agent ONLY. Tools never set a stance: a tool reports a
    quantified fact; interpreting whether it supports or refutes suspicion is
    the investigation layer's job.
    """

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
    """Ground-truth class of a case. Never shown to the agent."""

    clean = "clean"
    suspicious_but_legitimate = "suspicious_but_legitimate"
    illicit = "illicit"
    adversarial = "adversarial"


class AnomalyKind(str, Enum):
    """Generator anomaly knobs. One injector exists per member."""

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
    """Investigation event stream types (the Part 2 -> Part 3 seam)."""

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


CONTRACT_VERSION = "1.0.0"
