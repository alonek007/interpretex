"""Protocols: the three seams. Part 2 imports nothing from Part 1; Part 3 wires them."""
from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

from .investigation import InvestigationEvent, NetworkView, ToolResult, ToolSpec
from .trade import AgentCaseView, AttackSpec, CaseSummary, CaseSpec, TradeCase


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, *, system: str, messages: list[dict], temperature: float = 0.2,
                 max_tokens: int = 2048, tag: str = "") -> str: ...
    def complete_json(self, *, system: str, messages: list[dict], schema: dict,
                      temperature: float = 0.1, max_tokens: int = 2048,
                      tag: str = "", retries: int = 2) -> dict: ...


@runtime_checkable
class ToolRegistry(Protocol):
    def specs(self) -> list[ToolSpec]: ...
    def call(self, name: str, args: dict) -> ToolResult: ...


@runtime_checkable
class WorldAPI(Protocol):
    def list_cases(self) -> list[CaseSummary]: ...
    def load_case(self, case_id: str) -> TradeCase: ...
    def generate_case(self, spec: CaseSpec) -> TradeCase: ...
    def build_tool_registry(self, case: TradeCase) -> ToolRegistry: ...
    def network_view(self, entity_id: str | None = None, depth: int = 2) -> NetworkView: ...
    def attack(self, spec: AttackSpec, llm: LLMClient | None = None) -> TradeCase: ...


@runtime_checkable
class Investigator(Protocol):
    def investigate_stream(self, case: AgentCaseView, tools: ToolRegistry, *,
                           llm: LLMClient | None = None, budget: int = 6,
                           seed: int | None = None) -> Iterator[InvestigationEvent]: ...

    def investigate(self, case: AgentCaseView, tools: ToolRegistry, *,
                    llm: LLMClient | None = None, budget: int = 6,
                    seed: int | None = None, emit=None) -> object: ...
