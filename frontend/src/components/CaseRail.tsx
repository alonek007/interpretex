import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { CaseSummary } from "../types/contract";

export function CaseRail({
  selected,
  onSelect,
  onAttack,
}: {
  selected: string | null;
  onSelect: (id: string) => void;
  onAttack: (id: string) => void;
}) {
  const { data, isLoading } = useQuery({ queryKey: ["cases"], queryFn: api.cases });
  const [adv, setAdv] = useState<string | null>(null);
  const advCase = data?.find((c) => c.case_id === adv);

  return (
    <div className="w-72 shrink-0 border-r border-edge bg-panel flex flex-col">
      <div className="px-3 py-3 border-b border-edge">
        <div className="text-sm font-semibold text-slate-200">Cases</div>
        <div className="text-[11px] text-slate-500">Pick a case, then Investigate.</div>
      </div>
      <div className="flex-1 overflow-auto scroll-thin p-2 space-y-2">
        {isLoading && <div className="text-xs text-slate-500 p-2">Loading…</div>}
        {data?.map((c: CaseSummary) => (
          <button
            key={c.case_id}
            onClick={() => onSelect(c.case_id)}
            className={`w-full text-left rounded-md border p-2 transition ${
              selected === c.case_id
                ? "border-sky-500 bg-sky-500/10"
                : "border-edge bg-panel2 hover:border-slate-600"
            }`}
          >
            <div className="text-sm font-medium text-slate-100">{c.title}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              {c.commodity} · {c.quantity} {c.unit}
            </div>
            <div className="text-[11px] text-slate-400">
              {c.total_value.toLocaleString()} {c.currency} · {c.exporter_name} → {c.importer_name}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">
              {c.document_count} docs · {c.case_id}
            </div>
          </button>
        ))}
      </div>
      <div className="p-2 border-t border-edge space-y-2">
        <button
          onClick={async () => {
            const r = await api.attack({ seed: Math.floor(Math.random() * 1000) });
            setAdv(r.case_id);
            onAttack(r.case_id);
          }}
          className="w-full text-xs rounded-md border border-fuchsia-500/40 bg-fuchsia-500/10 text-fuchsia-300 py-1.5 hover:bg-fuchsia-500/20"
        >
          Generate adversarial case
        </button>
        {advCase && (
          <div className="text-[10px] text-slate-500">
            Last generated: {advCase.case_id} — investigating…
          </div>
        )}
      </div>
    </div>
  );
}
