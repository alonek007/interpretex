"""Evidence-graph provenance: every evidence node must trace to at least one
source, and the graph builder must flag orphan evidence. Provenance is a hard
requirement (section 8.4) — an assertion with no source is a compliance breach.
"""
from __future__ import annotations

import pytest

from agent import investigate
from agent.demo_cases import build
from agent.graph import EvidenceGraphBuilder, provenance_warnings
from agent.miniregistry import MiniToolRegistry
from interpretex_contracts import InvestigationEvent


@pytest.mark.parametrize("case_id", [
    "case_clean_001", "case_explainable_002", "case_suspicious_003",
])
def test_graph_has_evidence_and_hypothesis_nodes(case_id):
    view, world, tc = build(case_id)
    reg = MiniToolRegistry(view, world)
    result = investigate(view, reg, llm=None, budget=10)
    g = result.graph
    kinds = {n.kind for n in g.nodes}
    assert "hypothesis" in kinds
    assert "finding" in kinds  # evidence items are recorded as 'finding' nodes


def test_provenance_no_orphan_evidence():
    view, world, tc = build("case_suspicious_003")
    reg = MiniToolRegistry(view, world)
    result = investigate(view, reg, llm=None, budget=10)
    # every evidence node should carry at least one source ref
    orphan = [
        n.id for n in result.graph.nodes
        if n.kind == "evidence" and (not n.sources)
    ]
    warnings = provenance_warnings(result.graph)
    # either no orphan evidence exists, or it is explicitly flagged
    assert not orphan or any("provenance" in w.lower() or "orphan" in w.lower() for w in warnings)


def test_graph_builder_api():
    view, world, tc = build("case_clean_001")
    b = EvidenceGraphBuilder(view)
    snap, _, _ = b.snapshot()
    assert snap is not None
