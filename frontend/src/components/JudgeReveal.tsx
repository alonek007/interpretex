import { useState } from "react";
import { Eye } from "lucide-react";
import type { AnomalyKind, CaseLabel, Decision, Dimension, Verdict } from "../types/contract";
import { api } from "../api/client";

const ANOMALY_DIM: Record<AnomalyKind, Dimension> = {
  under_invoicing: "economic",
  over_invoicing: "economic",
  capacity_exceeded: "physical",
  impossible_transit: "temporal",
  insurance_after_shipment: "documentary",
  description_drift: "documentary",
  quantity_mismatch: "physical",
  hs_code_mismatch: "documentary",
  route_deviation: "temporal",
  historical_deviation: "behavioural",
  intermediary_reuse: "network",
  shared_ownership: "network",
  none: "economic",
};

export function JudgeReveal({
  caseId,
  decision,
  enabled,
}: {
  caseId: string | null;
  decision: Decision | null;
  enabled: boolean;
}) {
  const [label, setLabel] = useState<CaseLabel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reveal = async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const l = await api.label(caseId);
      setLabel(l);
    } catch (e: any) {
      setError(e?.status === 409 ? "Label locked until a run completes." : String(e));
    } finally {
      setLoading(false);
    }
  };

  const agentDims = new Set<Dimension>([
    ...(decision?.corroboration.corroborated_dimensions ?? []),
  ]);

  return (
    <div className="p-3 space-y-2">
      <button
        disabled={!enabled || loading}
        onClick={reveal}
        className={`w-full text-xs rounded-md py-2 flex items-center justify-center gap-2 ${
          enabled
            ? "bg-indigo-500/20 text-indigo-200 border border-indigo-500/40 hover:bg-indigo-500/30"
            : "bg-panel2 text-slate-600 border border-edge cursor-not-allowed"
        }`}
      >
        <Eye className="w-3.5 h-3.5" />
        {enabled ? "Reveal ground truth" : "Run must complete first"}
      </button>

      {error && <div className="text-[11px] text-rose-300">{error}</div>}

      {label && (
        <div className="space-y-2 fade-in">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Class:</span>
            <span className="text-slate-100 font-medium">{label.case_class}</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Expected:</span>
            <span className="font-medium">{label.expected_verdict.toUpperCase()}</span>
            <span className="text-slate-500">· agent:</span>
            <span className="font-medium">
              {(decision?.verdict ?? "—").toUpperCase() as Verdict | "—"}
            </span>
            <span
              className={
                label.expected_verdict === decision?.verdict
                  ? "text-emerald-300"
                  : "text-amber-300"
              }
            >
              {label.expected_verdict === decision?.verdict ? "✓ match" : "≠ differs"}
            </span>
          </div>

          <div className="text-[11px] uppercase tracking-wide text-slate-500">
            Injected vs found
          </div>
          <ul className="space-y-1">
            {label.injected_anomalies.map((a) => {
              const found = agentDims.has(ANOMALY_DIM[a]);
              return (
                <li
                  key={a}
                  className="flex items-center gap-2 text-[11px] text-slate-300"
                >
                  <span className={found ? "text-emerald-300" : "text-amber-300"}>
                    {found ? "✓" : "?"}
                  </span>
                  <span className="font-mono">{a}</span>
                  <span className="text-slate-500">→ {ANOMALY_DIM[a]}</span>
                </li>
              );
            })}
          </ul>

          {label.benign_explanation && (
            <div className="text-[11px] text-emerald-200">
              <b>Benign:</b> {label.benign_explanation}
            </div>
          )}
          {label.evasion_notes && (
            <div className="text-[11px] text-slate-400">
              <b>Evasion:</b> {label.evasion_notes}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
