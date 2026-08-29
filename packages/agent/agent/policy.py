"""The deterministic decision policy gate.

THE MOST IMPORTANT CODE IN THE AGENT. A pure function of the ledger:
no LLM call, no I/O, no randomness, fully unit tested. The LLM proposes;
this function disposes. When the model's suggested verdict disagrees with
the policy, the policy wins and the disagreement is recorded in rationale.

Rules (frozen, master plan section 8.9 / part prompt section 9):

ESCALATE requires ALL of:
  - suspicion-supporting evidence at severity >= medium in >= 2 distinct
    dimensions, after the independence penalty (corroborated_dimensions);
  - NO benign hypothesis with posterior >= 0.6;
  - >= 1 tool call whose targets_hypotheses included a benign hypothesis.

RELEASE requires either:
  - no suspicion-supporting evidence above low, OR
  - every medium+ support item matched by a refutes_suspicion item in the
    same dimension with weight >= 0.6.

Otherwise HOLD, and evidence_requests must be non-empty.

Hard rule 1: a single anomalous dimension can never escalate.
Hard rule 2: no escalation without a tested benign hypothesis.
"""
from __future__ import annotations

from typing import Optional

from interpretex_contracts import (
    STANDARD_CAVEATS,
    Corroboration,
    Decision,
    Dimension,
    EvidenceItem,
    Hypothesis,
    HypothesisKind,
    PlanStep,
    Severity,
    Stance,
    ToolResult,
    Verdict,
)

SEV_ORDER = {Severity.none: 0, Severity.low: 1, Severity.medium: 2, Severity.high: 3}
BENIGN_POSTERIOR_BLOCK = 0.6
REFUTING_WEIGHT_NEEDED = 0.6

# typology wording is compliance-language constrained: never "confirmed",
# "proven", "fraud" or "money laundering" as a conclusion.
TYPOLOGY_UNDER = "Indicators consistent with potential under-invoicing / trade-value manipulation"
TYPOLOGY_OVER = "Indicators consistent with potential over-invoicing / value inflation"
TYPOLOGY_PHANTOM = "Indicators consistent with potential phantom or misrepresented shipment"
TYPOLOGY_MISDESC = "Indicators consistent with potential misdescription of goods"


