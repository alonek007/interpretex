"""Investigation-layer models: tool seam, reasoning models, events, result.

Tool-side models (SourceRef/Observation/ToolSpec/ToolResult) are the Part 1 ->
Part 2 seam; InvestigationEvent is the Part 2 -> Part 3 seam. Reasoning models
are authored here but populated by Part 2 (and by Part 1 only for the scripted
demo-trace fixture).
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    AnomalyKind,
    CaseClass,
    Dimension,
    DocType,
    EventType,
    HypothesisKind,
    HypothesisStatus,
    Severity,
    SourceKind,
    Stance,
    Verdict,
)
from .trade import TradeDocument, TradeRecord

# ---------------------------------------------------------------- tool seam --


class SourceRef(BaseModel):
    """Provenance pointer. ``ref`` format is normative:

    - documents:      ``"<doc_id>.<field>"``  e.g. ``"INV-2026-0912.unit_price"``
    - reference world: ``"<table>/<key>[/<as_of>]"``  e.g. ``"benchmarks/copper_cathode/2026-08"``
    - derived:         ``"<tool>:<metric>"``  e.g. ``"check_price_benchmark:deviation_pct"``
    """

    model_config = ConfigDict(extra="forbid")

    kind: SourceKind
    ref: str
    value: Optional[Any] = None
    as_of: Optional[str] = None
    label: Optional[str] = None


class Observation(BaseModel):
    """One factual, quantified finding with no verdict language.

    ``statement`` is a single factual sentence; ``metrics`` carries the numbers
    behind the statement so the UI and report never re-parse prose.
    """

    model_config = ConfigDict(extra="forbid")

    observation_id: str
    dimension: Dimension
    statement: str
    severity: Severity
    metrics: dict[str, float]
    sources: list[SourceRef]
    expected_range: Optional[list[float]] = None


class ToolSpec(BaseModel):
    """Tool description rendered straight into the planner prompt.

    ``description`` must state what evidence the tool yields and which
    hypotheses it separates — not how it is implemented.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    dimensions: list[Dimension]
    args_schema: dict[str, Any]
    cost_units: int
    discriminates: list[str]


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    call_id: str
    args: dict[str, Any]
    ok: bool
    summary: str = Field(max_length=200)
    observations: list[Observation]
    raw: dict[str, Any]
    sources: list[SourceRef]
    cost_units: int
    latency_ms: int
    error: Optional[str] = None


# ----------------------------------------------------------- reasoning models --


class Triage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_narrative: str  # 2-4 plain sentences
    initial_concerns: list[str]
    unknowns: list[str]
    dimensions_to_probe: list[Dimension]


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str  # H1, H2, ...
    kind: HypothesisKind
    statement: str
    explains: list[Dimension]
    prior: float = Field(ge=0.0, le=1.0)
    posterior: float = Field(ge=0.0, le=1.0)
    status: HypothesisStatus
    discriminating_evidence_needed: list[str]
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    rationale: Optional[str] = None


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str  # E1, E2, ...
    dimension: Dimension
    stance: Stance
    statement: str
    weight: float = Field(ge=0.0, le=1.0)  # agent-assigned strength, not a probability
    severity: Severity
    hypotheses_affected: list[str]
    observation_ids: list[str]
    tool_call_id: Optional[str] = None
    sources: list[SourceRef]
    interpretation: Optional[str] = None  # one line: why this stance, given the alternatives


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int
    reasoning: str
    chosen_tool: Optional[str] = None  # None means stop
    chosen_args: dict[str, Any]
    targets_hypotheses: list[str]
    expected_information_gain: float = Field(ge=0.0)
    considered: list[dict[str, Any]]  # {tool, expected_information_gain, why_not}
    stop_reason: Optional[Literal["sufficient_evidence", "budget_exhausted", "no_informative_tool_left"]] = None


class BudgetState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int
    spent: int
    remaining: int
    calls_made: int
    tools_skipped: list[dict[str, Any]]  # {tool, reason}
    exhaustive_cost: Optional[int] = None


