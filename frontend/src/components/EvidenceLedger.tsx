import type { EvidenceItem } from "../types/contract";
import { EvidenceRow } from "./Badges";

export function EvidenceLedger({ evidence }: { evidence: EvidenceItem[] }) {
  const against = evidence.filter((e) => e.stance === "refutes_suspicion");
  const forList = evidence.filter((e) => e.stance === "supports_suspicion");
  const neutral = evidence.filter((e) => e.stance === "neutral");

  return (
    <div className="grid grid-cols-2 gap-2 p-2 h-full overflow-auto scroll-thin">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-rose-300 mb-1">
          For suspicion ({forList.length})
        </div>
        <div className="space-y-2">
          {forList.map((e) => (
            <EvidenceRow key={e.evidence_id} e={e} />
          ))}
        </div>
      </div>
      <div>
        <div className="text-[11px] uppercase tracking-wide text-emerald-300 mb-1">
          Against / benign ({against.length})
        </div>
        <div className="space-y-2">
          {against.length > 0 ? (
            against.map((e) => <EvidenceRow key={e.evidence_id} e={e} />)
          ) : (
            <div className="rounded-md border border-emerald-500/30 bg-emerald-500/5 p-2 text-xs text-emerald-200">
              No refuting evidence found — the following benign explanations were tested and not
              supported.
              {neutral.length > 0 && (
                <ul className="mt-1 list-disc list-inside text-emerald-300/80">
                  {neutral.map((e) => (
                    <li key={e.evidence_id}>{e.statement}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
