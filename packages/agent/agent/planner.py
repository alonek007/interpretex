"""The planner: what makes this an agent rather than a pipeline.

- A deterministic scorer runs ALONGSIDE the LLM's judgement: it fills
  `considered` when the model is lazy, overrides an invalid model choice,
  and is the whole planner in the fallback path.
- The benign_test_bonus biases the agent to spend a call on
  check_contract_or_supporting_evidence once a real anomaly appears — that is
  what unblocks escalation later.
- All stop conditions are deterministic and produce a final PlanStep with
  chosen_tool=None and a stop_reason.
"""
from __future__ import annotations

import jsonschema
from typing import Any

from interpretex_contracts import (
    AgentCaseView,
    ConsideredTool,
    Dimension,
    EvidenceItem,
    Hypothesis,
    HypothesisKind,
    PlanStep,
    Severity,
    SkippedTool,
    Stance,
    ToolSpec,
    Triage,
    canonical_json,
)

from .prompts import load_template
from .schemas import PLAN_SCHEMA

INFO_FLOOR = 0.15
BENIGN_TEST_BONUS = 0.5
TRIAGE_PRIORITY_BONUS = 0.2
BENIGN_POSTERIOR_BLOCK = 0.6


# ------------------------------------------------------------ deterministic scorer

def _dim_novelty(tool: ToolSpec, evidence: list[EvidenceItem]) -> float:
    best = 0.1
    for dim in tool.dimensions:
        count = sum(1 for e in evidence if e.dimension == dim)
        novelty = 1.0 if count == 0 else (0.35 if count <= 2 else 0.1)
        best = max(best, novelty)
    return best if tool.dimensions else 0.1


def _hypothesis_relevance(tool: ToolSpec, hypotheses: list[Hypothesis]) -> float:
    """0..1 — how much the tool speaks to live, non-refuted hypotheses.

    A hypothesis counts at full weight when its id is listed in the tool's
    `discriminates` (an exact, deterministic signal that the tool can separate
    that hypothesis from its rivals). Dimension overlap counts at reduced
    weight so a tool still scores for the dimensions it covers even when its
    discriminates list is narrow.
    """
    live = [h for h in hypotheses if h.status not in ("refuted", "untestable")]
    disc = {t.lower() for t in tool.discriminates}
    tool_dims = {d.value for d in tool.dimensions}
    direct = 0.0
    overlap = 0.0
    for h in live:
        if h.hypothesis_id.lower() in disc:
            direct += max(h.posterior, 0.05)
        elif set(d.value for d in h.explains) & tool_dims:
            overlap += max(h.posterior, 0.05)
    return min(1.0, direct + 0.3 * min(1.0, overlap))


def _benign_tool_ids(specs: list[ToolSpec]) -> set[str]:
    """Hypothesis ids that some tool explicitly lists in its discriminates and
    that are benign — i.e. the hypotheses a 'test the innocent explanation'
    tool can actually resolve."""
    ids: set[str] = set()
    for spec in specs:
        for t in spec.discriminates:
            if t[:1].upper() == "H" and t[1:].isdigit():
                ids.add(t.lower())
    return ids


def _anomaly_needs_benign_test(
    hypotheses: list[Hypothesis], evidence: list[EvidenceItem], specs: list[ToolSpec]
) -> bool:
    """True when a medium+ support signal exists in a dimension whose live
    benign hypothesis is actually resolvable by a benign-testing tool — exactly
    the moment the innocent explanation must be tested before any verdict."""
    benign_ids = _benign_tool_ids(specs)
    for ev in evidence:
        if ev.stance != Stance.supports_suspicion or ev.severity not in (Severity.medium, Severity.high):
            continue
        for h in hypotheses:
            if (
                h.hypothesis_id.lower() in benign_ids
                and h.kind == HypothesisKind.benign
                and h.status not in ("refuted", "untestable")
                and ev.dimension in h.explains
            ):
                return True
    return False


