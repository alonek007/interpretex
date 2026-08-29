import type {
  AttackSpec,
  Baseline,
  CaseLabel,
  CaseSummary,
  Flags,
  Health,
  InvestigationResult,
  NetworkView,
  ToolSpec,
} from "../types/contract";

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (r.status === 409) {
    // Label gate — expected before a completed run.
    throw { status: 409, body: await r.json().catch(() => ({})) };
  }
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`HTTP ${r.status}: ${text}`);
  }
  return (await r.json()) as T;
}

export const api = {
  health: () => getJSON<Health>("/api/health"),
  flags: () => getJSON<Flags>("/api/flags"),
  tools: () => getJSON<ToolSpec[]>("/api/tools"),
  cases: () => getJSON<CaseSummary[]>("/api/cases"),
  case: (id: string) => getJSON<any>(`/api/cases/${id}`),
  document: (id: string, docId: string) =>
    getJSON<any>(`/api/cases/${id}/documents/${docId}`),
  label: (id: string) => getJSON<CaseLabel>(`/api/cases/${id}/label`),
  network: (entityId?: string, depth = 2) =>
    getJSON<NetworkView>(
      `/api/network?${new URLSearchParams(
        entityId ? { entity_id: entityId, depth: String(depth) } : { depth: String(depth) }
      )}`
    ),
  attack: (spec: AttackSpec) =>
    fetch("/api/attack", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(spec),
    }).then(async (r) => {
      if (!r.ok) throw new Error(await r.text());
      return (await r.json()) as { case_id: string };
    }),
  createRun: (caseId: string, budget?: number, mode = "live", seed?: number) =>
    fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_id: caseId, budget, mode, seed }),
    }).then(async (r) => {
      if (!r.ok) throw new Error(await r.text());
      return (await r.json()) as { run_id: string };
    }),
  runResult: (runId: string) => getJSON<InvestigationResult>(`/api/runs/${runId}`),
  baseline: (runId: string) => getJSON<Baseline>(`/api/runs/${runId}/baseline`),
  reportURL: (runId: string) => `/api/runs/${runId}/report.md`,
  eventsURL: (runId: string) => `/api/runs/${runId}/events`,
};
