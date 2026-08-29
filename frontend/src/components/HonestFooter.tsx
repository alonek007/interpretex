import { ShieldCheck } from "lucide-react";

export function HonestFooter() {
  return (
    <div className="text-[11px] text-slate-500 border-t border-edge px-3 py-2 bg-panel2">
      <ShieldCheck className="inline w-3 h-3 mr-1 -mt-0.5 text-slate-500" />
      Prototype. Synthetic trade data and controlled reference sources. Decision support for a
      human reviewer, not an automated compliance determination.
    </div>
  );
}
