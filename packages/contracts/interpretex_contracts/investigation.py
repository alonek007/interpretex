"""Tool-layer models, reasoning models, events and results (frozen, sections 8.3-8.7)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    Dimension,
    EventType,
    HypothesisKind,
    HypothesisStatus,
    Severity,
    SourceKind,
    Stance,
    Verdict,
)


# ---------------------------------------------------------------- tool layer

class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SourceKind
    ref: str  # "<doc_id>.<field>" | "<table>/<key>[/<as_of>]" | "<tool>:<metric>"
    value: Optional[Any] = None
    as_of: Optional[str] = None
    label: Optional[str] = None


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    dimension: Dimension
    statement: str  # one factual quantified sentence, no verdict language
    severity: Severity  # deviation salience, never a fraud verdict
    metrics: dict[str, float] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    expected_range: Optional[str] = None


class ToolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str  # rendered into the planner prompt
    dimensions: list[Dimension]
    args_schema: dict[str, Any] = Field(default_factory=dict)  # JSON Schema
    cost_units: int = 1
    discriminates: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    call_id: str
    args: dict[str, Any] = Field(default_factory=dict)
    ok: bool
    summary: str  # <=200 chars, the first thing the planner reads
    observations: list[Observation] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    cost_units: int = 1
    latency_ms: int = 0
    error: Optional[str] = None


@runtime_checkable
class ToolRegistry(Protocol):
    """Case-scoped registry. call() must NEVER raise; failures return ok=False."""

    def specs(self) -> list[ToolSpec]: ...

    def call(self, name: str, args: dict[str, Any]) -> ToolResult: ...


# --------------------------------------------------------- reasoning models

class Triage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_narrative: str
    initial_concerns: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    dimensions_to_probe: list[Dimension] = Field(default_factory=list)


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str  # H1, H2, ...
    kind: HypothesisKind
    statement: str
    explains: list[Dimension] = Field(default_factory=list)
    prior: float = 0.5
    posterior: float = 0.5
    status: HypothesisStatus = HypothesisStatus.open
    discriminating_evidence_needed: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    rationale: Optional[str] = None


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str  # E1, E2, ...
    dimension: Dimension
    stance: Stance  # assigned by the agent only
    statement: str
    weight: float = 0.5  # agent-assigned strength 0..1, not a probability
    severity: Severity = Severity.none
    hypotheses_affected: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    tool_call_id: Optional[str] = None
    sources: list[SourceRef] = Field(default_factory=list)
    interpretation: Optional[str] = None


class ConsideredTool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    expected_information_gain: float = 0.0
    why_not: str = ""


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int
    reasoning: str
    chosen_tool: Optional[str] = None  # None means stop
    chosen_args: dict[str, Any] = Field(default_factory=dict)
    targets_hypotheses: list[str] = Field(default_factory=list)
    expected_information_gain: float = 0.0
    considered: list[ConsideredTool] = Field(default_factory=list)
    stop_reason: Optional[Literal["sufficient_evidence", "budget_exhausted", "no_informative_tool_left"]] = None


class SkippedTool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    reason: str


class BudgetState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int
    spent: int = 0
    remaining: int = 0
    calls_made: int = 0
    tools_skipped: list[SkippedTool] = Field(default_factory=list)
    exhaustive_cost: Optional[int] = None


class Corroboration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corroborated_dimensions: list[Dimension] = Field(default_factory=list)
    independent_signal_count: int = 0
    refuting_dimensions: list[Dimension] = Field(default_factory=list)
    strongest_benign_hypothesis: Optional[str] = None
    strongest_benign_posterior: float = 0.0
    narrative: str = ""


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    confidence: float
    headline: str  # readable in two seconds
    rationale: str  # 3-6 sentences citing evidence ids
    corroboration: Corroboration
    typology: Optional[str] = None
    caveats: list[str] = Field(default_factory=list)
    decisive_evidence_ids: list[str] = Field(default_factory=list)


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str
    why: str
    resolves_hypotheses: list[str] = Field(default_factory=list)
    priority: int = 2  # 1..3, 1 = highest


# ------------------------------------------------------------- evidence graph

GraphNodeKind = Literal[
    "document", "field", "reference", "tool", "finding", "dimension", "hypothesis", "decision", "entity", "vessel"
]
GraphRelation = Literal[
    "states", "compared_with", "produced", "supports", "refutes", "corroborates", "concludes", "linked_to"
]


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: GraphNodeKind
    label: str
    dimension: Optional[Dimension] = None
    stance: Optional[Stance] = None
    severity: Optional[Severity] = None
    meta: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    relation: GraphRelation
    label: Optional[str] = None


class EvidenceGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# ------------------------------------------------------------------- network

class NetworkFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    pattern: Literal[
        "intermediary_reuse", "shared_ownership", "vessel_reuse", "circular_trade", "price_pattern"
    ]
    statement: str
    entity_ids: list[str] = Field(default_factory=list)
    case_ids: list[str] = Field(default_factory=list)
    severity: Severity = Severity.none
    metrics: dict[str, float] = Field(default_factory=dict)


class NetworkView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus_entity_id: Optional[str] = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[NetworkFinding] = Field(default_factory=list)


# ------------------------------------------------------------ events + results

class InvestigationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int
    ts: datetime
    run_id: str
    type: EventType
    narration: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RunMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    case_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    model: str = "deterministic-fallback"
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    wall_ms: int = 0
    replayed: bool = False
    degraded: bool = False


class InvestigationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: RunMeta
    record: dict[str, Any]  # TradeRecord as model_dump(mode="json")
    triage: Triage
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    plan_steps: list[PlanStep] = Field(default_factory=list)
    tool_calls: list[ToolResult] = Field(default_factory=list)
    evidence_for: list[EvidenceItem] = Field(default_factory=list)
    evidence_against: list[EvidenceItem] = Field(default_factory=list)
    evidence_neutral: list[EvidenceItem] = Field(default_factory=list)
    budget: BudgetState
    graph: EvidenceGraph
    decision: Decision
    evidence_requests: list[EvidenceRequest] = Field(default_factory=list)
    report_markdown: str = ""
    events: list[dict[str, Any]] = Field(default_factory=list)  # full replayable trace


STANDARD_CAVEATS: tuple[str, str, str] = (
    "Reference data is synthetic and scoped to this prototype.",
    "Output is investigative decision support, not a regulatory determination.",
    "Anomalies may have legitimate explanations; no single tool can rule one out.",
)
