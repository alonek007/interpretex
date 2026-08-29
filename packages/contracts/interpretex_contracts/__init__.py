"""interpretex_contracts — the frozen shared contract (v1.0.0).

Owned by Part 1, imported by all three parts. Flat re-exports; the canonical
version string is ``CONTRACT_VERSION``.
"""

from .enums import (
    CONTRACT_VERSION,
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
from .helpers import (
    STANDARD_CAVEATS,
    Flags,
    IdCounter,
    SeqEmitter,
    event,
    new_run_id,
    sse_frame,
    sse_stream,
    stable_hash,
    utcnow,
)
from .investigation import (
    BudgetState,
    Corroboration,
    Decision,
    EvidenceGraph,
    EvidenceItem,
    EvidenceRequest,
    GraphEdge,
    GraphNode,
    Hypothesis,
    InvestigationEvent,
    InvestigationResult,
    NetworkFinding,
    NetworkPattern,
    NetworkView,
    Observation,
    PlanStep,
    RunMeta,
    SourceRef,
    ToolResult,
    ToolSpec,
    Triage,
)
from .llm import (
    LLMError,
    LLMJsonError,
    OpenRouterClient,
    ScriptedLLM,
    build_llm,
    extract_json_object,
    validate_against_schema,
)
from .fixtures import (
    FIXTURES_DIR,
    FixtureError,
    FixtureToolRegistry,
    list_case_fixture_ids,
    list_run_case_ids,
    list_tool_result_case_ids,
    load_case_fixture,
    load_case_fixture_raw,
    load_events_fixture,
    load_result_fixture,
    load_tool_results,
    load_tool_specs,
)
from .protocols import EmitFn, Investigator, LLMClient, ToolRegistry, WorldAPI
from .trade import (
    DEFAULT_TOOL_NAMES,
    AgentCaseView,
    AttackSpec,
    CaseLabel,
    CaseSpec,
    CaseSummary,
    Entity,
    Port,
    TradeCase,
    TradeDocument,
    TradeRecord,
    Vessel,
)

__version__ = CONTRACT_VERSION

__all__ = [
    "CONTRACT_VERSION",
    # enums
    "AnomalyKind", "CaseClass", "Dimension", "DocType", "EventType",
    "HypothesisKind", "HypothesisStatus", "Severity", "SourceKind", "Stance",
    "Verdict",
    # trade models
    "AgentCaseView", "AttackSpec", "CaseLabel", "CaseSpec", "CaseSummary",
    "DEFAULT_TOOL_NAMES", "Entity", "Port", "TradeCase", "TradeDocument",
    "TradeRecord", "Vessel",
    # investigation models
    "BudgetState", "Corroboration", "Decision", "EvidenceGraph",
    "EvidenceItem", "EvidenceRequest", "GraphEdge", "GraphNode",
    "Hypothesis", "InvestigationEvent", "InvestigationResult",
    "NetworkFinding", "NetworkPattern", "NetworkView", "Observation",
    "PlanStep", "RunMeta", "SourceRef", "ToolResult", "ToolSpec", "Triage",
    # protocols
    "EmitFn", "Investigator", "LLMClient", "ToolRegistry", "WorldAPI",
    # helpers
    "Flags", "IdCounter", "SeqEmitter", "STANDARD_CAVEATS", "event",
    "new_run_id", "sse_frame", "sse_stream", "stable_hash", "utcnow",
    # llm
    "LLMError", "LLMJsonError", "OpenRouterClient", "ScriptedLLM",
    "build_llm", "extract_json_object", "validate_against_schema",
    # fixtures
    "FIXTURES_DIR", "FixtureError", "FixtureToolRegistry",
    "list_case_fixture_ids", "list_run_case_ids", "list_tool_result_case_ids",
    "load_case_fixture", "load_case_fixture_raw", "load_events_fixture",
    "load_result_fixture", "load_tool_results", "load_tool_specs",
]
