"""The AgentCaseView must NEVER carry the label or world-side context."""

from interpretex_contracts import CaseLabel, Entity, Vessel, load_case_fixture


def test_agent_view_has_no_label_or_entities():
    case = load_case_fixture("case_suspicious_003")
    view = case.to_agent_view()
    assert not hasattr(view, "label")
    assert not hasattr(view, "entities")
    assert not hasattr(view, "vessel")
    # the agent must not be able to read the intended verdict
    assert isinstance(case.label, CaseLabel)
    dumped = view.model_dump()
    assert "label" not in dumped
    assert "entities" not in dumped


def test_agent_view_preserves_documents_and_record():
    case = load_case_fixture("case_explainable_002")
    view = case.to_agent_view()
    assert len(view.documents) == len(case.documents)
    assert view.record.commodity == case.record.commodity