def _tool_can_test_benign(spec: ToolSpec, hypotheses: list[Hypothesis]) -> bool:
    """A tool actually *tests the innocent explanation* only when its
    discriminates list benign hypotheses and no suspicious ones — i.e. the
    dedicated contract/supporting-evidence check. A price or consistency check
    that merely touches a benign dimension is not a benign test."""
    disc = {t.lower() for t in spec.discriminates}
    has_benign = any(
        h.hypothesis_id.lower() in disc
        and h.kind == HypothesisKind.benign
        and h.status not in ("refuted", "untestable")
        for h in hypotheses
    )
    has_suspicious = any(
        h.hypothesis_id.lower() in disc and h.kind == HypothesisKind.suspicious
        for h in hypotheses
    )
    return has_benign and not has_suspicious


# Dimension investigation priority: the headline economic/documentary checks
# come first; physical and temporal corroboration follow; behavioural and
# network are lowest-priority context. Used only to break ties between tools of
# equal information value, so the investigation always walks the most decisive
# dimension first.
DIM_PRIORITY = {
    "economic": 0,
    "documentary": 1,
    "physical": 2,
    "temporal": 3,
    "behavioural": 4,
    "network": 5,
}


def _relevance_to_dim(spec: ToolSpec, dim: str, hypotheses: list[Hypothesis]) -> float:
    """Sum of live-hypothesis posterior mass that this tool speaks to *in a
    specific dimension* — direct (in discriminates) at full weight, dimension
    overlap at reduced weight. Used to break ties between tools that all cover
    the same top-priority dimension."""
    disc = {t.lower() for t in spec.discriminates}
    rel = 0.0
    for h in hypotheses:
        if h.status in ("refuted", "untestable"):
            continue
        if dim not in {d.value for d in h.explains}:
            continue
        if h.hypothesis_id.lower() in disc:
            rel += max(h.posterior, 0.05)
        else:
            rel += 0.3 * max(h.posterior, 0.05)
    return rel


def choose_tool(
    specs: list[ToolSpec],
    scores: dict[str, float],
    affordable: list[ToolSpec],
    hypotheses: list[Hypothesis],
    evidence: list[EvidenceItem],
    benign_tested_flag: bool,
    probed_dims: set[str] | None = None,
    triage: Triage | None = None,
) -> ToolSpec | None:
    """Picks the next tool.

    1. When a real anomaly has appeared but no benign explanation has been
       tested yet, bias hard toward a benign-testing tool (the contract check)
       — that is the only way to satisfy the policy gate's 'tested benign
       hypothesis' precondition for escalation, and it unblocks the RELEASE
       path on explainable cases.
    2. Otherwise prefer the tool that covers the highest-priority *unprobed*
       flagged dimension (economic before documentary before physical before
       temporal …); ties are broken by how much that dimension's competing
       hypotheses the tool discriminates, then by how many remaining
       dimensions it clears at once, then cost, then spec order.
    """
    if not affordable:
        return None
    if _anomaly_needs_benign_test(hypotheses, evidence, specs) and not benign_tested_flag:
        benign_tools = [s for s in affordable if _tool_can_test_benign(s, hypotheses)]
        if benign_tools:
            return max(benign_tools, key=lambda s: scores.get(s.name, 0.0))
    flagged = {d.value for d in triage.dimensions_to_probe} if triage else set()
    unprobed = flagged - (probed_dims or set())
    # only tools that still cover an unprobed flagged dimension are useful; a tool
    # whose every dimension is already probed must not outrank a tool that would
    # actually advance the investigation.
    candidates = [s for s in affordable if set(d.value for d in s.dimensions) & unprobed]
    if not candidates:
        candidates = affordable

    def rank(spec: ToolSpec):
        dims = [d.value for d in spec.dimensions]
        best = min((DIM_PRIORITY[d] for d in dims if d in unprobed), default=99)
        best_dim = next((d for d in dims if DIM_PRIORITY.get(d, 99) == best), None)
        rel_best = _relevance_to_dim(spec, best_dim, hypotheses) if best_dim else 0.0
        cleared = sum(1 for d in dims if d in unprobed)
        return (best, -rel_best, -cleared, spec.cost_units, specs.index(spec))

    return min(candidates, key=rank)


