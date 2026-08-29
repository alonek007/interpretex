"""Hypothesis generation and posterior updating.

Hard rule enforced in Python (never trusted to the model): every dimension
raised by triage must be covered by at least one BENIGN and at least one
SUSPICIOUS hypothesis. If the model returns only suspicious ones, templates
are injected from a fixed benign catalogue. Catch-all hypotheses are always
present. Hypothesis ids are assigned once (H1, H2, ...) and never renumbered.
"""
from __future__ import annotations

from typing import Any, Iterable

from interpretex_contracts import (
    Dimension,
    EvidenceItem,
    Hypothesis,
    HypothesisKind,
    HypothesisStatus,
    Stance,
    Triage,
)

from .prompts import load_template
from .schemas import HYPOTHESISE_SCHEMA

# Fixed benign catalogue keyed by dimension (section 6.2).
BENIGN_CATALOGUE: dict[str, str] = {
    "economic": "The price reflects an agreed volume discount or a long-term contract.",
    "physical": "The vessel or the recorded weight was recorded incorrectly.",
    "temporal": "A date was mis-keyed.",
    "documentary": "A clerical error in one document explains the inconsistency.",
    "behavioural": "A legitimate change in the customer's trading pattern.",
    "network": "An ordinary commercial group structure explains the shared parties.",
}
BENIGN_DISCRIMINATORS: dict[str, list[str]] = {
    "economic": ["supporting contract or offtake agreement", "customer's own historical price range"],
    "physical": ["vessel registry capacity", "independent weight records"],
    "temporal": ["port-to-port transit statistics", "corrected dates"],
    "documentary": ["corrected or re-issued document"],
    "behavioural": ["prior trades for this entity"],
    "network": ["ownership registry for the shared intermediary"],
}
SUSPICIOUS_TEMPLATES: dict[str, str] = {
    "economic": "The declared value is being manipulated (under- or over-invoicing).",
    "physical": "The declared cargo cannot physically match the conveyance.",
    "temporal": "The claimed voyage could not have taken place as documented.",
    "documentary": "The documents were altered or issued to misrepresent the goods.",
    "behavioural": "The deviation from the customer's own history signals intent.",
    "network": "A shared intermediary or common ownership links this case to prior concerns.",
}
CATCH_ALL_BENIGN = "Documentation or data-entry error explains the inconsistency."
CATCH_ALL_SUSPICIOUS = "The declared value or description of the goods is being manipulated."


def build_messages(triage: Triage, tool_specs: list[Any]) -> tuple[str, list[dict[str, str]]]:
    system = load_template("hypothesise")
    specs = "; ".join(
        f"{s.name} discriminates: {', '.join(s.discriminates) or '(any live hypothesis)'}" for s in tool_specs
    )
    user = (
        f"TRIAGE:\n"
        f"narrative: {triage.trade_narrative}\n"
        f"concerns: {' | '.join(triage.initial_concerns) or '(none)'}\n"
        f"unknowns: {' | '.join(triage.unknowns) or '(none)'}\n"
        f"dimensions flagged: {', '.join(d.value for d in triage.dimensions_to_probe) or '(none)'}\n\n"
        f"TOOLS:\n{specs}\n\n"
        "Return the hypotheses JSON object now."
    )
    return system, [{"role": "user", "content": user}]


def _coerce_dims(raw: Iterable[Any]) -> list[Dimension]:
    out: list[Dimension] = []
    for item in raw or []:
        try:
            dim = Dimension(str(item))
        except ValueError:
            continue
        if dim not in out:
            out.append(dim)
    return out or [Dimension.economic]


def run_hypothesise(triage: Triage, tool_specs: list[Any], llm: Any, tag: str = "hypothesise") -> list[Hypothesis]:
    """LLM hypothesis generation. Raises on LLM failure — loop degrades."""
    system, messages = build_messages(triage, tool_specs)
    data = llm.complete_json(
        system=system, messages=messages, schema=HYPOTHESISE_SCHEMA, temperature=0.1, max_tokens=1500, tag=tag
    )
    raw = data.get("hypotheses") or []
    parsed: list[Hypothesis] = []
    for item in raw[:14]:
        if not isinstance(item, dict):
            continue
        kind_raw = str(item.get("kind", "suspicious"))
        kind = HypothesisKind.benign if kind_raw == "benign" else HypothesisKind.suspicious
        parsed.append(
            Hypothesis(
                hypothesis_id="-",  # assigned in ensure_balance
                kind=kind,
                statement=str(item.get("statement", "")).strip(),
                explains=_coerce_dims(item.get("explains")),
                prior=max(0.0, min(1.0, float(item.get("prior", 0.5) or 0.5))),
                posterior=max(0.0, min(1.0, float(item.get("prior", 0.5) or 0.5))),
                status=HypothesisStatus.open,
                discriminating_evidence_needed=[str(x) for x in (item.get("discriminating_evidence_needed") or [])][:5],
            )
        )
    return parsed


