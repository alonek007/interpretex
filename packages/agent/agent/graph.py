"""Incremental evidence-graph construction from SourceRefs.

Node ids are stable and derivable:
  doc:<doc_id> · field:<doc_id>.<field> · ref:<table>/<key>[/<as_of>]
  tool:<tool>  · find:<evidence_id> · dim:<dimension> · hyp:<hypothesis_id>
  dec:final

Every finding must be reachable from at least one document or reference node;
the decision node must be reachable from every corroborating dimension.
If a SourceRef is missing, a derived node is created rather than dropping the
edge, so provenance is never silently broken.
"""
from __future__ import annotations

from interpretex_contracts import (
    AgentCaseView,
    Dimension,
    EvidenceItem,
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    SourceKind,
    ToolResult,
)

_DIM_ORDER = ("economic", "physical", "temporal", "documentary", "behavioural", "network")


def doc_node_id(doc_id: str) -> str:
    return f"doc:{doc_id}"


def ref_node_id(ref: str) -> str:
    if "/" in ref:
        return f"ref:{ref}"
    return f"field:{ref}"


class EvidenceGraphBuilder:
    def __init__(self, case: AgentCaseView) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._edge_keys: set[tuple[str, str, str]] = set()
        self._new_nodes: list[GraphNode] = []
        self._new_edges: list[GraphEdge] = []
        for doc in case.documents:
            self._add_node(GraphNode(
                id=doc_node_id(doc.doc_id), kind="document",
                label=f"{doc.doc_id} ({doc.doc_type.value})", meta={"issuer": doc.issuer},
            ))

    # ---------------------------------------------------------------- internals

    def _add_node(self, node: GraphNode) -> None:
        if node.id not in self._nodes:
            self._nodes[node.id] = node
            self._new_nodes.append(node)

    def _add_edge(self, source: str, target: str, relation: str, label: str | None = None) -> None:
        key = (source, target, relation)
        if key in self._edge_keys or source not in self._nodes or target not in self._nodes:
            return
        self._edge_keys.add(key)
        edge = GraphEdge(source=source, target=target, relation=relation, label=label)  # type: ignore[arg-type]
        self._edges.append(edge)
        self._new_edges.append(edge)

    def _source_nodes(self, item: EvidenceItem, tool_result: ToolResult | None) -> list[str]:
        """Create/lookup nodes for an evidence item's sources; returns node ids."""
        ids: list[str] = []
        sources = item.sources or (tool_result.sources if tool_result else [])
        for src in sources:
            if src.kind in (SourceKind.document, SourceKind.reference_db):
                if "/" not in src.ref and "." in src.ref:
                    doc_id, _, field = src.ref.partition(".")
                    self._add_node(GraphNode(id=doc_node_id(doc_id), kind="document",
                                             label=doc_id, meta={"recovered_from": "source_ref"}))
                    self._add_node(GraphNode(id=ref_node_id(src.ref), kind="field",
                                             label=src.label or field or src.ref, meta={"ref": src.ref}))
                    self._add_edge(doc_node_id(doc_id), ref_node_id(src.ref), "states")
                else:
                    self._add_node(GraphNode(
                        id=ref_node_id(src.ref), kind="reference",
                        label=src.label or src.ref, meta={"ref": src.ref, "as_of": src.as_of},
                    ))
            elif src.kind == SourceKind.derived:
                self._add_node(GraphNode(id=ref_node_id(src.ref), kind="tool",
                                         label=src.label or src.ref, meta={"ref": src.ref}))
            else:  # model
                self._add_node(GraphNode(id=ref_node_id(src.ref), kind="tool",
                                         label=src.label or src.ref, meta={"ref": src.ref}))
            ids.append(ref_node_id(src.ref))
        if not ids and tool_result is not None:
            # never break provenance: derive from the tool
            nid = f"tool:{tool_result.tool}"
            self._add_node(GraphNode(id=nid, kind="tool", label=tool_result.tool,
                                     meta={"note": "no source refs on tool output"}))
            ids.append(nid)
        return ids

    # ------------------------------------------------------------------- public

    def add_evidence(self, item: EvidenceItem, tool_result: ToolResult | None = None) -> None:
        find_id = f"find:{item.evidence_id}"
        self._add_node(GraphNode(
            id=find_id, kind="finding", label=item.statement[:160],
            dimension=item.dimension, stance=item.stance, severity=item.severity,
            meta={"evidence_id": item.evidence_id, "weight": item.weight},
        ))
        tool_node = f"tool:{tool_result.tool}" if tool_result else None
        if tool_node:
            self._add_node(GraphNode(id=tool_node, kind="tool", label=tool_result.tool, meta={}))  # type: ignore[union-attr]
            self._add_edge(tool_node, find_id, "produced")
        for src_id in self._source_nodes(item, tool_result):
            relation = "compared_with" if src_id.startswith(("field:", "ref:")) else "states"
            self._add_edge(src_id, find_id, relation)  # type: ignore[arg-type]
        # finding -> dimension node
        dim_id = f"dim:{item.dimension.value}"
        self._add_node(GraphNode(id=dim_id, kind="dimension", label=item.dimension.value,
                                 dimension=item.dimension))
        self._add_edge(find_id, dim_id, "corroborates")
        # finding -> hypotheses
        for hid in item.hypotheses_affected:
            h_id = f"hyp:{hid}"
            self._add_node(GraphNode(id=h_id, kind="hypothesis", label=hid, meta={"hypothesis_id": hid}))
            relation = "supports" if item.stance.value == "supports_suspicion" else "refutes"
            self._add_edge(find_id, h_id, relation)  # type: ignore[arg-type]

    def add_hypothesis(self, hypothesis_id: str, statement: str) -> None:
        self._add_node(GraphNode(id=f"hyp:{hypothesis_id}", kind="hypothesis",
                                 label=statement[:160], meta={"hypothesis_id": hypothesis_id}))

    def add_decision(self, verdict: str, corroborated_dimensions: list[Dimension]) -> None:
        self._add_node(GraphNode(id="dec:final", kind="decision", label=verdict.upper(), meta={"verdict": verdict}))
        for dim in corroborated_dims:
            dim_id = f"dim:{dim.value}"
            self._add_node(GraphNode(id=dim_id, kind="dimension", label=dim.value, dimension=dim))
            self._add_edge(dim_id, "dec:final", "concludes")
        if not corroborated_dimensions:  # keep the decision reachable anyway
            self._add_node(GraphNode(id="dim:none", kind="dimension", label="none",
                                     dimension=Dimension.documentary))
            self._add_edge("dim:none", "dec:final", "concludes")

    def snapshot(self) -> tuple[EvidenceGraph, list[GraphNode], list[GraphEdge]]:
        graph = EvidenceGraph(nodes=list(self._nodes.values()), edges=list(self._edges))
        new_nodes, new_edges = self._new_nodes, self._new_edges
        self._new_nodes, self._new_edges = [], []
        return graph, new_nodes, new_edges

    def build(self) -> EvidenceGraph:
        return EvidenceGraph(nodes=list(self._nodes.values()), edges=list(self._edges))