def score_tools(
    specs: list[ToolSpec],
    hypotheses: list[Hypothesis],
    evidence: list[EvidenceItem],
    triage: Triage,
    called_keys: set[str],
    benign_tested_flag: bool,
    args_for: dict[str, dict[str, Any]],
    probed_dims: set[str] | None = None,
) -> dict[str, float]:
    """Deterministic information-gain-style score per tool (section 7)."""
    probed = probed_dims or set()
    benign_candidate_live = _anomaly_needs_benign_test(hypotheses, evidence, specs)
    flagged = {d.value for d in triage.dimensions_to_probe}
    scores: dict[str, float] = {}
    for spec in specs:
        key = canonical_json([spec.name, args_for.get(spec.name, {})])
        if key in called_keys:
            scores[spec.name] = 0.0
            continue
        novelty = _dim_novelty(spec, evidence)
        relevance = _hypothesis_relevance(spec, hypotheses)
        can_test_benign = any(
            h.kind == HypothesisKind.benign
            and h.status not in ("refuted", "untestable")
            and (set(d.value for d in h.explains) & set(d.value for d in spec.dimensions)
                 or h.kind.value in {t.lower() for t in spec.discriminates})
            for h in hypotheses
        )
        bonus = (
            BENIGN_TEST_BONUS
            if (can_test_benign and not benign_tested_flag and benign_candidate_live)
            else 0.0
        )
        unprobed_flagged = flagged - probed
        coverage = 0.05 if (unprobed_flagged & {d.value for d in spec.dimensions}) else 0.0
        priority = TRIAGE_PRIORITY_BONUS if any(d in triage.dimensions_to_probe for d in spec.dimensions) else 0.0
        cost = max(1, spec.cost_units)
        scores[spec.name] = round((novelty + relevance + bonus + coverage + priority) / cost, 4)
    return scores


# ---------------------------------------------------------------- args builder

def build_args(spec: ToolSpec, case: AgentCaseView, hypotheses: list[Hypothesis]) -> dict[str, Any]:
    """Deterministic arguments from the case record, filtered by the tool's schema."""
    r = case.record
    candidates: dict[str, dict[str, Any]] = {
        "read_document": {"doc_type": case.documents[0].doc_type.value if case.documents else None},
        "check_document_consistency": {},
        "check_price_benchmark": {
            "commodity": r.commodity,
            "quantity": r.quantity,
            "as_of_date": str(r.ship_date or case.received_at.date()),
            "declared_unit_price": r.unit_price,
        },
        "check_vessel_capacity": {
            "vessel_name": r.vessel_name or "",
            "claimed_weight_tons": r.gross_weight_tons or r.quantity,
        },
        "check_transit_plausibility": {
            "origin_port": r.origin_port or "",
            "destination_port": r.destination_port or "",
            "ship_date": str(r.ship_date) if r.ship_date else "",
            "arrival_date": str(r.arrival_date) if r.arrival_date else "",
            "vessel_name": r.vessel_name or "",
        },
        "check_historical_trade": {"entity_id": r.exporter_id, "commodity": r.commodity},
        "check_counterparty_network": {"entity_id": r.broker_id or r.exporter_id, "depth": 2},
        "check_contract_or_supporting_evidence": {"claim": _benign_claim(hypotheses)},
    }
    args = dict(candidates.get(spec.name, {}))
    props = (spec.args_schema or {}).get("properties", {})
    if props:
        args = {k: v for k, v in args.items() if k in props}
        for key in props:  # let required keys pass through even if unknown to us
            if key not in args:
                args[key] = None
        args = {k: v for k, v in args.items() if v is not None or props[k].get("type") in (None, "null")}
    return args


