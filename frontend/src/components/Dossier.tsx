import ReactMarkdown from "react-markdown";
import type { InvestigationEvent } from "../types/contract";

export function Dossier({ report, events }: { report: string | null; events: InvestigationEvent[] }) {
  const md = report ?? events.find((e) => e.type === "report_ready")?.payload?.report_markdown;
  if (!md) return <div className="text-xs text-slate-500 p-3">Dossier not ready.</div>;
  return (
    <div className="p-4 overflow-auto scroll-thin h-full prose prose-invert prose-sm max-w-none">
      <ReactMarkdown>{md}</ReactMarkdown>
    </div>
  );
}
