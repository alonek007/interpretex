import { useEffect, useRef, useState } from "react";
import type { InvestigationEvent } from "../types/contract";
import { DimensionBadge, SeverityBadge, ToolChip } from "./Badges";

const TYPE_LABEL: Record<string, string> = {
  run_started: "Start",
  case_loaded: "Case",
  triage: "Triage",
  hypotheses_updated: "Hypotheses",
  plan_step: "Plan",
  tool_call_started: "Tool ▶",
  tool_call_completed: "Tool ■",
  evidence_added: "Evidence",
  graph_updated: "Graph",
  budget_updated: "Budget",
  corroboration: "Corroboration",
  decision: "Decision",
  evidence_requested: "Requests",
  report_ready: "Report",
  run_failed: "Failed",
  heartbeat: "♥",
};

function Row({ ev }: { ev: InvestigationEvent }) {
  const [open, setOpen] = useState(false);
  const p = ev.payload || {};
  return (
    <div className="px-3 py-1.5 border-b border-edge/60 hover:bg-panel2/50">
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-slate-600 w-8 shrink-0">#{ev.seq}</span>
        <span className="text-[10px] uppercase tracking-wide text-slate-500 w-24 shrink-0">
          {TYPE_LABEL[ev.type] ?? ev.type}
        </span>
        {ev.type === "tool_call_started" && <ToolChip tool={p.tool} />}
        {ev.type === "tool_call_completed" && <ToolChip tool={p.tool_result?.tool} />}
        {ev.type === "evidence_added" && (
          <>
            <DimensionBadge dim={p.evidence?.dimension} />
            <SeverityBadge sev={p.evidence?.severity} />
          </>
        )}
        <button
          className="ml-auto text-[10px] text-slate-500 hover:text-slate-300"
          onClick={() => setOpen((o) => !o)}
        >
          {open ? "hide" : "payload"}
        </button>
      </div>
      <div className="text-sm text-slate-200 mt-0.5">{ev.narration}</div>
      {open && (
        <pre className="mt-1 text-[10px] text-slate-400 bg-ink rounded p-2 overflow-auto scroll-thin max-h-48">
          {JSON.stringify(p, null, 2)}
        </pre>
      )}
    </div>
  );
}

export function Timeline({ events }: { events: InvestigationEvent[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events.length]);

  return (
    <div className="flex-1 overflow-auto scroll-thin bg-panel">
      {events.length === 0 && (
        <div className="p-4 text-xs text-slate-500">No events yet. Start an investigation.</div>
      )}
      {events.map((ev) => (
        <Row key={ev.seq} ev={ev} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
