"""Corroboration: dimensional independence analysis.

The facts are computed deterministically in Python; the LLM contributes only
the narrative sentence. Two signals are NOT independent if one mechanically
implies the other — detected by comparing the SourceRef.ref sets behind the
two evidence items: substantial overlap means a shared cause.
"""
from __future__ import annotations

from interpretex_contracts import (
    Corroboration,
    Dimension,
    EvidenceItem,
    Hypothesis,
    HypothesisKind,
    Severity,
    Stance,
)

OVERLAP_THRESHOLD = 0.6

# Known-dependent dimension pairs (section 8): (dim_a, dim_b) where a signal in
# dim_a can mechanically imply one in dim_b when they trace to the same fields.
DEPENDENT_PAIRS: set[tuple[str, str]] = {
    ("documentary", "physical"),   # quantity mismatch -> capacity excess (same tonnage)
    ("temporal", "physical"),      # impossible transit -> vessel substitution (same dates)
    ("documentary", "economic"),   # quantity mismatch -> price deviation (same totals)
}


def _refs(e: EvidenceItem) -> set[str]:
    return {s.ref for s in e.sources}


def _dependent(a: EvidenceItem, b: EvidenceItem) -> bool:
    pair = tuple(sorted((a.dimension.value, b.dimension.value)))
    if pair not in DEPENDENT_PAIRS:
        return False
    ra, rb = _refs(a), _refs(b)
    if not ra or not rb:
        return False
    overlap = len(ra & rb) / min(len(ra), len(rb))
    return overlap >= OVERLAP_THRESHOLD


def independent_support_items(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    """Medium+ suspicion-supporting items, dropping those dependent on an
    already-kept (higher-weight) item. Sort by weight desc for determinism."""
    support_med = [
        e for e in evidence
        if e.stance == Stance.supports_suspicion and e.severity in (Severity.medium, Severity.high)
    ]
    kept: list[EvidenceItem] = []
    for e in sorted(support_med, key=lambda x: (-x.weight, x.evidence_id)):
        if any(_dependent(e, k) for k in kept):
            continue
        kept.append(e)
    return kept


def strongest_benign(hypotheses: list[Hypothesis]) -> tuple[str | None, float]:
    best_id, best_post = None, 0.0
    for h in hypotheses:
        if h.kind == HypothesisKind.benign and h.posterior >= best_post:
            best_id, best_post = h.hypothesis_id, h.posterior
    return best_id, round(best_post, 3)


def compute_facts(evidence: list[EvidenceItem], hypotheses: list[Hypothesis]) -> Corroboration:
    independent = independent_support_items(evidence)
    dims: dict[str, Dimension] = {}
    for e in independent:
        dims.setdefault(e.dimension.value, e.dimension)
    corroborated = [Dimension(k) for k in ("economic", "physical", "temporal", "documentary", "behavioural", "network") if k in dims]
    refuting_dims: dict[str, Dimension] = {}
    for e in evidence:
        if e.stance == Stance.refutes_suspicion:
            refuting_dims.setdefault(e.dimension.value, e.dimension)
    refuting = [Dimension(k) for k in ("economic", "physical", "temporal", "documentary", "behavioural", "network") if k in refuting_dims]
    best_id, best_post = strongest_benign(hypotheses)
    return Corroboration(
        corroborated_dimensions=corroborated,
        independent_signal_count=len(independent),
        refuting_dimensions=refuting,
        strongest_benign_hypothesis=best_id,
        strongest_benign_posterior=best_post,
        narrative="",
    )


def default_narrative(corr: Corroboration, evidence: list[EvidenceItem]) -> str:
    """Template narrative used when no LLM is available (fallback path)."""
    dims = ", ".join(d.value for d in corr.corroborated_dimensions)
    if not dims:
        if corr.refuting_dimensions:
            return (
                "No suspicion-supporting signal survived; refuting evidence was found in "
                + ", ".join(d.value for d in corr.refuting_dimensions)
                + ". The evidence does not support escalation."
            )
        return "No significant supporting signals were identified in the dimensions examined."
    independent = independent_support_items(evidence)
    ref_sets = [sorted(_refs(e)) for e in independent]
    distinct_sources = len({r for rs in ref_sets for r in rs})
    shared = len(ref_sets) > 1 and len(set.intersection(*[set(rs) for rs in ref_sets]) if ref_sets else set()) > 0
    if shared:
        return (
            f"Supporting signals appear in {dims}, but they trace to overlapping source fields; "
            "they are treated as one underlying finding observed several times rather than "
            "genuinely independent corroboration."
        )
    return (
        f"Supporting signals arise in {dims} and trace to {distinct_sources} distinct source fields "
        f"checked against different reference sources, which makes them mutually reinforcing; "
        f"the strongest surviving benign explanation ({corr.strongest_benign_hypothesis}) stands at "
        f"posterior {corr.strongest_benign_posterior:.2f}."
    )


def run_narrative(corr: Corroboration, evidence: list[EvidenceItem], llm: Any, tag: str = "corroborate") -> str:
    """One LLM call for the narrative only; falls back to the template on failure."""
    system = load_template("corroborate")
    ind = independent_support_items(evidence)
    facts = (
        f"dimensions holding medium+ suspicion-supporting evidence (after independence penalty): "
        f"{[d.value for d in corr.corroborated_dimensions]}; "
        f"independent signal count: {corr.independent_signal_count}; "
        f"refuting dimensions: {[d.value for d in corr.refuting_dimensions]}; "
        f"strongest benign hypothesis: {corr.strongest_benign_hypothesis} "
        f"(posterior {corr.strongest_benign_posterior:.2f}).\n"
        "Independent items and their source refs:\n"
        + "\n".join(f"- {e.evidence_id} [{e.dimension.value}] refs={sorted(_refs(e))}" for e in ind)
    )
    try:
        data = llm.complete_json(
            system=system, messages=[{"role": "user", "content": facts}],
            schema={"type": "object", "properties": {"narrative": {"type": "string"}},
                    "required": ["narrative"], "additionalProperties": False},
            temperature=0.2, max_tokens=400, tag=tag,
        )
        narrative = str(data.get("narrative", "")).strip()
        return narrative or default_narrative(corr, evidence)
    except Exception:
        return default_narrative(corr, evidence)
