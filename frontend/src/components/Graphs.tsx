import { useMemo } from "react";
import ReactFlow, { Background, Controls, MarkerType } from "reactflow";
import "reactflow/dist/style.css";
import type { GraphEdge, GraphNode } from "../types/contract";
import { DIMENSION_COLOR, VERDICT_COLOR } from "../lib/dim";
import { layoutLR } from "../lib/layout";

const KIND_SHAPE: Record<string, string> = {
  document: "round",
  field: "round",
  reference: "round",
  tool: "round",
  finding: "diamond",
  dimension: "ellipse",
  hypothesis: "ellipse",
  decision: "rectangle",
  entity: "rectangle",
  vessel: "rectangle",
};

export function EvidenceGraph({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const { rfNodes, rfEdges } = useMemo(() => {
    const ns = nodes.map((n) => ({
      id: n.id,
      data: { label: n.label },
      position: { x: 0, y: 0 },
      style: {
        background: "#0f1626",
        border: `1px solid ${n.dimension ? DIMENSION_COLOR[n.dimension] : "#475569"}`,
        color: "#e6edf7",
        borderRadius: KIND_SHAPE[n.kind] === "diamond" ? "4px" : "6px",
        width: 180,
        fontSize: 11,
      },
    }));
    const es = edges.map((e) => ({
      id: `${e.source}->${e.target}:${e.relation}`,
      source: e.source,
      target: e.target,
      label: e.label ?? e.relation,
      animated: true,
      style: { stroke: "#475569", fontSize: 9 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#475569" },
    }));
    return { rfNodes: layoutLR(ns, es), rfEdges: es };
  }, [nodes, edges]);

  if (!nodes.length) {
    return (
      <div className="text-xs text-slate-500 p-3 h-full flex items-center justify-center">
        Graph builds as the investigation progresses.
      </div>
    );
  }
  return (
    <div className="h-full">
      <ReactFlow nodes={rfNodes} edges={rfEdges} fitView proOptions={{ hideAttribution: true }}>
        <Background color="#1e293b" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

export function NetworkGraphView({
  nodes,
  edges,
  findings,
}: {
  nodes: { id: string; label: string; kind: string; role?: string }[];
  edges: GraphEdge[];
  findings: { finding_id: string; pattern: string; statement: string; entity_ids: string[]; severity: string }[];
}) {
  const { rfNodes, rfEdges } = useMemo(() => {
    const ns = nodes.map((n) => ({
      id: n.id,
      data: { label: `${n.label}\n${n.role ?? ""}` },
      position: { x: 0, y: 0 },
      style: {
        background: "#0f1626",
        border: "1px solid #fb7185",
        color: "#e6edf7",
        borderRadius: 6,
        width: 170,
        fontSize: 11,
      },
    }));
    const es = edges.map((e) => ({
      id: `${e.source}->${e.target}:${e.relation}`,
      source: e.source,
      target: e.target,
      label: e.label ?? e.relation,
      style: { stroke: "#64748b", fontSize: 9 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#64748b" },
    }));
    return { rfNodes: layoutLR(ns, es, 170, 48), rfEdges: es };
  }, [nodes, edges]);

  return (
    <div className="grid grid-rows-[1fr_auto] h-full">
      <div className="min-h-0">
        {nodes.length ? (
          <ReactFlow nodes={rfNodes} edges={rfEdges} fitView proOptions={{ hideAttribution: true }}>
            <Background color="#1e293b" />
            <Controls showInteractive={false} />
          </ReactFlow>
        ) : (
          <div className="text-xs text-slate-500 p-3">No network loaded.</div>
        )}
      </div>
      <div className="max-h-40 overflow-auto scroll-thin border-t border-edge p-2 space-y-1">
        {findings.map((f) => (
          <div key={f.finding_id} className="text-[11px] text-slate-300">
            <span className="text-rose-300 font-mono">{f.pattern}</span> — {f.statement}
          </div>
        ))}
        {!findings.length && <div className="text-[11px] text-slate-500">No findings.</div>}
      </div>
    </div>
  );
}
