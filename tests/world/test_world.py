"""World-layer tests: determinism, tool robustness, demo-case guarantees, language."""

import re

import pytest

from interpretex_world import World, attack
from interpretex_world.demo import build_demo_cases, build_attacker_fallback

BANNED = re.compile(
    r"\b(fraud|fraudulent|launder|laundering|laundered|suspicious|illicit|illegal|"
    r"criminal|smuggle|evasion|evade|money laundering|terror|sanction busting|risk)\b",
    re.I,
)


def test_demo_cases_deterministic():
    a = build_demo_cases()
    b = build_demo_cases()
    assert [c.model_dump_json() for c in a] == [c.model_dump_json() for c in b]


def test_attacker_fallback_deterministic():
    a = build_attacker_fallback().model_dump_json()
    b = build_attacker_fallback().model_dump_json()
    assert a == b


@pytest.mark.parametrize("case_id", [
    "case_clean_001", "case_explainable_002", "case_suspicious_003", "case_adv_004",
])
def test_tools_never_raise(case_id):
    w = World()
    case = w.load_case(case_id)
    reg = w.build_tool_registry(case)
    for spec in reg.specs():
        # unknown/blank args must return ok=False, never raise
        res = reg.call(spec.name, {})
        assert res is not None
        assert res.summary is not None


def test_clean_case_has_no_observation_above_low():
    w = World()
    reg = w.build_tool_registry(w.load_case("case_clean_001"))
    for spec in reg.specs():
        res = reg.call(spec.name, {})
        for o in res.observations:
            assert o.severity.value in ("none", "low"), (
                f"clean case raised {o.severity.value}: {o.statement}")


def test_explainable_case_has_exactly_one_medium():
    w = World()
    reg = w.build_tool_registry(w.load_case("case_explainable_002"))
    mediums = 0
    for spec in reg.specs():
        res = reg.call(spec.name, {})
        mediums += sum(1 for o in res.observations if o.severity.value == "medium")
    assert mediums == 1, f"expected exactly one medium, got {mediums}"


def test_suspicious_case_escalates_on_multiple_dimensions():
    w = World()
    reg = w.build_tool_registry(w.load_case("case_suspicious_003"))
    highs = [o.dimension.value for spec in reg.specs()
             for o in reg.call(spec.name, {}).observations
             if o.severity.value == "high"]
    assert len(highs) >= 4, f"illicit case needs >=4 high dims, got {highs}"


def test_adversarial_case_stays_low_or_medium():
    w = World()
    case = attack()
    reg = w.build_tool_registry(case)
    high = 0
    for spec in reg.specs():
        res = reg.call(spec.name, {})
        high += sum(1 for o in res.observations if o.severity.value == "high")
    assert high == 0, "attacker case must not trip any high-severity signal"


def test_no_verdict_language_in_tool_output():
    w = World()
    for case in w._demo_and_attacker():
        reg = w.build_tool_registry(case)
        for spec in reg.specs():
            res = reg.call(spec.name, {"claim": "grade A"} if spec.name ==
                           "check_contract_or_supporting_evidence" else {})
            blob = res.summary + " " + " ".join(o.statement for o in res.observations)
            assert not BANNED.search(blob), f"{case.case_id}/{spec.name}: {blob[:120]}"