def provenance_warnings(graph: EvidenceGraph) -> list[str]:
    """Findings NOT reachable from any document or reference node, plus dims
    that cannot reach the decision node. Empty list == acceptance test passes."""
    adjacency: dict[str, list[str]] = {}
    for edge in graph.edges:
        adjacency.setdefault(edge.source, []).append(edge.target)
    reachable: set[str] = set()

    def dfs(node: str) -> None:
        if node in reachable:
            return
        reachable.add(node)
        for nxt in adjacency.get(node, []):
            dfs(nxt)

    for node in graph.nodes:
        if node.kind in ("document", "reference"):
            dfs(node.id)

    warnings: list[str] = []
    for node in graph.nodes:
        if node.kind == "finding" and node.id not in reachable:
            warnings.append(f"finding {node.id} is not reachable from any document/reference node")
    for node in graph.nodes:
        if node.kind == "decision":
            for dim in [n for n in graph.nodes if n.kind == "dimension" and any(
                    e.source == n.id and e.target == node.id for e in graph.edges)]:
                sub_reachable: set[str] = set()
                stack = [dim.id]
                while stack:
                    cur = stack.pop()
                    if cur in sub_reachable:
                        continue
                    sub_reachable.add(cur)
                    stack.extend(adjacency.get(cur, []))
                if node.id not in sub_reachable:
                    warnings.append(f"dimension {dim.id} cannot reach the decision node")
    return warnings
