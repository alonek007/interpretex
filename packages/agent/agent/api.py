"""Part 2 public surface — exactly this, nothing more (section 5.6).

    investigate_stream(case, tools, *, llm=None, budget=6, seed=None)
        -> Iterator[InvestigationEvent]     # generator; last event is report_ready
    investigate(case, tools, *, llm=None, budget=6, seed=None, emit=None)
        -> InvestigationResult              # thin blocking wrapper

`llm=None` runs the deterministic fallback path (meta.degraded=true).
The agent imports nothing from Part 1: the ToolRegistry and LLMClient arrive
by dependency injection against the shared contracts protocols.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator

from interpretex_contracts import (
    AgentCaseView,
    InvestigationEvent,
    InvestigationResult,
    ToolRegistry,
)

if TYPE_CHECKING:  # pragma: no cover
    from interpretex_contracts import EmitFn, LLMClient

__all__ = ["investigate", "investigate_stream"]


def investigate_stream(
    case: AgentCaseView,
    tools: ToolRegistry,
    *,
    llm: Any | None = None,
    budget: int = 6,
    seed: int | None = None,
) -> Iterator[InvestigationEvent]:
    """Generator of InvestigationEvent; final event is report_ready whose
    payload['result'] is the full InvestigationResult as model_dump(mode='json')."""
    from .loop import run_investigation

    yield from run_investigation(case, tools, llm=llm, budget=budget, seed=seed)


def investigate(
    case: AgentCaseView,
    tools: ToolRegistry,
    *,
    llm: Any | None = None,
    budget: int = 6,
    seed: int | None = None,
    emit: Any | None = None,
) -> InvestigationResult:
    """Blocking wrapper: drains investigate_stream. `emit` receives every event."""
    result: InvestigationResult | None = None
    for event in investigate_stream(case, tools, llm=llm, budget=budget, seed=seed):
        if emit is not None:
            emit(event)
        if event.type.value == "report_ready":
            result = InvestigationResult.model_validate(event.payload["result"])
    if result is None:  # stream terminated with run_failed
        raise RuntimeError("investigation terminated without a report_ready event")
    return result
