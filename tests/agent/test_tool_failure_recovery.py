"""Tool failure recovery: a tool that raises must NOT break the investigation.

The loop wraps every ToolRegistry.call in try/except and converts the failure
into a failed ToolResult, so the agent degrades that stage and keeps going.
"""
from __future__ import annotations

import pytest

from agent import investigate
from agent.demo_cases import build
from interpretex_contracts import EventType

from tests.agent.fakes import FakeToolRegistry


@pytest.mark.parametrize("fail", [
    {"check_price_benchmark"},
    {"check_document_consistency"},
    {"check_contract_or_supporting_evidence"},
])
def test_tool_failure_does_not_crash(fail):
    view, world, tc = build("case_suspicious_003")
    reg = FakeToolRegistry(view, world, fail=fail)
    # must not raise
    result = investigate(view, reg, llm=None, budget=10)
    assert result.decision.verdict.value in ("release", "hold", "escalate")
    assert result.meta is not None
    # a tool-failure is recorded as a failed call, never an unhandled exception
    failed = [t for t in result.tool_calls if not t.ok]
    # at least the failing tool appears as a failed call (or was skipped past)
    assert failed or result.meta.degraded


def test_recovery_emits_events():
    view, world, tc = build("case_suspicious_003")
    reg = FakeToolRegistry(view, world, fail={"check_price_benchmark"})
    events = list(__import__("agent", fromlist=["investigate_stream"]).investigate_stream(
        view, reg, llm=None, budget=10))
    # stream still terminates with report_ready despite the failure
    assert events[-1].type == EventType.report_ready
