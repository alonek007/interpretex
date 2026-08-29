"""Demo-case oracle: the three seeded cases must hit their expected verdicts.

This is the acceptance gate from master plan section 14 — never escalate an
explainable or clean case; always escalate a genuinely suspicious one.
"""
from __future__ import annotations

import pytest

from agent import investigate
from agent.demo_cases import build
from agent.miniregistry import MiniToolRegistry
from agent.eval import _case_class, _verdict_ok


@pytest.mark.parametrize("case_id,expected", [
    ("case_clean_001", "release"),
    ("case_explainable_002", "release"),   # HOLD acceptable; RELEASE is fine
    ("case_suspicious_003", "escalate"),
])
def test_demo_verdicts(case_id, expected):
    view, world, tc = build(case_id)
    reg = MiniToolRegistry(view, world)
    result = investigate(view, reg, llm=None, budget=10)
    verdict = result.decision.verdict.value
    assert _verdict_ok(case_id, verdict), f"{case_id}: expected {expected}-ish, got {verdict}"
    # the suspicious case must never be a false release/hold on a clean/explainable one
    if expected == "escalate":
        assert verdict == "escalate"
    else:
        assert verdict != "escalate"


def test_demo_case_class_resolves():
    assert _case_class("case_explainable_002") == "suspicious_but_legitimate"
    assert _case_class("case_suspicious_003") == "illicit"


def test_labels_not_visible_to_agent():
    """The agent receives an AgentCaseView with no label; only the eval/test
    harness reads the ground-truth label."""
    view, world, tc = build("case_suspicious_003")
    assert not hasattr(view, "label")
    assert tc.label is not None  # label lives on TradeCase, read only by eval
