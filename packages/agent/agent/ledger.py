"""The evidence ledger: tool observations become EvidenceItems with stance,
weight and provenance. Provenance is assembled in Python from the tool output,
ALWAYS — the model never produces a SourceRef.
"""
from __future__ import annotations

from typing import Any

from interpretex_contracts import (
    Dimension,
    EvidenceItem,
    Hypothesis,
    Observation,
    Severity,
    SourceKind,
    SourceRef,
    Stance,
    ToolResult,
)

from .prompts import load_template
from .schemas import INTERPRET_SCHEMA

_MAX_EVIDENCE_PER_CALL = 8


def build_messages(
    hypotheses: list[Hypothesis], tool_result: ToolResult, evidence: list[EvidenceItem]
) -> tuple[str, list[dict[str, str]]]:
    system = load_template("interpret")
    hyp_lines = "\n".join(
        f"- {h.hypothesis_id} [{h.kind.value}] post={h.posterior:.2f} status={h.status.value}: {h.statement}"
        for h in hypotheses
    )
    obs_lines = []
    for o in tool_result.observations:
        rng = f" expected_range={o.expected_range}" if o.expected_range else ""
        obs_lines.append(
            f"- {o.observation_id} [{o.dimension.value}] severity={o.severity.value}{rng}: {o.statement}"
            f" metrics={o.metrics}"
        )
    ev_lines = "\n".join(f"- {e.evidence_id} [{e.dimension.value}/{e.stance.value}]: {e.statement}"
                         for e in evidence) or "(none yet)"
    status = "the tool call SUCCEEDED" if tool_result.ok else f"the tool call FAILED: {tool_result.error}"
    user = (
        f"HYPOTHESES:\n{hyp_lines}\n\n"
        f"TOOL_RESULT: {tool_result.tool} (call {tool_result.call_id}); {status}.\n"
        f"summary: {tool_result.summary}\n"
        f"observations:\n" + ("\n".join(obs_lines) or "(none)") + "\n\n"
        f"EVIDENCE so far:\n{ev_lines}\n\n"
        "Return the interpret JSON object now."
    )
    return system, [{"role": "user", "content": user}]


def _coerce_stance(raw: Any) -> Stance:
    try:
        return Stance(str(raw))
    except ValueError:
        return Stance.neutral


def _coerce_severity(raw: Any) -> Severity:
    try:
        return Severity(str(raw))
    except ValueError:
        return Severity.none


def _coerce_dimension(raw: Any) -> Dimension:
    try:
        return Dimension(str(raw))
    except ValueError:
        return Dimension.documentary


def _sources_for(observation_ids: list[str], tool_result: ToolResult) -> list[SourceRef]:
    """Provenance assembled in Python. Never trust model-produced refs."""
    by_id = {o.observation_id: o for o in tool_result.observations}
    merged: list[SourceRef] = []
    seen: set[tuple[str, str]] = set()
    for oid in observation_ids:
        obs = by_id.get(oid)
        for ref in obs.sources if obs else []:
            key = (ref.kind.value, ref.ref)
            if key not in seen:
                seen.add(key)
                merged.append(ref)
    if not merged:
        merged = list(tool_result.sources)
    if not merged:
        # provenance must never be silently broken: derive from the tool itself
        merged = [SourceRef(kind=SourceKind.derived, ref=f"{tool_result.tool}:result",
                            label=f"output of {tool_result.tool}")]
    return merged


def run_interpret(
    hypotheses: list[Hypothesis],
    tool_result: ToolResult,
    evidence_so_far: list[EvidenceItem],
    llm: Any,
    next_id: int,
    tag: str,
) -> tuple[list[EvidenceItem], list[dict[str, Any]]]:
    """LLM interpret+update. Returns (new evidence items, raw hypothesis updates).
    Raises on LLM failure — the loop degrades per stage."""
    system, messages = build_messages(hypotheses, tool_result, evidence_so_far)
    data = llm.complete_json(
        system=system, messages=messages, schema=INTERPRET_SCHEMA, temperature=0.1,
        max_tokens=1600, tag=tag,
    )
    items: list[EvidenceItem] = []
    seen_keys: set[tuple[str, tuple[str, ...]]] = {
        (e.dimension.value, tuple(sorted(e.observation_ids))) for e in evidence_so_far
    }
    known_obs = {o.observation_id for o in tool_result.observations}
    known_hyp = {h.hypothesis_id for h in hypotheses}

    for raw in (data.get("evidence") or [])[:_MAX_EVIDENCE_PER_CALL]:
        if not isinstance(raw, dict):
            continue
        obs_ids = [str(x) for x in (raw.get("observation_ids") or []) if str(x) in known_obs]
        if not obs_ids:
            continue
        key = (_coerce_dimension(raw.get("dimension")).value, tuple(sorted(obs_ids)))
        if key in seen_keys:  # dedupe
            continue
        seen_keys.add(key)
        try:
            weight = max(0.0, min(1.0, float(raw.get("weight", 0.5) or 0.5)))
        except (TypeError, ValueError):
            weight = 0.5
        hyps = [str(h) for h in (raw.get("hypotheses_affected") or []) if str(h) in known_hyp]
        items.append(
            EvidenceItem(
                evidence_id=f"E{next_id + len(items)}",
                dimension=_coerce_dimension(raw.get("dimension")),
                stance=_coerce_stance(raw.get("stance")),
                statement=str(raw.get("statement", "")).strip()
                or next((o.statement for o in tool_result.observations if o.observation_id == obs_ids[0]), ""),
                weight=weight,
                severity=_coerce_severity(_obs_severity(tool_result, obs_ids)),
                hypotheses_affected=hyps,
                observation_ids=obs_ids,
                tool_call_id=tool_result.call_id,
                sources=_sources_for(obs_ids, tool_result),
                interpretation=str(raw.get("interpretation", "")).strip() or None,
            )
        )

    updates = [
        u for u in (data.get("hypothesis_updates") or [])
        if isinstance(u, dict) and str(u.get("hypothesis_id", "")) in known_hyp
    ]
    return items, updates


def _obs_severity(tool_result: ToolResult, obs_ids: list[str]) -> str:
    by_id = {o.observation_id: o for o in tool_result.observations}
    best = Severity.none
    order = {Severity.none: 0, Severity.low: 1, Severity.medium: 2, Severity.high: 3}
    for oid in obs_ids:
        obs = by_id.get(oid)
        if obs and order[obs.severity] > order[best]:
            best = obs.severity
    return best.value


def partition(evidence: list[EvidenceItem]) -> tuple[list[EvidenceItem], list[EvidenceItem], list[EvidenceItem]]:
    """Split into (for, against, neutral)."""
    return (
        [e for e in evidence if e.stance == Stance.supports_suspicion],
        [e for e in evidence if e.stance == Stance.refutes_suspicion],
        [e for e in evidence if e.stance == Stance.neutral],
    )