def ensure_balance(hypotheses_in: list[Hypothesis], triage: Triage) -> tuple[list[Hypothesis], list[str]]:
    """Assign ids, enforce the benign/suspicious coverage rule, add catch-alls,
    normalise priors within each primary dimension group. Returns (hypotheses, injected_ids)."""
    hypotheses: list[Hypothesis] = []
    injected: list[str] = []

    def add(kind: HypothesisKind, statement: str, dims: list[Dimension], discrim: list[str]) -> Hypothesis:
        hyp = Hypothesis(
            hypothesis_id=f"H{len(hypotheses) + 1}",
            kind=kind,
            statement=statement,
            explains=dims,
            prior=0.5,
            posterior=0.5,
            status=HypothesisStatus.open,
            discriminating_evidence_needed=discrim,
        )
        hypotheses.append(hyp)
        return hyp

    for hyp in hypotheses_in:
        if not hyp.statement:
            continue
        hyp.hypothesis_id = f"H{len(hypotheses) + 1}"
        hypotheses.append(hyp)

    flagged = list(triage.dimensions_to_probe) or [Dimension.economic]
    for dim in flagged:
        covered_benign = any(h.kind == HypothesisKind.benign and dim in h.explains for h in hypotheses)
        covered_susp = any(h.kind == HypothesisKind.suspicious and dim in h.explains for h in hypotheses)
        if not covered_benign:
            new = add(
                HypothesisKind.benign,
                BENIGN_CATALOGUE.get(dim.value, CATCH_ALL_BENIGN),
                [dim],
                BENIGN_DISCRIMINATORS.get(dim.value, ["the documents the bank holds"]),
            )
            injected.append(new.hypothesis_id)
        if not covered_susp:
            new = add(
                HypothesisKind.suspicious,
                SUSPICIOUS_TEMPLATES.get(dim.value, CATCH_ALL_SUSPICIOUS),
                [dim],
                [f"a reference lookup in the {dim.value} dimension"],
            )
            injected.append(new.hypothesis_id)

    # catch-alls, always
    if not any(h.statement == CATCH_ALL_BENIGN for h in hypotheses):
        add(HypothesisKind.benign, CATCH_ALL_BENIGN, [Dimension.documentary], ["documentary consistency check"])
    if not any(h.statement == CATCH_ALL_SUSPICIOUS for h in hypotheses):
        add(HypothesisKind.suspicious, CATCH_ALL_SUSPICIOUS, [Dimension.economic], ["price benchmark check"])

    _normalise_priors(hypotheses)
    return hypotheses, injected


def _normalise_priors(hypotheses: list[Hypothesis]) -> None:
    """Scale priors so they sum to roughly 1 within each primary-dimension group."""
    groups: dict[str, list[Hypothesis]] = {}
    for h in hypotheses:
        primary = (h.explains[0].value if h.explains else "economic")
        groups.setdefault(primary, []).append(h)
    for group in groups.values():
        total = sum(h.prior for h in group) or 1.0
        for h in group:
            h.prior = round(max(0.05, min(0.9, h.prior / total)), 3)
            h.posterior = h.prior


def apply_updates(
    hypotheses: list[Hypothesis],
    evidence_items: list[EvidenceItem],
    updates: list[dict[str, Any]],
) -> tuple[list[Hypothesis], list[str]]:
    """Apply interpret-stage hypothesis updates. Unknown ids are ignored;
    posteriors clamped to [0,1]; supporting/contradicting id lists maintained."""
    by_id = {h.hypothesis_id: h for h in hypotheses}
    changed: list[str] = []

    # evidence-id bookkeeping first
    for ev in evidence_items:
        for hid in ev.hypotheses_affected:
            hyp = by_id.get(hid)
            if hyp is None:
                continue
            if ev.stance == Stance.supports_suspicion:
                if ev.evidence_id not in hyp.supporting_evidence_ids:
                    if hyp.kind == HypothesisKind.suspicious:
                        hyp.supporting_evidence_ids.append(ev.evidence_id)
                    else:
                        hyp.contradicting_evidence_ids.append(ev.evidence_id)
            elif ev.stance == Stance.refutes_suspicion:
                if ev.evidence_id not in hyp.contradicting_evidence_ids:
                    if hyp.kind == HypothesisKind.suspicious:
                        hyp.contradicting_evidence_ids.append(ev.evidence_id)
                    else:
                        hyp.supporting_evidence_ids.append(ev.evidence_id)

    for upd in updates:
        hyp = by_id.get(str(upd.get("hypothesis_id", "")))
        if hyp is None:
            continue
        try:
            post = max(0.0, min(1.0, float(upd.get("posterior", hyp.posterior))))
        except (TypeError, ValueError):
            post = hyp.posterior
        hyp.posterior = round(post, 3)
        try:
            hyp.status = HypothesisStatus(str(upd.get("status", hyp.status)))
        except ValueError:
            pass
        rationale = str(upd.get("rationale", "")).strip()
        if rationale:
            hyp.rationale = rationale
        if hyp.hypothesis_id not in changed:
            changed.append(hyp.hypothesis_id)
    return hypotheses, changed
