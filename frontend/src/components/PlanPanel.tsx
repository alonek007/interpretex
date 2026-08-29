import type { PlanStep } from "../types/contract";
import { ToolChip } from "./Badges";

export function PlanPanel({ steps }: { steps: PlanStep[] }) {
  if (!steps.length) return <div className="text-xs text-slate-500 p-3">No plan steps yet.</div>;
  return (
    <div className="space-y-2 p-2">
      {steps.map((s) => (
        <div key={s.step} className="rounded-md border border-edge bg-panel2 p-2 fade-in">
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-500">step {s.step}</span>
            {s.chosen_tool && <ToolChip tool={s.chosen_tool} />}
            <span className="text-[11px] text-slate-500">
              gain {s.expected_information_gain.toFixed(2)}
            </span>
          </div>
          <div className="text-sm text-slate-200 mt-0.5">{s.reasoning}</div>
          {s.considered?.length > 0 && (
            <div className="mt-1">
              <div className="text-[10px] uppercase tracking-wide text-slate-500">
                Rejected alternatives
              </div>
              <ul className="text-[11px] text-slate-400 list-disc list-inside">
                {s.considered.map((c, i) => (
                  <li key={i}>
                    <span className="font-mono text-slate-300">{c.tool}</span> — {c.why_not}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {s.stop_reason && (
            <div className="text-[10px] text-amber-300/80 mt-1">stop: {s.stop_reason}</div>
          )}
        </div>
      ))}
    </div>
  );
}
