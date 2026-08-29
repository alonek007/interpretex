import { useState } from "react";
import { api } from "../api/client";

const KNOWN_THRESHOLDS = {
  price_deviation_pct: 0.3,
  capacity_utilisation: 1.0,
  insurance_lag_days: 3,
};

export function AttackerPanel({ onAttack }: { onAttack: (caseId: string) => void }) {
  const [maxDim, setMaxDim] = useState(2);
  const [stealth, setStealth] = useState(0.8);
  const [seed, setSeed] = useState(1);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await api.attack({ max_dimensions: maxDim, target_stealth: stealth, seed });
      onAttack(r.case_id);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-3 space-y-3">
      <div className="text-[11px] text-slate-400">
        Craft an evasive case that sits inside every individual threshold — it must be caught by
        correlation, not by any single check.
      </div>
      <label className="block text-[11px] text-slate-400">
        max dimensions: {maxDim}
        <input
          type="range"
          min={1}
          max={4}
          value={maxDim}
          onChange={(e) => setMaxDim(Number(e.target.value))}
          className="w-full"
        />
      </label>
      <label className="block text-[11px] text-slate-400">
        target stealth: {stealth}
        <input
          type="range"
          min={0.3}
          max={0.95}
          step={0.05}
          value={stealth}
          onChange={(e) => setStealth(Number(e.target.value))}
          className="w-full"
        />
      </label>
      <label className="block text-[11px] text-slate-400">
        seed
        <input
          type="number"
          value={seed}
          onChange={(e) => setSeed(Number(e.target.value))}
          className="w-full bg-ink border border-edge rounded px-2 py-1 text-slate-200"
        />
      </label>
      <div className="text-[10px] text-slate-500 uppercase tracking-wide">Known thresholds (read-only)</div>
      <ul className="text-[10px] text-slate-500 font-mono">
        {Object.entries(KNOWN_THRESHOLDS).map(([k, v]) => (
          <li key={k}>
            {k} = {v}
          </li>
        ))}
      </ul>
      <button
        disabled={busy}
        onClick={submit}
        className="w-full text-xs rounded-md border border-fuchsia-500/40 bg-fuchsia-500/10 text-fuchsia-200 py-2 hover:bg-fuchsia-500/20 disabled:opacity-50"
      >
        {busy ? "Generating…" : "Generate & investigate"}
      </button>
    </div>
  );
}
