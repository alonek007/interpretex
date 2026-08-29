import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Play, RotateCcw } from "lucide-react";
import { api } from "../api/client";
import type { Flags, NetworkView } from "../types/contract";
import { useRunStream } from "../hooks/useRunStream";
import { CaseRail } from "./CaseRail";
import { Timeline } from "./Timeline";
import { HypothesisBoard } from "./HypothesisBoard";
import { EvidenceLedger } from "./EvidenceLedger";
import { DecisionPanel } from "./DecisionPanel";
import { BudgetMeter } from "./BudgetMeter";
import { PlanPanel } from "./PlanPanel";
import { Dossier } from "./Dossier";
import { JudgeReveal } from "./JudgeReveal";
import { AttackerPanel } from "./AttackerPanel";
import { EvidenceGraph, NetworkGraphView } from "./Graphs";
import { HonestFooter } from "./HonestFooter";

const TABS = [
  ["hypotheses", "Hypotheses"],
  ["evidence", "Evidence"],
  ["graph", "Graph"],
  ["network", "Network"],
  ["plan", "Plan"],
  ["dossier", "Dossier"],
  ["attack", "Attack"],
  ["reveal", "Reveal"],
] as const;

function RunView({
  runId,
  caseId,
  flags,
}: {
  runId: string;
  caseId: string | null;
  flags: Flags | undefined;
}) {
  const { state } = useRunStream(runId);
  const [tab, setTab] = useState<string>("hypotheses");
  const networkQ = useQuery<NetworkView>({
    queryKey: ["network"],
    queryFn: () => api.network(),
    enabled: tab === "network" && !!flags?.network,
  });

  const visibleTabs = TABS.filter(([t]) => {
    if (t === "network") return !!flags?.network;
    if (t === "attack") return !!flags?.attacker;
    if (t === "plan") return !!flags?.budget;
    return true;
  });

  return (
    <div className="flex flex-col h-full">
      {/* center column */}
      <div className="flex flex-1 min-h-0">
        <div className="flex-1 flex flex-col min-w-0 border-r border-edge">
          <Timeline events={state.events} />
          <DecisionPanel
            decision={state.decision}
            runId={runId}
            degraded={state.degraded}
          />
        </div>

        {/* right inspector */}
        <div className="w-[26rem] shrink-0 flex flex-col bg-panel min-h-0">
          <div className="flex flex-wrap gap-1 p-2 border-b border-edge">
            {visibleTabs.map(([t, label]) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`text-[11px] px-2 py-1 rounded ${
                  tab === t
                    ? "bg-sky-500/20 text-sky-200 border border-sky-500/40"
                    : "text-slate-400 hover:text-slate-200 border border-transparent"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex-1 min-h-0 overflow-auto scroll-thin">
            {tab === "hypotheses" && <HypothesisBoard hypotheses={state.hypotheses} />}
            {tab === "evidence" && <EvidenceLedger evidence={state.evidence} />}
            {tab === "graph" && (
              <EvidenceGraph nodes={state.graph.nodes} edges={state.graph.edges} />
            )}
            {tab === "network" && (
              <NetworkGraphView
                nodes={networkQ.data?.nodes ?? []}
                edges={(networkQ.data?.edges ?? []) as any}
                findings={networkQ.data?.findings ?? []}
              />
            )}
            {tab === "plan" && <PlanPanel steps={state.planSteps} />}
            {tab === "dossier" && <Dossier report={state.report} events={state.events} />}
            {tab === "attack" && <AttackerPanel onAttack={() => {}} />}
            {tab === "reveal" && (
              <JudgeReveal
                caseId={caseId}
                decision={state.decision}
                enabled={state.status === "done"}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function Investigation() {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [budget, setBudget] = useState(6);
  const flagsQ = useQuery<Flags>({ queryKey: ["flags"], queryFn: api.flags });
  const flags = flagsQ.data;

  const investigate = async (id: string) => {
    const r = await api.createRun(id, budget);
    setRunId(r.run_id);
  };

  const onAttack = async (id: string) => {
    setCaseId(id);
    const r = await api.createRun(id, budget);
    setRunId(r.run_id);
  };

  return (
    <div className="flex h-screen flex-col">
      <div className="flex flex-1 min-h-0">
        <CaseRail selected={caseId} onSelect={setCaseId} onAttack={onAttack} />

        <div className="flex-1 flex flex-col min-w-0">
          {/* top bar */}
          <div className="flex items-center gap-3 px-3 py-2 border-b border-edge bg-panel">
            <div className="text-sm font-semibold text-slate-200">Interpretex</div>
            <div className="text-[11px] text-slate-500">
              {caseId ? `case: ${caseId}` : "no case selected"}
            </div>
            <div className="ml-auto flex items-center gap-2">
              {flags?.budget && (
                <select
                  value={budget}
                  onChange={(e) => setBudget(Number(e.target.value))}
                  className="bg-ink border border-edge rounded px-2 py-1 text-xs text-slate-200"
                >
                  {[3, 4, 6, 8, 10].map((b) => (
                    <option key={b} value={b}>
                      budget {b}
                    </option>
                  ))}
                </select>
              )}
              <button
                disabled={!caseId || !!runId}
                onClick={() => caseId && investigate(caseId)}
                className="text-xs rounded-md px-3 py-1.5 flex items-center gap-1 bg-sky-500/20 text-sky-200 border border-sky-500/40 hover:bg-sky-500/30 disabled:opacity-40"
              >
                <Play className="w-3.5 h-3.5" /> Investigate
              </button>
              {runId && (
                <button
                  onClick={() => setRunId(null)}
                  className="text-xs rounded-md px-2 py-1.5 flex items-center gap-1 text-slate-400 border border-edge hover:text-slate-200"
                  title="Reset run"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {runId ? (
            <RunView key={runId} runId={runId} caseId={caseId} flags={flags} />
          ) : (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
              Select a case and press Investigate to watch the reasoning stream.
            </div>
          )}
        </div>
      </div>
      <HonestFooter />
    </div>
  );
}
