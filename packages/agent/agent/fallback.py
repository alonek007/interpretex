"""The deterministic fallback: no-LLM investigation path.

Runs when llm=None, when LLMError/LLMJsonError escapes the repair loop, or
when any structured call returns something unusable. Degrade per stage, not
globally: each helper below replaces exactly one LLM stage. The full path
still produces a valid InvestigationResult with meta.degraded=true.

Stance rules (frozen):
  - supports_suspicion when severity >= medium and no supporting benign
    finding exists in the same dimension;
  - refutes_suspicion when a tool explicitly found supporting evidence for a
    benign claim;
  - else neutral.
"""
from __future__ import annotations

from typing import Any

from interpretex_contracts import (
    AgentCaseView,
    Dimension,
    EvidenceItem,
    Hypothesis,
    HypothesisKind,
    HypothesisStatus,
    Severity,
    SourceKind,
    SourceRef,
    Stance,
    ToolResult,
    ToolSpec,
    Triage,
)

from . import hypotheses as hyp_mod
from . import planner as planner_mod

_MEDIUM = (Severity.medium, Severity.high)


def fallback_triage(case: AgentCaseView, specs: list[ToolSpec]) -> Triage:
    r = case.record
    narrative = (
        f"The case presents a {r.commodity} shipment of {r.quantity} {r.unit} at "
        f"{r.unit_price} {r.currency} per {r.unit} from {r.exporter_id} to {r.importer_id}"
        + (f" via {r.vessel_name}" if r.vessel_name else "")
        + f" with {len(case.documents)} documents on file."
    )
    concerns: list[str] = []
    if r.insurance_issue_date and r.ship_date and r.insurance_issue_date > r.ship_date:
        concerns.append(
            f"Insurance was issued on {r.insurance_issue_date}, after the shipment date "
            f"{r.ship_date}."
        )
    if r.ship_date and r.arrival_date:
        concerns.append(
            f"The claimed transit from {r.origin_port or 'origin'} to "
            f"{r.destination_port or 'destination'} ({r.ship_date} -> {r.arrival_date}) cannot be "
            f"judged from paper alone."
        )
    if r.vessel_name and not r.gross_weight_tons:
        concerns.append("Vessel capacity cannot be assessed without a gross weight figure.")
    if r.broker_id:
        concerns.append(f"The role and history of broker {r.broker_id} cannot be judged from the file.")
    if not concerns:
        concerns.append("The documents on their face are consistent; market and history checks are still unverified.")
    unknowns = [
        "The market price of the commodity around the shipment date",
        "The vessel's registered cargo capacity",
        "The feasible transit time between the ports at the vessel's speed",
        "The customer's own historical prices and quantities",
        "Whether the counterparties or intermediaries recur in other cases",
    ]
    dims = [Dimension.economic, Dimension.documentary]
    if r.vessel_name:
        dims += [Dimension.physical, Dimension.temporal]
    if r.broker_id and any(s.name == "check_counterparty_network" for s in specs):
        dims += [Dimension.network, Dimension.behavioural]
    return Triage(
        trade_narrative=narrative,
        initial_concerns=concerns[:6],
        unknowns=unknowns[:6],
        dimensions_to_probe=dims,
    )


def fallback_hypotheses(triage: Triage) -> tuple[list[Hypothesis], list[str]]:
    """Catalogue hypotheses for every flagged dimension + catch-alls."""
    return hyp_mod.ensure_balance([], triage)


# ------------------------------------------------------------ benign-signal rules

def _metric(obs: Any, key: str) -> float | None:
    for k, v in obs.metrics.items():
        if key in k.lower():
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def benign_signal(tool_result: ToolResult, obs: Any) -> bool:
    """Did the tool explicitly find evidence FOR a benign claim?"""
    # trust the structured flag first — prose heuristics are the fallback
    if tool_result.tool == "check_contract_or_supporting_evidence":
        found = tool_result.raw.get("found", tool_result.raw.get("claim_found"))
        if found is not None:
            return tool_result.ok and bool(found)
        text = (obs.statement + " " + tool_result.summary).lower()
        return tool_result.ok and ("found" in text and "not found" not in text and "not-found" not in text
                                   and "no document" not in text)
    text = (obs.statement + " " + tool_result.summary).lower()
    if tool_result.tool == "check_historical_trade":
        z = _metric(obs, "z")
        if z is not None:
            return abs(z) <= 1.0
        return "within" in text or "consistent with" in text
    if tool_result.tool == "check_document_consistency":
        mism = _metric(obs, "mismatch")
        if mism is not None:
            return mism == 0
        return "consistent" in text or "no mismatch" in text or "agree" in text
    if tool_result.tool == "check_transit_plausibility":
        util = _metric(obs, "utilisation")
        if util is not None:
            return util <= 1.0
        return "within" in text or "plausible" in text
    if tool_result.tool == "check_vessel_capacity":
        util = _metric(obs, "utilisation")
        if util is not None:
            return util <= 0.95
        return "within" in text or "under capacity" in text
    if tool_result.tool == "check_price_benchmark":
        dev = _metric(obs, "deviation")
        if dev is not None:
            return abs(dev) <= 5.0
        return "within" in text
    return False


