"""The stream contract: events are emitted in a strict, valid order.

section 5.4 mandates: gapless seq starting at 0; run_started is first;
report_ready is last; every tool_call_completed follows its matching
tool_call_started; the decision event precedes report_ready. The stream is a
generator, so ordering is observable as it happens, not only at the end.
"""
from __future__ import annotations

import pytest

from agent import investigate_stream
from agent.demo_cases import build
from agent.miniregistry import MiniToolRegistry
from interpretex_contracts import EventType


@pytest.mark.parametrize("case_id", [
    "case_clean_001", "case_explainable_002", "case_suspicious_003",
])
def test_stream_ordering(case_id):
    view, world, tc = build(case_id)
    reg = MiniToolRegistry(view, world)
    events = list(investigate_stream(view, reg, llm=None, budget=10))

    types = [e.type for e in events]
    seqs = [e.seq for e in events]

    # gapless, monotonic, starts at 0
    assert seqs == list(range(len(seqs)))
    assert types[0] == EventType.run_started
    assert types[-1] == EventType.report_ready

    # decision strictly precedes report_ready
    assert types.index(EventType.decision) < types.index(EventType.report_ready)

    # every tool_call_completed is paired with a preceding tool_call_started
    started = 0
    for t in types:
        if t == EventType.tool_call_started:
            started += 1
        elif t == EventType.tool_call_completed:
            assert started > 0
            started -= 1
    assert started == 0


def test_stream_yields_report_payload():
    view, world, tc = build("case_clean_001")
    reg = MiniToolRegistry(view, world)
    events = list(investigate_stream(view, reg, llm=None, budget=10))
    last = events[-1]
    assert last.type == EventType.report_ready
    assert "result" in last.payload
    assert "report_markdown" in last.payload
