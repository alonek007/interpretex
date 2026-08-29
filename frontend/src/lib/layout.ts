import dagre from "dagre";
import type { Edge, Node } from "reactflow";

export function layoutLR(nodes: Node[], edges: Edge[], nodeW = 180, nodeH = 54): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 24, ranksep: 60 });
  nodes.forEach((n) => g.setNode(n.id, { width: nodeW, height: nodeH }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const p = g.node(n.id);
    return { ...n, position: { x: p.x - nodeW / 2, y: p.y - nodeH / 2 } };
  });
}