def fallback_interpret(
    hypotheses: list[Hypothesis],
    tool_result: ToolResult,
    evidence_so_far: list[EvidenceItem],
    next_id: int,
) -> tuple[list[EvidenceItem], list[dict[str, Any]]]:
    """Rule-based stance assignment + deterministic posterior moves."""
    items: list[EvidenceItem] = []
    seen_keys = {(e.dimension.value, tuple(sorted(e.observation_ids))) for e in evidence_so_far}
    # dimensions in which a benign finding has ALREADY been recorded (a
    # refutes_suspicion item or a benign observation earlier in this result)
    benign_dims = {
        e.dimension.value for e in evidence_so_far if e.stance == Stance.refutes_suspicion
    }

    for obs in tool_result.observations:
        key = (obs.dimension.value, (obs.observation_id,))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        benign = tool_result.ok and benign_signal(tool_result, obs)
        if benign:
            stance, weight = Stance.refutes_suspicion, 0.65
            interp = "The tool explicitly found support for a benign explanation; this weighs against suspicion."
        elif obs.severity in _MEDIUM and obs.dimension.value not in benign_dims:
            stance = Stance.supports_suspicion
            weight = 0.75 if obs.severity == Severity.high else 0.55
            interp = "No benign explanation currently covers this elevated deviation."
        else:
            stance, weight = Stance.neutral, 0.3
            interp = "The observation is neither elevated nor explained; it does not move the decision."
        affected = [h.hypothesis_id for h in hypotheses if obs.dimension in h.explains]
        sources = list(obs.sources) or list(tool_result.sources) or [
            SourceRef(kind=SourceKind.derived, ref=f"{tool_result.tool}:result",
                      label=f"output of {tool_result.tool}")
        ]
        items.append(EvidenceItem(
            evidence_id=f"E{next_id + len(items)}",
            dimension=obs.dimension,
            stance=stance,
            statement=obs.statement,
            weight=weight,
            severity=obs.severity,
            hypotheses_affected=affected,
            observation_ids=[obs.observation_id],
            tool_call_id=tool_result.call_id,
            sources=sources,
            interpretation=interp,
        ))

    updates: list[dict[str, Any]] = []
    for ev in items:
        for h in hypotheses:
            if h.hypothesis_id not in ev.hypotheses_affected:
                continue
            delta = 0.2 * ev.weight
            if ev.stance == Stance.refutes_suspicion:
                new_post = h.posterior + delta if h.kind == HypothesisKind.benign else h.posterior - delta
            elif ev.stance == Stance.supports_suspicion:
                new_post = h.posterior - delta if h.kind == HypothesisKind.benign else h.posterior + delta
            else:
                continue
            new_post = max(0.05, min(0.95, new_post))
            status = h.status
            if new_post <= 0.15:
                status = HypothesisStatus.refuted
            elif new_post >= 0.75:
                status = HypothesisStatus.supported
            elif new_post < h.prior - 0.1:
                status = HypothesisStatus.weakened
            updates.append({
                "hypothesis_id": h.hypothesis_id,
                "posterior": new_post,
                "status": status.value,
                "rationale": f"Moved by {ev.evidence_id} ({ev.stance.value}) in the {ev.dimension.value} dimension.",
            })
    return items, updates


def fallback_plan(
    step_no: int,
    specs: list[ToolSpec],
    case: AgentCaseView,
    hypotheses: list[Hypothesis],
    evidence: list[EvidenceItem],
    triage: Triage,
    remaining: int,
    called_keys: set[str],
    benign_tested_flag: bool,
    probed_dims: set[str] | None = None,
) -> Any:
    """The deterministic scorer is the whole planner in the fallback path.
    Stop conditions are enforced by the loop before this is called."""
    args_for = {s.name: planner_mod.build_args(s, case, hypotheses) for s in specs}
    scores = planner_mod.score_tools(specs, hypotheses, evidence, triage, called_keys,
                                     benign_tested_flag, args_for, probed_dims)
    affordable = [s for s in specs if s.cost_units <= remaining and scores.get(s.name, 0.0) > 0.0]
    if not affordable:
        min_cost = min((s.cost_units for s in specs), default=99)
        reason = "budget_exhausted" if min_cost > remaining else "no_informative_tool_left"
        return planner_mod.deterministic_plan_step(
            step_no, reason, specs, hypotheses, evidence, triage, remaining,
            called_keys, benign_tested_flag, args_for, probed_dims,
        )
    best = planner_mod.choose_tool(specs, scores, affordable, hypotheses, evidence, benign_tested_flag,
                                  probed_dims, triage)
    return planner_mod._mk_step(
        step_no, best.name, args_for[best.name], scores, specs, remaining,
        called_keys, benign_tested_flag, hypotheses,
        "Deterministic scorer: highest expected information gain per unit cost.",
    )


def _probed_dims(specs: list[ToolSpec], called_keys: set[str]) -> set[str]:
    """Recover probed dimension names from called_keys entries
    (canonical_json([tool_name, args]) strings)."""
    import json as _json

    called_names: set[str] = set()
    for k in called_keys:
        try:
            name = _json.loads(k)[0] if isinstance(k, str) else k[0]
        except Exception:
            name = k if isinstance(k, str) else ""
        called_names.add(name)
    dims: set[str] = set()
    for spec in specs:
        if spec.name in called_names:
            dims.update(d.value for d in spec.dimensions)
    return dims
