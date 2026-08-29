"""The three seams, as typing Protocols.

Part 2 imports nothing from Part 1: it receives a ToolRegistry and an
LLMClient by dependency injection. Part 3 wires the real implementations via
two environment variables. These Protocols are the whole interface surface.
"""

from typing import Callable, Iterator, Optional, Protocol, runtime_checkable

from .investigation import (
    InvestigationEvent,
    InvestigationResult,
    NetworkView,
    ToolResult,
    ToolSpec,
)
from .trade import AgentCaseView, AttackSpec, CaseSpec, CaseSummary, TradeCase

#: Callback that receives each event as it is produced (used by ``investigate``).
EmitFn = Callable[[InvestigationEvent], None]


@runtime_checkable
class ToolRegistry(Protocol):
    """Case-scoped tool access: the registry closes over ONE case, so tool
    args never carry a case_id and the agent cannot query the wrong case."""

    def specs(self) -> list[ToolSpec]:
        """Available tools in stable order."""
        ...

    def call(self, name: str, args: dict) -> ToolResult:
        """Execute one tool. Must NEVER raise: unknown tool, bad args and
        internal failure all return ok=False with ``error`` set."""
        ...


@runtime_checkable
class LLMClient(Protocol):
    model: str

    def complete(self, *, system: str, messages: list[dict],
                 temperature: float = 0.2, max_tokens: int = 2048,
                 tag: str = "") -> str: ...

    def complete_json(self, *, system: str, messages: list[dict],
                      schema: dict, temperature: float = 0.1,
                      max_tokens: int = 2048, tag: str = "",
                      retries: int = 2) -> dict: ...


@runtime_checkable
class WorldAPI(Protocol):
    """Part 1's public surface (packages/world/api.py)."""

    def list_cases(self) -> list[CaseSummary]: ...

    def load_case(self, case_id: str) -> TradeCase:  # KeyError if unknown
        ...

    def generate_case(self, spec: CaseSpec) -> TradeCase: ...

    def build_tool_registry(self, case: TradeCase) -> ToolRegistry: ...

    def network_view(self, entity_id: Optional[str] = None,
                     depth: int = 2) -> NetworkView: ...

    def attack(self, spec: AttackSpec, llm=None) -> TradeCase: ...


@runtime_checkable
class Investigator(Protocol):
    """Part 2's public surface (packages/agent/api.py)."""

    def investigate_stream(self, case: AgentCaseView, tools: ToolRegistry, *,
                           llm=None, budget: int = 6, seed: Optional[int] = None
                           ) -> Iterator[InvestigationEvent]: ...

    def investigate(self, case: AgentCaseView, tools: ToolRegistry, *,
                    llm=None, budget: int = 6, seed: Optional[int] = None,
                    emit: Optional[EmitFn] = None) -> InvestigationResult: ...


__all__ = [
    "ToolRegistry", "LLMClient", "WorldAPI", "Investigator",
    "EmitFn", "AgentCaseView", "AttackSpec", "CaseSpec", "CaseSummary",
    "TradeCase", "ToolSpec", "ToolResult",
]
