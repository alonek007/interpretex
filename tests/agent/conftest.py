"""Shared pytest fixtures for the Part 2 agent test-suite."""
from __future__ import annotations

import pytest

from agent.demo_cases import build
from agent.miniregistry import MiniToolRegistry

from tests.agent.fakes import FakeToolRegistry, ScriptedLLM


@pytest.fixture
def case_ids():
    return ["case_clean_001", "case_explainable_002", "case_suspicious_003"]


@pytest.fixture
def make_case():
    """Returns (AgentCaseView, MiniWorld, TradeCase) for a demo case id."""

    def _(case_id: str):
        return build(case_id)

    return _


@pytest.fixture
def registry_for():
    """Returns (AgentCaseView, ToolRegistry) for a demo case id (no failures)."""

    def _(case_id: str):
        view, world, tc = build(case_id)
        return view, MiniToolRegistry(view, world), tc

    return _


@pytest.fixture
def failing_registry_for():
    """Returns a registry that raises on the given tool names."""

    def _(case_id: str, fail: set[str] | None = None):
        view, world, tc = build(case_id)
        return view, FakeToolRegistry(view, world, fail=fail), tc

    return _