def _benign_claim(hypotheses: list[Hypothesis]) -> str:
    text = " ".join(
        h.statement.lower() for h in hypotheses if h.kind == HypothesisKind.benign and h.status != "refuted"
    )
    if "offtake" in text or "long-term" in text:
        return "long_term_offtake"
    if "grade" in text or "lower grade" in text:
        return "grade_difference"
    if "distress" in text:
        return "distressed_sale"
    if "inspection" in text:
        return "inspection"
    return "bulk_discount"


# ------------------------------------------------------------------- planning

def validate_choice(
    chosen: str | None,
    args: dict[str, Any],
    specs: list[ToolSpec],
    remaining: int,
    called_keys: set[str],
) -> tuple[bool, str]:
    if chosen is None:
        return True, ""
    spec = next((s for s in specs if s.name == chosen), None)
    if spec is None:
        return False, "chosen tool does not exist"
    if spec.cost_units > remaining:
        return False, "chosen tool is not affordable within the remaining budget"
    key = canonical_json([chosen, args])
    if key in called_keys:
        return False, "identical call already made"
    try:
        if spec.args_schema:
            jsonschema.validate(args, spec.args_schema)
    except jsonschema.ValidationError as exc:
        return False, f"args failed the tool schema: {exc.message[:120]}"
    return True, ""


def fill_considered(
    scores: dict[str, float],
    specs: list[ToolSpec],
    remaining: int,
    called_keys: set[str],
    chosen: str | None,
    args_for: dict[str, dict[str, Any]],
) -> list[ConsideredTool]:
    out: list[ConsideredTool] = []
    for spec in sorted(specs, key=lambda s: -scores.get(s.name, 0.0)):
        key = canonical_json([spec.name, args_for.get(spec.name, {})])
        if spec.name == chosen or key in called_keys:
            continue
        score = scores.get(spec.name, 0.0)
        if spec.cost_units > remaining:
            why = f"not affordable: costs {spec.cost_units} of {remaining} remaining"
        elif score == 0.0:
            why = "already called with these arguments"
        elif chosen is None:
            why = "not selected: lower expected information gain per unit cost"
        else:
            why = f"lower expected information gain per unit cost than {chosen}"
        out.append(ConsideredTool(tool=spec.name, expected_information_gain=score, why_not=why))
    return out


def evaluate_stop(
    specs: list[ToolSpec],
    hypotheses: list[Hypothesis],
    evidence: list[EvidenceItem],
    triage: Triage,
    remaining: int,
    benign_tested_flag: bool,
    probed_dims: set[str],
) -> str | None:
    support_med = [
        e for e in evidence
        if e.stance == Stance.supports_suspicion and e.severity in (Severity.medium, Severity.high)
    ]
    support_above_low = [
        e for e in evidence
        if e.stance == Stance.supports_suspicion and e.severity in (Severity.medium, Severity.high, Severity.low)
    ]
    flagged = {d.value for d in triage.dimensions_to_probe}
    # 1. corroborated across >= 2 dims with the benign explanation tested
    if len({e.dimension.value for e in support_med}) >= 2 and benign_tested_flag:
        return "sufficient_evidence"
    # 2. nothing above low and every triage-flagged dimension probed
    if not support_above_low and flagged.issubset(probed_dims) and flagged:
        return "sufficient_evidence"
    # 3. every elevated signal fully matched by a strong refuter in its own
    #    dimension, benign explanation tested, and all flagged dims probed
    if support_med and benign_tested_flag and flagged.issubset(probed_dims) and flagged:
        refuting = [e for e in evidence if e.stance == Stance.refutes_suspicion]
        fully_matched = all(
            any(r.dimension == s.dimension and r.weight >= 0.6 for r in refuting)
            for s in support_med
        )
        if fully_matched:
            return "sufficient_evidence"
    # 4. nothing affordable remains
    min_cost = min((s.cost_units for s in specs), default=99)
    if min_cost > remaining:
        return "budget_exhausted"
    return None


