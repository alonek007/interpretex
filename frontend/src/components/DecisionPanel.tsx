import { Download } from "lucide-react";
import type { Decision } from "../types/contract";
import { VERDICT_COLOR } from "../lib/dim";
import { api } from "../api/client";

export function DecisionPanel({
  decision,
  runId,
  degraded,
}: {
  decision: Decision | null;
  runId: string | null;
  degraded: boolean;
}) {
  if (!decision) {
    return <div className="text-xs text-slate-500 p-3">Awaiting decision…</div>;
  }
  const color = VERDICT_COLOR[decision.verdict] ?? "#64748b";
  return (
    <div className="border-t-2 p-3" style={{ borderColor: color }}>
      <div
        className="rounded-md px-3 py-2 flex items-center gap-3"
        style={{ background: `${color}1f`, border: `1px solid ${color}` }}
      >
        <span className="text-2xl font-bold" style={{ color }}>
          {decision.verdict.toUpperCase()}
        </span>
        <div className="text-xs text-slate-300">
          confidence {(decision.confidence * 100).toFixed(0)}%
        </div>
        {degraded && (
          <span className="ml-auto text-[10px] text-amber-300 border border-amber-400/40 rounded px-1.5 py-0.5">
            reasoning produced without model inference
          </span>
        )}
      </div>
      <div className="text-sm font-medium text-slate-100 mt-2">{decision.headline}</div>
      <div className="text-xs text-slate-300 mt-1">{decision.rationale}</div>

      <div className="flex flex-wrap gap-1 mt-2">
        {decision.corroboration.corroborated_dimensions.map((d) => (
          <span
            key={d}
            className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/30"
          >
            {d}
          </span>
        ))}
      </div>

      {decision.typology && (
        <div className="text-[11px] text-slate-400 mt-1">Typology: {decision.typology}</div>
      )}

      {decision.caveats?.length > 0 && (
        <ul className="mt-1 text-[11px] text-slate-400 list-disc list-inside">
          {decision.caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}

      {runId && (
        <a
          href={api.reportURL(runId)}
          className="mt-2 inline-flex items-center gap-1 text-[11px] text-sky-300 hover:text-sky-200"
        >
          <Download className="w-3 h-3" /> Download dossier (.md)
        </a>
      )}
    </div>
  );
}
