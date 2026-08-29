"""Unit tests for the deterministic policy gate (the most important code).

The gate is a pure function of the evidence ledger: it must escalate only when
>= 2 corroborated suspicious dimensions exist, no benign posterior >= 0.6, and a
benign hypothesis was actually tested; otherwise release when every elevated
signal is matched, else hold. The LLM may *propose*; the gate *disposes*.
"""
from __future__ import annotations

from interpretex_contracts import (
    Corroboration,
    Decision,
    Dimension,
    EvidenceItem,
    Hypothesis,
    HypothesisKind,
    Severity,
    Stance,
)

from agent import policy


def _hyp(hid, kind, posterior=0.3, explains=(Dimension.economic,)):
    return Hypothesis(
        hypothesis_id=hid, kind=kind,
        statement=f"{hid} statement", prior=0.333, posterior=posterior,
        explains=list(explains), status="open",
    )


def _ev(eid, dim, stance, sev=Severity.medium, weight=0.7):
    return EvidenceItem(
        evidence_id=eid, dimension=dim, stance=stance,
        statement=f"{eid} {dim.value}", weight=weight, severity=sev,
        hypotheses_affected=[], observation_ids=[eid], tool_call_id="c1",
        sources=[], interpretation="",
    )


HYPS = [
    _hyp("H1", HypothesisKind.benign, 0.2, (Dimension.economic,)),
    _hyp("H2", HypothesisKind.suspicious, 0.7, (Dimension.economic,)),
    _hyp("H3", HypothesisKind.benign, 0.2, (Dimension.documentary,)),
    _hyp("H4", HypothesisKind.suspicious, 0.7, (Dimension.documentary,)),
]


def _corr(dims):
    return Corroboration(
        independent_signal_count=len(dims),
        corroborated_dimensions=list(dims),
        narrative="n",
    )


def _decide(evidence, hyps=HYPS, corr=None, calls=None, plan_steps=None):
    corr = corr or _corr([d for d in {e.dimension for e in evidence}])
    return policy.decide(evidence, hyps, corr, calls or [], plan_steps or [], degraded=False)


def test_single_dimension_never_escalates():
    ev = [_ev("E1", Dimension.economic, Stance.supports_suspicion)]
    d = _decide(ev)
    assert d.verdict.value == "hold"  # one dim can never escalate


def test_two_dims_but_benign_untested_holds():
    ev = [
        _ev("E1", Dimension.economic, Stance.supports_suspicion),
        _ev("E2", Dimension.documentary, Stance.supports_suspicion),
    ]
    d = _decide(ev)  # no contract call -> benign not tested
    assert d.verdict.value == "hold"


def test_two_dims_benign_tested_escalates():
    ev = [
        _ev("E1", Dimension.economic, Stance.supports_suspicion),
        _ev("E2", Dimension.documentary, Stance.supports_suspicion),
    ]
    from interpretex_contracts import PlanStep
    ps = [PlanStep(step=1, reasoning="", chosen_tool="check_contract_or_supporting_evidence",
                   chosen_args={}, targets_hypotheses=[], expected_information_gain=0.0, considered=[])]
    calls = []
    d = _decide(ev, plan_steps=ps, calls=calls)
    assert d.verdict.value == "escalate"
    assert d.typology is not None


def test_fully_matched_release():
    ev = [
        _ev("E1", Dimension.economic, Stance.supports_suspicion),
        _ev("E2", Dimension.economic, Stance.refutes_suspicion, weight=0.7),
    ]
    d = _decide(ev)
    assert d.verdict.value == "release"


def test_strong_benign_blocks_escalate():
    hyps = list(HYPS)
    hyps[0] = _hyp("H1", HypothesisKind.benign, 0.8, (Dimension.economic,))  # posterior >= 0.6
    ev = [
        _ev("E1", Dimension.economic, Stance.supports_suspicion),
        _ev("E2", Dimension.documentary, Stance.supports_suspicion),
    ]
    from interpretex_contracts import PlanStep
    ps = [PlanStep(step=1, reasoning="", chosen_tool="check_contract_or_supporting_evidence",
                   chosen_args={}, targets_hypotheses=[], expected_information_gain=0.0, considered=[])]
    d = _decide(ev, hyps=hyps, plan_steps=ps)
    assert d.verdict.value != "escalate"