def deterministic_plan_step(
    step_no: int,
    stop_reason: str,
    specs: list[ToolSpec],
    hypotheses: list[Hypothesis],
    evidence: list[EvidenceItem],
    triage: Triage,
    remaining: int,
    called_keys: set[str],
    benign_tested_flag: bool,
    args_for: dict[str, dict[str, Any]],
    probed_dims: set[str] | None = None,
) -> PlanStep:
    scores = score_tools(specs, hypotheses, evidence, triage, called_keys, benign_tested_flag,
                         args_for, probed_dims)
    considered = fill_considered(scores, specs, remaining, called_keys, None, args_for)
    return PlanStep(
        step=step_no,
        reasoning=f"Stopping ({stop_reason}): no further check would change the decision.",
        chosen_tool=None,
        chosen_args={},
        targets_hypotheses=[],
        expected_information_gain=0.0,
        considered=considered,
        stop_reason=stop_reason,
    )


def llm_plan_step(
    step_no: int,
    triage: Triage,
    hypotheses: list[Hypothesis],
    evidence: list[EvidenceItem],
    specs: list[ToolSpec],
    remaining: int,
    called_keys: set[str],
    benign_tested_flag: bool,
    case: AgentCaseView,
    llm: Any,
    tag: str,
    probed_dims: set[str] | None = None,
) -> tuple[PlanStep, bool]:
    """LLM plan call with Python-side validation. Returns (step, llm_ok)."""
    args_for = {s.name: build_args(s, case, hypotheses) for s in specs}
    scores = score_tools(specs, hypotheses, evidence, triage, called_keys, benign_tested_flag, args_for, probed_dims)
    affordable = [s for s in specs if s.cost_units <= remaining and scores.get(s.name, 0.0) > 0.0]
    system = load_template("plan")
    hyp_lines = "\n".join(
        f"- {h.hypothesis_id} [{h.kind.value}] post={h.posterior:.2f} status={h.status.value}: {h.statement}"
        for h in hypotheses
    )
    ev_lines = "\n".join(f"- {e.evidence_id} [{e.dimension.value}/{e.severity.value}]: {e.statement}"
                         for e in evidence) or "(none yet)"
    called_lines = "\n".join(f"- {k[0]} args={k[1]}" for k in sorted(called_keys)) or "(none)"
    tool_lines = "\n".join(
        f"- {s.name} (cost {s.cost_units}; dims {', '.join(d.value for d in s.dimensions)}; "
        f"discriminates {', '.join(s.discriminates) or '(any)'})\n  {s.description}\n"
        f"  suggested args: {json_dumps(args_for.get(s.name, {}))}"
        for s in affordable
    )
    user = (
        f"TRIAGE: {triage.trade_narrative}\n\nHYPOTHESES:\n{hyp_lines}\n\nEVIDENCE:\n{ev_lines}\n\n"
        f"TOOLS_CALLED:\n{called_lines}\n\nBUDGET: {remaining} cost units remaining.\n\n"
        f"TOOLS (affordable):\n{tool_lines or '(none)'}\n\n"
        "Return the plan JSON object now."
    )
    try:
        data = llm.complete_json(
            system=system, messages=[{"role": "user", "content": user}], schema=PLAN_SCHEMA,
            temperature=0.1, max_tokens=1200, tag=tag,
        )
    except Exception:
        # deterministic scorer is the whole planner on LLM failure
        best = choose_tool(specs, scores, affordable, hypotheses, evidence, benign_tested_flag, probed_dims, triage)
        if best is None:
            reason = "budget_exhausted" if remaining < min(s.cost_units for s in specs) else "no_informative_tool_left"
            return deterministic_plan_step(step_no, reason, specs, hypotheses, evidence, triage,
                                           remaining, called_keys, benign_tested_flag, args_for, probed_dims), False
        return _mk_step(step_no, best.name, args_for[best.name], scores, specs, remaining,
                        called_keys, benign_tested_flag, hypotheses,
                        "LLM plan call failed; deterministic scorer chose the next check."), False

    chosen = data.get("chosen_tool")
    if isinstance(chosen, str) and chosen.strip():
        chosen = chosen.strip()
        args = data.get("chosen_args") or args_for.get(chosen, {})
        ok, why = validate_choice(chosen, args, specs, remaining, called_keys)
        if not ok:
            best = choose_tool(specs, scores, affordable, hypotheses, evidence, benign_tested_flag, probed_dims, triage)
            if best is None:
                reason = (
                    "budget_exhausted"
                    if remaining < min(s.cost_units for s in specs)
                    else "no_informative_tool_left"
                )
                return deterministic_plan_step(step_no, reason, specs, hypotheses, evidence, triage,
                                              remaining, called_keys, benign_tested_flag, args_for, probed_dims), True
            step = _mk_step(step_no, best.name, args_for[best.name], scores, specs, remaining,
                            called_keys, benign_tested_flag, hypotheses,
                            f"Override (model choice invalid: {why}); deterministic scorer's top pick.")
            return step, True
        considered = [
            ConsideredTool(tool=str(c.get("tool", "")), expected_information_gain=float(c.get("expected_information_gain", 0.0) or 0.0), why_not=str(c.get("why_not", "")))
            for c in (data.get("considered") or []) if isinstance(c, dict)
        ]
        if len(affordable) >= 2 and len(considered) < 1:
            considered = fill_considered(scores, specs, remaining, called_keys, chosen, args_for)
        step = PlanStep(
            step=step_no,
            reasoning=str(data.get("reasoning", "")).strip() or "Model-selected next check.",
            chosen_tool=chosen,
            chosen_args=args,
            targets_hypotheses=[str(t) for t in (data.get("targets_hypotheses") or [])],
            expected_information_gain=float(data.get("expected_information_gain", 0.0) or 0.0),
            considered=considered,
        )
        return step, True

    stop = str(data.get("stop_reason") or "sufficient_evidence")
    if stop not in ("sufficient_evidence", "budget_exhausted", "no_informative_tool_left"):
        stop = "sufficient_evidence"
    considered = fill_considered(scores, specs, remaining, called_keys, None, args_for)
    step = PlanStep(
        step=step_no,
        reasoning=str(data.get("reasoning", "")).strip() or f"Stopping: {stop}.",
        chosen_tool=None,
        chosen_args={},
        targets_hypotheses=[],
        expected_information_gain=0.0,
        considered=considered,
        stop_reason=stop,
    )
    return step, True


