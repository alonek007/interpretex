import type { Dimension, EvidenceItem, Severity } from "../types/contract";
import { DIMENSION_LABEL, dimClass } from "../lib/dim";

export function DimensionBadge({ dim }: { dim?: Dimension }) {
  if (!dim) return null;
  return (
    <span className={`text-[11px] px-1.5 py-0.5 rounded ${dimClass(dim)} dim-chip font-medium`}>
      {DIMENSION_LABEL[dim]}
    </span>
  );
}

export function SeverityBadge({ sev }: { sev?: Severity }) {
  const color =
    sev === "high"
      ? "#fb7185"
      : sev === "medium"
      ? "#f59e0b"
      : sev === "low"
      ? "#64748b"
      : "#475569";
  return (
    <span
      className="text-[11px] px-1.5 py-0.5 rounded font-medium"
      style={{ background: `${color}22`, color, border: `1px solid ${color}66` }}
    >
      {sev ?? "none"}
    </span>
  );
}

export function ToolChip({ tool }: { tool: string }) {
  return (
    <span className="text-[11px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/30 font-mono">
      {tool}
    </span>
  );
}

export function EvidenceRow({ e }: { e: EvidenceItem }) {
  return (
    <div className="rounded-md border border-edge bg-panel2 p-2 fade-in">
      <div className="flex items-center gap-2 flex-wrap">
        <DimensionBadge dim={e.dimension} />
        <SeverityBadge sev={e.severity} />
        <span className="text-[11px] text-slate-400">
          w={e.weight.toFixed(2)} · {e.evidence_id}
        </span>
      </div>
      <div className="mt-1 text-sm text-slate-200">{e.statement}</div>
      {e.interpretation && (
        <div className="mt-1 text-xs text-slate-400 italic">{e.interpretation}</div>
      )}
      {e.sources?.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {e.sources.map((s, i) => (
            <span key={i} className="text-[10px] text-slate-500 font-mono">
              {s.kind} · {s.ref}
              {s.value ? ` · ${s.value}` : ""}
              {s.as_of ? ` · ${s.as_of}` : ""}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
