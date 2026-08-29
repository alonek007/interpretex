import type { BudgetState } from "../types/contract";

export function BudgetMeter({ budget }: { budget: BudgetState | null }) {
  if (!budget) return <div className="text-xs text-slate-500 p-3">No budget data.</div>;
  const pct = (v: number, total: number) => (total ? Math.round((v / total) * 100) : 0);
  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center justify-between text-xs text-slate-300">
        <span>
          Spent <b className="text-slate-100">{budget.spent}</b> / {budget.limit}
        </span>
        <span className="text-slate-500">exhaustive: {budget.exhaustive_cost}</span>
      </div>
      <div className="flex h-3 rounded overflow-hidden bg-ink">
        <div
          className="bg-sky-400"
          style={{ width: `${pct(budget.spent, budget.exhaustive_cost)}%` }}
          title="agent spend"
        />
        <div
          className="bg-slate-600/40"
          style={{
            width: `${pct(budget.exhaustive_cost - budget.spent, budget.exhaustive_cost)}%`,
          }}
          title="exhaustive ghost"
        />
      </div>
      <div className="text-[11px] text-slate-400">
        Reached the same verdict spending <b>{budget.spent}</b> units instead of{" "}
        <b>{budget.exhaustive_cost}</b>.
      </div>
      {budget.tools_skipped?.length > 0 && (
        <div className="mt-1">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Skipped</div>
          <ul className="text-[11px] text-slate-400 list-disc list-inside">
            {budget.tools_skipped.map((s) => (
              <li key={s.tool}>
                <span className="font-mono text-slate-300">{s.tool}</span> — {s.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