def _mk_step(
    step_no: int,
    chosen: str,
    args: dict[str, Any],
    scores: dict[str, float],
    specs: list[ToolSpec],
    remaining: int,
    called_keys: set[str],
    benign_tested_flag: bool,
    hypotheses: list[Hypothesis],
    reasoning: str,
) -> PlanStep:
    considered = fill_considered(scores, specs, remaining, called_keys, chosen, args)
    spec = next(s for s in specs if s.name == chosen)
    targets = [
        h.hypothesis_id for h in hypotheses
        if h.status not in ("refuted", "untestable")
        and (h.hypothesis_id in {t.lower() for t in spec.discriminates}
             or set(d.value for d in h.explains) & set(d.value for d in spec.dimensions))
    ]
    return PlanStep(
        step=step_no,
        reasoning=reasoning,
        chosen_tool=chosen,
        chosen_args=args,
        targets_hypotheses=targets,
        expected_information_gain=scores.get(chosen, 0.0),
        considered=considered,
    )


def skipped_tools(specs: list[ToolSpec], called: list[str], remaining: int, scores: dict[str, float]) -> list[SkippedTool]:
    out: list[SkippedTool] = []
    for spec in specs:
        if spec.name in called:
            continue
        if spec.cost_units > remaining:
            out.append(SkippedTool(tool=spec.name, reason=f"budget exhausted (cost {spec.cost_units} > {remaining} remaining)"))
        elif scores.get(spec.name, 0.0) < INFO_FLOOR:
            out.append(SkippedTool(tool=spec.name, reason="below information-gain floor"))
    return out


def json_dumps(obj: Any) -> str:
    import json as _json

    return _json.dumps(obj, default=str)
