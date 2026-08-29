// Hand-written mirrors of interpretex_contracts (1.0.0). Field names are
// byte-identical to the Python models. Keep them in sync manually.

export type Dimension =
  | "economic"
  | "physical"
  | "temporal"
  | "documentary"
  | "behavioural"
  | "network";

export type Severity = "none" | "low" | "medium" | "high";
export type Stance = "supports_suspicion" | "refutes_suspicion" | "neutral";
export type HypothesisKind = "benign" | "suspicious";
export type HypothesisStatus =
  | "open"
  | "supported"
  | "weakened"
  | "refuted"
  | "untestable";
export type Verdict = "release" | "hold" | "escalate";
export type SourceKind = "document" | "reference_db" | "derived" | "model";
export type CaseClass = "clean" | "suspicious_but_legitimate" | "illicit" | "adversarial";
export type AnomalyKind =
  | "under_invoicing"
  | "over_invoicing"
  | "capacity_exceeded"
  | "impossible_transit"
  | "insurance_after_shipment"
  | "description_drift"
  | "quantity_mismatch"
  | "hs_code_mismatch"
  | "route_deviation"
  | "historical_deviation"
  | "intermediary_reuse"
  | "shared_ownership"
  | "none";

export type EventType =
  | "run_started"
  | "case_loaded"
  | "triage"
  | "hypotheses_updated"
  | "plan_step"
  | "tool_call_started"
  | "tool_call_completed"
  | "evidence_added"
  | "graph_updated"
  | "budget_updated"
  | "corroboration"
  | "decision"
  | "evidence_requested"
  | "report_ready"
  | "run_failed"
  | "heartbeat";

export interface SourceRef {
  kind: SourceKind;
  ref: string;
  value?: string;
  as_of?: string;
  label?: string;
}

export interface Observation {
  observation_id: string;
  dimension: Dimension;
  statement: string;
  severity: Severity;
  metrics: Record<string, number>;
  sources: SourceRef[];
  expected_range?: string;
}

export interface ToolSpec {
  name: string;
  description: string;
  dimensions: Dimension[];
  args_schema: Record<string, unknown>;
  cost_units: number;
  discriminates: string[];
}

export interface ToolResult {
  tool: string;
  call_id: string;
  args: Record<string, unknown>;
  ok: boolean;
  summary: string;
  observations: Observation[];
  raw: Record<string, unknown>;
  sources: SourceRef[];
  cost_units: number;
  latency_ms: number;
  error?: string;
}

export interface Hypothesis {
  hypothesis_id: string;
  kind: HypothesisKind;
  statement: string;
  explains: Dimension[];
  prior: number;
  posterior: number;
  status: HypothesisStatus;
  discriminating_evidence_needed: string[];
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  rationale?: string;
}

export interface EvidenceItem {
  evidence_id: string;
  dimension: Dimension;
  stance: Stance;
  statement: string;
  weight: number;
  severity: Severity;
  hypotheses_affected: string[];
  observation_ids: string[];
  tool_call_id?: string;
  sources: SourceRef[];
  interpretation?: string;
}

export interface Corroboration {
  corroborated_dimensions: Dimension[];
  independent_signal_count: number;
  refuting_dimensions: Dimension[];
  strongest_benign_hypothesis?: string;
  strongest_benign_posterior: number;
  narrative: string;
}

export interface Decision {
  verdict: Verdict;
  confidence: number;
  headline: string;
  rationale: string;
  corroboration: Corroboration;
  typology?: string;
  caveats: string[];
  decisive_evidence_ids: string[];
}

export interface EvidenceRequest {
  item: string;
  why: string;
  resolves_hypotheses: string[];
  priority: number;
}

export type GraphNodeKind =
  | "document"
  | "field"
  | "reference"
  | "tool"
  | "finding"
  | "dimension"
  | "hypothesis"
  | "decision"
  | "entity"
  | "vessel";

