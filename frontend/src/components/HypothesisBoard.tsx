import type { Hypothesis } from "../types/contract";

const STATUS_COLOR: Record<string, string> = {
  open: "#64748b",
  supported: "#fb7185",
  weakened: "#f59e0b",
  refuted: "#34d399",
  untestable: "#475569",
};

export function HypothesisBoard({ hypotheses }: { hypotheses: Hypothesis[] }) {
  if (!hypotheses.length) {
    return <div className="text-xs text-slate-500 p-3">No hypotheses yet.</div>;
  }
  return (
    <div className="space-y-2 p-2">
      {hypotheses.map((h) => {
        const color = STATUS_COLOR[h.status] ?? "#64748b";
        return (
          <div
            key={h.hypothesis_id}
            className="rounded-md border border-edge bg-panel2 p-2 fade-in"
          >
            <div className="flex items-center gap-2">
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                  h.kind === "benign"
                    ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                    : "bg-rose-500/15 text-rose-300 border border-rose-500/30"
                }`}
              >
                {h.kind === "benign" ? "BENIGN" : "SUSPICIOUS"}
              </span>
              <span className="text-[11px] text-slate-400">{h.hypothesis_id}</span>
              <span
                className="text-[10px] px-1.5 py-0.5 rounded ml-auto"
                style={{ background: `${color}22`, color, border: `1px solid ${color}66` }}
              >
                {h.status}
              </span>
            </div>
            <div className="text-sm text-slate-200 mt-1">{h.statement}</div>
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] text-slate-500">
                prior {h.prior.toFixed(2)} → posterior
              </span>
              <div className="flex-1 h-1.5 rounded bg-ink overflow-hidden">
                <div
                  className="h-full bg-sky-400 transition-all"
                  style={{ width: `${Math.round(h.posterior * 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-slate-300 w-10 text-right">
                {h.posterior.toFixed(2)}
              </span>
            </div>
            {h.rationale && (
              <div className="text-[11px] text-slate-400 mt-1 italic">{h.rationale}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}
