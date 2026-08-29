"""The deterministic fallback path (llm=None) must still produce a fully valid
investigation and never crash. Degradation is per-stage, not global: the result
is complete and meta.degraded records what happened.
"""
from __future__ import annotations

import pytest

from agent import investigate
from agent.demo_cases import build
from agent.miniregistry import MiniToolRegistry


@pytest.mark.parametrize("case_id", [
    "case_clean_001", "case_explainable_002", "case_suspicious_003",
])
def test_fallback_completes(case_id):
    view, world, tc = build(case_id)
    reg = MiniToolRegistry(view, world)
    result = investigate(view, reg, llm=None, budget=10)
    assert result.decision.verdict.value in ("release", "hold", "escalate")
    assert result.meta.degraded is True  # no LLM => fully deterministic fallback
    assert result.plan_steps
    assert result.report_markdown


def test_fallback_is_deterministic():
    import copy
    view, world, tc = build("case_suspicious_003")
    reg = MiniToolRegistry(view, world)
    r1 = investigate(view, reg, llm=None, budget=10)
    reg2 = MiniToolRegistry(view, world)
    r2 = investigate(view, reg2, llm=None, budget=10)
    assert [s.chosen_tool for s in r1.plan_steps if s.chosen_tool] == \
           [s.chosen_tool for s in r2.plan_steps if s.chosen_tool]
    assert r1.decision.verdict.value == r2.decision.verdict.value