export interface GraphNode {
  id: string;
  kind: GraphNodeKind;
  label: string;
  dimension?: Dimension;
  stance?: Stance;
  severity?: Severity;
  meta: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation:
    | "states"
    | "compared_with"
    | "produced"
    | "supports"
    | "refutes"
    | "corroborates"
    | "concludes"
    | "linked_to";
  label?: string;
}

export interface EvidenceGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface NetworkFinding {
  finding_id: string;
  pattern:
    | "intermediary_reuse"
    | "shared_ownership"
    | "vessel_reuse"
    | "circular_trade"
    | "price_pattern";
  statement: string;
  entity_ids: string[];
  case_ids: string[];
  severity: Severity;
  metrics: Record<string, number>;
}

export interface NetworkNode {
  id: string;
  label: string;
  kind: "entity" | "vessel" | "case";
  country?: string;
  role?: string;
  sanctions_status?: string;
  meta: Record<string, unknown>;
}

export interface NetworkEdge {
  source: string;
  target: string;
  relation: string;
  label?: string;
}

export interface NetworkView {
  focus_entity_id?: string;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  findings: NetworkFinding[];
}

export interface Triage {
  trade_narrative: string;
  initial_concerns: string[];
  unknowns: string[];
  dimensions_to_probe: Dimension[];
}

export interface PlanStep {
  step: number;
  reasoning: string;
  chosen_tool?: string;
  chosen_args: Record<string, unknown>;
  targets_hypotheses: string[];
  expected_information_gain: number;
  considered: { tool: string; expected_information_gain: number; why_not: string }[];
  stop_reason?: "sufficient_evidence" | "budget_exhausted" | "no_informative_tool_left";
}

export interface SkippedTool {
  tool: string;
  reason: string;
}

export interface BudgetState {
  limit: number;
  spent: number;
  remaining: number;
  calls_made: number;
  tools_skipped: SkippedTool[];
  exhaustive_cost: number;
}

export interface RunMeta {
  run_id: string;
  case_id: string;
  started_at: string;
  finished_at?: string;
  model: string;
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  wall_ms: number;
  replayed: boolean;
  degraded: boolean;
}

export interface InvestigationResult {
  meta: RunMeta;
  record: Record<string, unknown>;
  triage: Triage;
  hypotheses: Hypothesis[];
  plan_steps: PlanStep[];
  tool_calls: ToolResult[];
  evidence_for: EvidenceItem[];
  evidence_against: EvidenceItem[];
  evidence_neutral: EvidenceItem[];
  budget: BudgetState;
  graph: EvidenceGraph;
  decision: Decision;
  evidence_requests: EvidenceRequest[];
  report_markdown: string;
  events: InvestigationEvent[];
}

export interface InvestigationEvent {
  seq: number;
  ts: string;
  run_id: string;
  type: EventType;
  narration: string;
  payload: Record<string, any>;
}

export interface CaseSummary {
  case_id: string;
  title: string;
  commodity: string;
  quantity: number;
  unit: string;
  total_value: number;
  currency: string;
  exporter_name: string;
  importer_name: string;
  origin_port?: string;
  destination_port?: string;
  document_count: number;
  received_at: string;
  is_adversarial: boolean;
}

export interface CaseLabel {
  case_class: CaseClass;
  injected_anomalies: AnomalyKind[];
  expected_verdict: Verdict;
  benign_explanation?: string;
  evasion_notes?: string;
  generator_seed?: number;
}

export interface Flags {
  budget: boolean;
  attacker: boolean;
  network: boolean;
  history: boolean;
  replay: boolean;
}

export interface Health {
  status: string;
  contract_version: string;
  model: string;
  flags: Flags;
  world: string;
  agent: string;
}

export interface Baseline {
  agent_cost: number;
  exhaustive_cost: number;
  agent_verdict: Verdict;
  baseline_verdict: Verdict;
  tools_skipped: SkippedTool[];
  signal_count: number;
}

export interface AttackSpec {
  max_dimensions?: number;
  target_stealth?: number;
  seed?: number;
}
