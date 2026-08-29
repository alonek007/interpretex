import type { Dimension } from "../types/contract";

// One colour per Dimension, used everywhere (timeline chips, evidence rows,
// graph nodes, corroboration, network). A judge learns "orange = economic" once.
export const DIMENSION_COLOR: Record<Dimension, string> = {
  economic: "#f59e0b",
  physical: "#22d3ee",
  temporal: "#a78bfa",
  documentary: "#34d399",
  behavioural: "#f472b6",
  network: "#fb7185",
};

export const DIMENSION_LABEL: Record<Dimension, string> = {
  economic: "Economic",
  physical: "Physical",
  temporal: "Temporal",
  documentary: "Documentary",
  behavioural: "Behavioural",
  network: "Network",
};

export function dimClass(d: Dimension): string {
  return `dim-${d}`;
}

export function dimColor(d?: Dimension): string {
  return d ? DIMENSION_COLOR[d] : "#64748b";
}

export const VERDICT_COLOR: Record<string, string> = {
  release: "#34d399",
  hold: "#f59e0b",
  escalate: "#fb7185",
};

export const SEVERITY_RING: Record<string, string> = {
  none: "#475569",
  low: "#64748b",
  medium: "#f59e0b",
  high: "#fb7185",
};
