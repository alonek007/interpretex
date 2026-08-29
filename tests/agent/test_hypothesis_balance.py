"""Hypothesis balance: for every flagged dimension the catalogue must contain at
least one benign AND one suspicious hypothesis, with stable ids H1..H10 and no
duplicates. Balance is what stops the agent from being blind to the innocent
explanation.
"""
from __future__ import annotations

import pytest

from agent import fallback as fb
from agent.demo_cases import build
from agent.miniregistry import MiniToolRegistry
from interpretex_contracts import HypothesisKind


def _hyps(case_id):
    view, world, tc = build(case_id)
    reg = MiniToolRegistry(view, world)
    specs = reg.specs()
    triage = fb.fallback_triage(view, specs)
    hyps, injected = fb.fallback_hypotheses(triage)
    return triage, hyps, injected


@pytest.mark.parametrize("case_id", [
    "case_clean_001", "case_explainable_002", "case_suspicious_003",
])
def test_balance_per_dimension(case_id):
    triage, hyps, injected = _hyps(case_id)
    for dim in triage.dimensions_to_probe:
        covering = [h for h in hyps if dim in h.explains]
        assert any(h.kind == HypothesisKind.benign for h in covering), \
            f"{dim.value} has no benign hypothesis"
        assert any(h.kind == HypothesisKind.suspicious for h in covering), \
            f"{dim.value} has no suspicious hypothesis"


def test_no_duplicate_ids():
    _, hyps, _ = _hyps("case_suspicious_003")
    ids = [h.hypothesis_id for h in hyps]
    assert len(ids) == len(set(ids))


def test_ids_are_well_formed_and_include_core_set():
    _, hyps, _ = _hyps("case_suspicious_003")
    ids = {h.hypothesis_id for h in hyps}
    # the canonical H1..H10 set is always present...
    assert {f"H{i}" for i in range(1, 11)}.issubset(ids)
    # ...and any extras keep the H<n> scheme
    assert all(i[0] == "H" and i[1:].isdigit() for i in ids)