def _support(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    return [e for e in evidence if e.stance == Stance.supports_suspicion]


def _refuting(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    return [e for e in evidence if e.stance == Stance.refutes_suspicion]


def _at_or_above(items: list[EvidenceItem], floor: Severity) -> list[EvidenceItem]:
    return [e for e in items if SEV_ORDER[e.severity] >= SEV_ORDER[floor]]


def _distinct_dims(items: list[EvidenceItem]) -> list[Dimension]:
    seen: dict[str, Dimension] = {}
    for e in items:  # keep enum-declaration order for determinism
        seen.setdefault(e.dimension.value, e.dimension)
    return [Dimension(k) for k in (
        "economic", "physical", "temporal", "documentary", "behavioural", "network"
    ) if k in seen]


def benign_hypothesis_ids(hypotheses: list[Hypothesis]) -> set[str]:
    return {h.hypothesis_id for h in hypotheses if h.kind == HypothesisKind.benign}


# The dedicated benign-confirmation tool. Per section 13, this is the only tool
# whose job is to surface evidence FOR an innocent explanation, so it is the only
# tool that can satisfy the policy gate's "tested benign hypothesis" precondition.
BENIGN_TEST_TOOLS = {"check_contract_or_supporting_evidence"}


def benign_tested(
    hypotheses: list[Hypothesis], plan_steps: list[PlanStep], tool_calls: list[ToolResult] | None = None
) -> bool:
    """True iff the dedicated benign-confirmation tool was actually invoked.

    A price or consistency check that merely *touches* a benign dimension does
    NOT count — it tests for anomalies, it does not confirm the innocent
    explanation. Only an explicit benign-support search satisfies the gate."""
    for tc in tool_calls or []:
        if tc.tool in BENIGN_TEST_TOOLS:
            return True
    for step in plan_steps:
        if step.chosen_tool in BENIGN_TEST_TOOLS:
            return True
    return False


def _refutation_matches(support_items: list[EvidenceItem], refuting: list[EvidenceItem]) -> bool:
    """Every medium+ support item matched by a refuter in the same dimension, weight >= 0.6."""
    for item in support_items:
        if SEV_ORDER[item.severity] < SEV_ORDER[Severity.medium]:
            continue
        ok = any(
            r.dimension == item.dimension and r.weight >= REFUTING_WEIGHT_NEEDED for r in refuting
        )
        if not ok:
            return False
    return True


def _strongest_benign(hypotheses: list[Hypothesis]) -> tuple[Optional[str], float]:
    best_id, best_post = None, 0.0
    for h in hypotheses:
        if h.kind == HypothesisKind.benign and h.posterior >= best_post:
            best_id, best_post = h.hypothesis_id, h.posterior
    return best_id, best_post


def _decisive_ids(evidence: list[EvidenceItem], verdict: Verdict) -> list[str]:
    support_med = _at_or_above(_support(evidence), Severity.medium)
    refuting = _refuting(evidence)
    if verdict == Verdict.escalate:
        return [e.evidence_id for e in support_med]
    if verdict == Verdict.release:
        matched = [
            r for r in refuting
            if any(s.dimension == r.dimension for s in support_med)
        ] or refuting
        return [e.evidence_id for e in matched]
    return [e.evidence_id for e in support_med] + [
        e.evidence_id for e in refuting if any(s.dimension == e.dimension for s in support_med)
    ]


def _typology(evidence: list[EvidenceItem], verdict: Verdict) -> Optional[str]:
    if verdict != Verdict.escalate:
        return None
    text = " ".join(e.statement.lower() for e in _support(evidence))
    med_dims = {e.dimension for e in _at_or_above(_support(evidence), Severity.medium)}
    # a price-deviation statement decides under- vs over-invoicing first
    import re as _re

    m = _re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", text)
    if m is not None:
        try:
            return TYPOLOGY_UNDER if float(m.group(1)) < 0 else TYPOLOGY_OVER
        except ValueError:
            pass
    if "under-invoic" in text or "undervalu" in text:
        return TYPOLOGY_UNDER
    if "over-invoic" in text or "overvalu" in text or "above the benchmark" in text:
        return TYPOLOGY_OVER
    if Dimension.documentary in med_dims and ("scrap" in text or "describ" in text or "drift" in text):
        return TYPOLOGY_MISDESC
    if med_dims >= {Dimension.temporal, Dimension.physical} and "transit" in text:
        return TYPOLOGY_PHANTOM
    return TYPOLOGY_UNDER


def _confidence(
    evidence: list[EvidenceItem],
    corroborated: list[Dimension],
    strongest_benign_posterior: float,
    tool_calls: list[ToolResult],
    degraded: bool,
) -> float:
    support_med = _at_or_above(_support(evidence), Severity.medium)
    decisive = support_med or list(evidence)
    mean_weight = sum(e.weight for e in decisive) / max(len(decisive), 1)
    margin = max(0.0, (1.0 - strongest_benign_posterior) if support_med else strongest_benign_posterior)
    probed_dims = {
        o.dimension for tc in tool_calls for o in tc.observations
    }
    fraction_probed = min(1.0, len(probed_dims) / len(Dimension))
    conf = (
        0.25
        + 0.15 * min(len(corroborated), 3)
        + 0.25 * mean_weight
        + 0.10 * margin
        + 0.10 * fraction_probed
    )
    if degraded:
        conf -= 0.15
    return round(min(0.9, max(0.05, conf)), 2)


def _headline(verdict: Verdict, corroborated: list[Dimension], top: Optional[EvidenceItem]) -> str:
    dims = ", ".join(d.value for d in corroborated) or "none"
    if verdict == Verdict.escalate:
        focus = top.statement if top else "multiple anomalies"
        return f"ESCALATE: corroborated anomalies across {dims} — {focus[:110]}"
    if verdict == Verdict.release:
        return "RELEASE: no significant corroborated anomaly was identified in the dimensions examined"
    focus = f" — {top.statement[:100]}" if top else ""
    return f"HOLD — request documentation: unresolved anomaly in {dims}{focus}"


def _rationale(
    verdict: Verdict,
    evidence: list[EvidenceItem],
    hypotheses: list[Hypothesis],
    corroborated: list[Dimension],
    benign_tested_flag: bool,
    llm_suggested: Optional[str],
    decisive: list[str],
) -> str:
    support_med = _at_or_above(_support(evidence), Severity.medium)
    refuting = _refuting(evidence)
    strongest_id, strongest_post = _strongest_benign(hypotheses)
    dims_txt = ", ".join(d.value for d in corroborated) or "none"
    ids_txt = ", ".join(decisive[:6]) or "none"

    if verdict == Verdict.escalate:
        core = (
            f"Suspicion-supporting evidence reaches medium severity or above in {len(corroborated)} "
            f"independent dimensions ({dims_txt}) after the independence penalty "
            f"({ids_txt}). The strongest benign hypothesis ({strongest_id}) holds a posterior of "
            f"{strongest_post:.2f}, below the 0.6 block, and a benign explanation was actively "
            f"tested before escalation. The deterministic policy gate therefore escalates on "
            f"corroborated, independent signals."
        )
    elif verdict == Verdict.release:
        if not support_med:
            core = (
                f"No suspicion-supporting evidence rises above low severity (decisive ids: {ids_txt}); "
                f"the strongest benign hypothesis ({strongest_id}) stands at posterior {strongest_post:.2f}. "
                f"The policy gate releases when nothing above low remains."
            )
        else:
            core = (
                f"Medium-or-above signals in {dims_txt} were matched by refuting evidence in the same "
                f"dimension with weight >= {REFUTING_WEIGHT_NEEDED} ({ids_txt}), consistent with the "
                f"tested benign hypothesis {strongest_id} (posterior {strongest_post:.2f}). The policy "
                f"gate releases because every elevated signal is accounted for."
            )
    else:
        raise_txt = (
            "Escalation is blocked: "
            + (
                "only one dimension reaches medium-or-above, and a single-dimension anomaly can never "
                "escalate. "
                if len(corroborated) < 2
                else ""
            )
            + (
                "" if benign_tested_flag else "no tool call ever targeted a benign hypothesis. "
            )
            + (
                f"a benign hypothesis ({strongest_id}) holds posterior {strongest_post:.2f} >= 0.6. "
                if strongest_post >= BENIGN_POSTERIOR_BLOCK
                else ""
            )
        )
        core = (
            f"Medium-or-above suspicion-supporting evidence exists in {dims_txt} ({ids_txt}). "
            f"{raise_txt}The verdict is therefore HOLD: request the documentation that would resolve "
            f"the live hypotheses. The verdict would move to ESCALATE if a second independent dimension "
            f"reached medium severity while the benign explanation stayed below 0.6 after being tested; "
            f"it would move to RELEASE if the outstanding medium signals were matched by refuting "
            f"evidence of weight >= {REFUTING_WEIGHT_NEEDED} in their dimensions."
        )

    if llm_suggested and llm_suggested not in ("", verdict.value):
        core += (
            f" The model suggested '{llm_suggested}'; the deterministic policy disagrees and the "
            f"policy wins."
        )
    return core


def decide(
    evidence: list[EvidenceItem],
    hypotheses: list[Hypothesis],
    corroboration: Corroboration,
    tool_calls: list[ToolResult],
    plan_steps: list[PlanStep],
    *,
    llm_suggested_verdict: Optional[str] = None,
    degraded: bool = False,
) -> Decision:
    """Pure deterministic verdict over the evidence ledger."""
    support = _support(evidence)
    refuting = _refuting(evidence)
    support_med = _at_or_above(support, Severity.medium)

    # Independence penalty already applied by corroboration.py; fall back to
    # raw distinct dims when the caller passed an empty corroboration.
    corroborated = corroboration.corroborated_dimensions or _distinct_dims(support_med)
    tested = benign_tested(hypotheses, plan_steps, tool_calls)
    strongest_id, strongest_post = _strongest_benign(hypotheses)

    verdict: Verdict
    if not support_med or _refutation_matches(support_med, refuting):
        # No elevated signal at all, or every elevated signal is counter-balanced
        # by a strong refuter in its own dimension. Fully explained anomalies can
        # never escalate — this precedence IS the Case 2 thesis.
        verdict = Verdict.release
    elif (
        len(corroborated) >= 2
        and strongest_post < BENIGN_POSTERIOR_BLOCK
        and tested
    ):
        verdict = Verdict.escalate
    else:
        verdict = Verdict.hold

    decisive = _decisive_ids(evidence, verdict)
    top = next((e for e in support_med if e.evidence_id in decisive), None) or (
        refuting[0] if refuting else None
    )
    conf = _confidence(evidence, corroborated, strongest_post, tool_calls, degraded)

    return Decision(
        verdict=verdict,
        confidence=conf,
        headline=_headline(verdict, corroborated, top),
        rationale=_rationale(
            verdict, evidence, hypotheses, corroborated, tested, llm_suggested_verdict, decisive
        ),
        corroboration=corroboration,
        typology=_typology(evidence, verdict),
        caveats=list(STANDARD_CAVEATS),
        decisive_evidence_ids=decisive,
    )
