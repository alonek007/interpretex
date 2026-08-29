"""Baseline / contrast helpers.

The `baseline` endpoint contrasts the investigator's verdict with what a naive
single-signal rules engine would have done on the same evidence. That contrast
is the demo's central claim ("we escalate on correlation, not on any one red
flag"), so the computation lives here where it is easy to reason about and test.
"""
from __future__ import annotations

from typing import Any

from interpretex_contracts import InvestigationResult, Stance


def baseline_for(result: InvestigationResult) -> dict[str, Any]:
    """Return the naive-threshold baseline verdict for a completed result.

    The baseline escalates on *any* single signal that supports suspicion,
    regardless of corroboration or tested benign explanations. The agent is
    expected to differ on case_explainable_002 (baseline escalates, agent
    holds) — that gap is the whole point.
    """
    supports = [e for e in result.evidence_for if e.stance == Stance.supports_suspicion]
    has_signal = bool(supports)
    baseline_verdict = "escalate" if has_signal else ("hold" if result.evidence_neutral else "release")

    return {
        "agent_cost": result.budget.spent,
        "exhaustive_cost": result.budget.exhaustive_cost,
        "agent_verdict": result.decision.verdict.value,
        "baseline_verdict": baseline_verdict,
        "tools_skipped": [
            {"tool": s.tool, "reason": s.reason} for s in result.budget.tools_skipped
        ],
        "signal_count": len(supports),
    }
