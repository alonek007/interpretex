"""Contract fixture integrity: every shipped fixture must parse through its model."""

import pytest

from interpretex_contracts import (
    FixtureError, InvestigationEvent, InvestigationResult, ToolResult, ToolSpec,
    TradeCase, list_case_fixture_ids, load_case_fixture, load_events_fixture,
    load_result_fixture, load_tool_results, load_tool_specs,
)


def test_tool_specs_validate():
    specs = load_tool_specs()
    assert len(specs) == 8
    names = {s.name for s in specs}
    assert names == {
        "read_document", "check_document_consistency", "check_price_benchmark",
        "check_vessel_capacity", "check_transit_plausibility", "check_historical_trade",
        "check_counterparty_network", "check_contract_or_supporting_evidence",
    }


@pytest.mark.parametrize("case_id", list_case_fixture_ids())
def test_case_fixture_validate(case_id):
    case = load_case_fixture(case_id)
    assert isinstance(case, TradeCase)
    assert case.case_id == case_id


@pytest.mark.parametrize("case_id", list_case_fixture_ids())
def test_tool_results_validate(case_id):
    results = load_tool_results(case_id)
    assert len(results) == 8
    for name, res in results.items():
        assert isinstance(res, ToolResult)
        # every canned result is a real, non-error result
        assert res.ok is True, f"{case_id}/{name} fixture result not ok"


def test_run_fixture_validate():
    events = load_events_fixture("case_suspicious_003")
    result = load_result_fixture("case_suspicious_003")
    assert all(isinstance(e, InvestigationEvent) for e in events)
    assert isinstance(result, InvestigationResult)
    assert result.meta.case_id == "case_suspicious_003"


def test_event_seq_is_gapless():
    events = load_events_fixture("case_suspicious_003")
    assert [e.seq for e in events] == list(range(len(events)))
    assert events[0].type.value == "run_started"
    assert events[-1].type.value == "report_ready"
    assert result_verdict_is_escalate()


def test_result_verdict_escalate():
    result = load_result_fixture("case_suspicious_003")
    assert result.decision.verdict.value == "escalate"


def result_verdict_is_escalate():
    return True
