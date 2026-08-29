import { useCallback, useEffect, useReducer, useRef } from "react";
import type {
  BudgetState,
  Corroboration,
  Decision,
  EvidenceGraph,
  EvidenceItem,
  EvidenceRequest,
  GraphEdge,
  GraphNode,
  Hypothesis,
  InvestigationEvent,
  PlanStep,
  ToolResult,
  Triage,
} from "../types/contract";

export interface RunState {
  runId: string | null;
  status: "idle" | "streaming" | "done" | "failed";
  events: InvestigationEvent[];
  record: Record<string, any> | null;
  triage: Triage | null;
  hypotheses: Hypothesis[];
  planSteps: PlanStep[];
  toolCalls: ToolResult[];
  evidence: EvidenceItem[];
  budget: BudgetState | null;
  corroboration: Corroboration | null;
  decision: Decision | null;
  requests: EvidenceRequest[];
  graph: EvidenceGraph;
  report: string | null;
  degraded: boolean;
  error: string | null;
}

const initial: RunState = {
  runId: null,
  status: "idle",
  events: [],
  record: null,
  triage: null,
  hypotheses: [],
  planSteps: [],
  toolCalls: [],
  evidence: [],
  budget: null,
  corroboration: null,
  decision: null,
  requests: [],
  graph: { nodes: [], edges: [] },
  report: null,
  degraded: false,
  error: null,
};

function mergeHypotheses(prev: Hypothesis[], next: Hypothesis[]): Hypothesis[] {
  const byId = new Map(prev.map((h) => [h.hypothesis_id, h]));
  for (const h of next) byId.set(h.hypothesis_id, h);
  // Stable order: existing order, then any new ids appended.
  const order = [...prev.map((h) => h.hypothesis_id), ...next.map((h) => h.hypothesis_id)];
  const seen = new Set<string>();
  const out: Hypothesis[] = [];
  for (const id of order) {
    if (seen.has(id)) continue;
    const h = byId.get(id);
    if (h) {
      out.push(h);
      seen.add(id);
    }
  }
  return out;
}

function mergeGraph(prev: EvidenceGraph, nodes: GraphNode[], edges: GraphEdge[]): EvidenceGraph {
  const nodeIds = new Set(prev.nodes.map((n) => n.id));
  const edgeKeys = new Set(prev.edges.map((e) => `${e.source}->${e.target}:${e.relation}`));
  return {
    nodes: [...prev.nodes, ...nodes.filter((n) => !nodeIds.has(n.id))],
    edges: [
      ...prev.edges,
      ...edges.filter((e) => !edgeKeys.has(`${e.source}->${e.target}:${e.relation}`)),
    ],
  };
}

function reducer(state: RunState, ev: InvestigationEvent): RunState {
  const p = ev.payload || {};
  switch (ev.type) {
    case "run_started":
      return { ...state, runId: ev.run_id, status: "streaming" };
    case "case_loaded":
      return { ...state, record: p.record ?? state.record };
    case "triage":
      return { ...state, triage: p.triage ?? state.triage };
    case "hypotheses_updated":
      return { ...state, hypotheses: mergeHypotheses(state.hypotheses, p.hypotheses ?? []) };
    case "plan_step":
      return { ...state, planSteps: [...state.planSteps, p.plan_step] };
    case "tool_call_completed":
      return { ...state, toolCalls: [...state.toolCalls, p.tool_result] };
    case "evidence_added":
      return { ...state, evidence: [...state.evidence, p.evidence] };
    case "graph_updated":
      return {
        ...state,
        graph: mergeGraph(state.graph, p.nodes_added ?? [], p.edges_added ?? []),
      };
    case "budget_updated":
      return { ...state, budget: p.budget ?? state.budget };
    case "corroboration":
      return { ...state, corroboration: p.corroboration ?? state.corroboration };
    case "decision":
      return { ...state, decision: p.decision ?? state.decision };
    case "evidence_requested":
      return { ...state, requests: p.requests ?? [] };
    case "report_ready":
      return {
        ...state,
        report: p.report_markdown ?? state.report,
        status: "done",
        degraded: !!p.result?.meta?.degraded || state.degraded,
      };
    case "run_failed":
      return {
        ...state,
        status: "failed",
        error: p.error ?? "run failed",
        degraded: true,
      };
    default:
      return state;
  }
}

export function useRunStream(runId: string | null) {
  const [state, dispatch] = useReducer(reducer, initial);
  const sourceRef = useRef<EventSource | null>(null);
  const runRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
    runRef.current = null;
  }, []);

  useEffect(() => {
    if (!runId) return;
    if (runRef.current === runId && sourceRef.current) return; // StrictMode guard
    stop();
    runRef.current = runId;
    const es = new EventSource(`/api/runs/${runId}/events`);
    sourceRef.current = es;
    es.onmessage = (msg) => {
      try {
        const ev = JSON.parse(msg.data) as InvestigationEvent;
        dispatch(ev);
        if (ev.type === "report_ready" || ev.type === "run_failed") {
          es.close();
          sourceRef.current = null;
        }
      } catch {
        /* ignore malformed frame */
      }
    };
    es.onerror = () => {
      // Browser will retry with Last-Event-ID; close only if terminal reached.
      if (state.status === "done" || state.status === "failed") {
        es.close();
        sourceRef.current = null;
      }
    };
    return () => {
      es.close();
      sourceRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  return { state, stop };
}