class Corroboration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corroborated_dimensions: list[Dimension]
    independent_signal_count: int
    refuting_dimensions: list[Dimension]
    strongest_benign_hypothesis: Optional[str] = None
    strongest_benign_posterior: float = Field(ge=0.0, le=1.0)
    narrative: str  # why these signals are or are not independent of one another


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str  # readable in two seconds
    rationale: str  # 3-6 sentences citing evidence ids
    corroboration: Corroboration
    typology: Optional[str] = None
    caveats: list[str]
    decisive_evidence_ids: list[str]


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str
    why: str
    resolves_hypotheses: list[str]
    priority: int = Field(ge=1, le=3)


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal[
        "document", "field", "reference", "tool", "finding",
        "dimension", "hypothesis", "decision", "entity", "vessel",
    ]
    label: str
    dimension: Optional[Dimension] = None
    stance: Optional[Stance] = None
    severity: Optional[Severity] = None
    meta: dict[str, Any]


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    relation: Literal[
        "states", "compared_with", "produced", "supports",
        "refutes", "corroborates", "concludes", "linked_to",
    ]
    label: Optional[str] = None


class EvidenceGraph(BaseModel):
    """A provenance DAG, not a picture: every finding reachable from a source."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ------------------------------------------------------------------ network ---

NetworkPattern = Literal[
    "intermediary_reuse", "shared_ownership", "vessel_reuse",
    "circular_trade", "price_pattern",
]


class NetworkFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    pattern: NetworkPattern
    statement: str
    entity_ids: list[str]
    case_ids: list[str]
    severity: Severity
    metrics: dict[str, float]


class NetworkView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus_entity_id: Optional[str] = None
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    findings: list[NetworkFinding]


# -------------------------------------------------------------- run + events --


class RunMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    case_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    model: str
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    wall_ms: int
    replayed: bool
    degraded: bool


class InvestigationEvent(BaseModel):
    """One event in the SSE stream.

    Ordering guarantees (part of the contract):
    - ``seq`` starts at 0 and increments by exactly 1 with no gaps;
    - ``run_started`` is always seq 0;
    - the stream terminates with ``report_ready`` or ``run_failed``;
    - a ``tool_call_completed`` always follows its matching ``tool_call_started``;
    - ``decision`` always precedes ``report_ready``.

    ``narration`` is a single human-readable line: the timeline must be
    renderable from narration alone, so the UI degrades gracefully if a
    payload shape surprises it.
    """

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=0)
    ts: datetime
    run_id: str
    type: EventType
    narration: str
    payload: dict[str, Any]


class InvestigationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: RunMeta
    record: TradeRecord
    triage: Triage
    hypotheses: list[Hypothesis]
    plan_steps: list[PlanStep]
    tool_calls: list[ToolResult]
    evidence_for: list[EvidenceItem]
    evidence_against: list[EvidenceItem]
    evidence_neutral: list[EvidenceItem]
    budget: BudgetState
    graph: EvidenceGraph
    decision: Decision
    evidence_requests: list[EvidenceRequest]
    report_markdown: str
    events: list[InvestigationEvent]  # full replayable trace


__all__ = [
    "SourceRef", "Observation", "ToolSpec", "ToolResult",
    "Triage", "Hypothesis", "EvidenceItem", "PlanStep", "BudgetState",
    "Corroboration", "Decision", "EvidenceRequest",
    "GraphNode", "GraphEdge", "EvidenceGraph",
    "NetworkPattern", "NetworkFinding", "NetworkView",
    "RunMeta", "InvestigationEvent", "InvestigationResult",
    # re-exported convenience names used across parts
    "AnomalyKind", "CaseClass", "Dimension", "DocType", "EventType",
    "HypothesisKind", "HypothesisStatus", "Severity", "SourceKind",
    "Stance", "Verdict", "TradeDocument", "TradeRecord",
]
