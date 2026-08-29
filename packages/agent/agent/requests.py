"""Evidence-request generator: every HOLD must produce non-empty requests.

Derives requests from hypotheses still open or weakened by walking their
discriminating_evidence_needed and turning it into a concrete document ask.
"""
from __future__ import annotations

from interpretex_contracts import EvidenceRequest, Hypothesis, HypothesisKind, Verdict

from .prompts import load_template
from .schemas import REQUESTS_SCHEMA

# Document-ask catalogue keyed by keyword hits in hypothesis statements (section 10).
CATALOGUE: list[tuple[tuple[str, ...], str, str]] = [
    (
        ("discount", "offtake", "long-term", "contract", "pricing", "price"),
        "The original purchase or offtake contract including the pricing schedule",
        "to test whether the price deviation reflects agreed tiered or contract pricing",
    ),
    (
        ("grade", "quality", "assay"),
        "An independent inspection or assay certificate for grade and quantity",
        "to confirm the goods match the grade the price assumes",
    ),
    (
        ("weight", "capacity", "vessel", "loading"),
        "Vessel loading confirmation or stowage plan, and terminal loading records",
        "to verify the physical cargo against the declared tonnage",
    ),
    (
        ("insurance",),
        "A corrected insurance certificate with an explanation of its issue date",
        "to establish when cover attached relative to shipment",
    ),
    (
        ("transit", "voyage", "date", "transhipment"),
        "Transhipment documentation and the vessel's actual port-call log",
        "to test whether the voyage timeline is feasible as documented",
    ),
    (
        ("ownership", "intermediary", "broker", "network", "beneficial"),
        "An ultimate beneficial ownership declaration for the intermediary",
        "to establish who stands behind the shared intermediary",
    ),
    (
        ("history", "trading pattern", "prior"),
        "Prior invoices for the same commodity from the same counterparty",
        "to establish the customer's own historical price range",
    ),
    (
        ("clerical", "error", "data-entry", "documentation"),
        "Re-issued or corrected original documents for the fields in disagreement",
        "to rule out clerical error as the explanation for documentary drift",
    ),
]
DEFAULT_ITEM = "The original purchase or sale contract including the pricing schedule"
DEFAULT_WHY = "to close the remaining uncertainty on the live hypotheses"


def build_messages(verdict: Verdict, hypotheses: list[Hypothesis]) -> tuple[str, list[dict[str, str]]]:
    system = load_template("evidence_request")
    lines = "\n".join(
        f"- {h.hypothesis_id} [{h.kind.value}] post={h.posterior:.2f} status={h.status.value}: "
        f"{h.statement} | needs: {'; '.join(h.discriminating_evidence_needed) or '(unspecified)'}"
        for h in hypotheses if h.status in ("open", "weakened")
    ) or "(no live hypotheses)"
    user = f"VERDICT: {verdict.value}\n\nLIVE HYPOTHESES:\n{lines}\n\nReturn the requests JSON object now."
    return system, [{"role": "user", "content": user}]


def deterministic_requests(hypotheses: list[Hypothesis], verdict: Verdict) -> list[EvidenceRequest]:
    if verdict == Verdict.release:
        return []
    live = [h for h in hypotheses if h.status in ("open", "weakened")]
    out: list[EvidenceRequest] = []
    seen: set[str] = set()
    for h in sorted(live, key=lambda x: (-x.posterior, x.hypothesis_id)):
        text = (h.statement + " " + " ".join(h.discriminating_evidence_needed)).lower()
        matched = False
        for keywords, item, why in CATALOGUE:
            if any(k in text for k in keywords) and item not in seen:
                seen.add(item)
                out.append(
                    EvidenceRequest(
                        item=item,
                        why=f"{why} — resolves {h.hypothesis_id} "
                            f"({'benign' if h.kind == HypothesisKind.benign else 'suspicious'} explanation).",
                        resolves_hypotheses=[h.hypothesis_id],
                        priority=1 if h.posterior >= 0.45 else (2 if h.posterior >= 0.25 else 3),
                    )
                )
                matched = True
                break
        if not matched and len(out) < 4:
            item = DEFAULT_ITEM
            if item not in seen:
                seen.add(item)
                out.append(
                    EvidenceRequest(
                        item=item,
                        why=f"{DEFAULT_WHY} — resolves {h.hypothesis_id}.",
                        resolves_hypotheses=[h.hypothesis_id],
                        priority=2,
                    )
                )
    if not out and verdict == Verdict.hold:
        out.append(
            EvidenceRequest(
                item=DEFAULT_ITEM,
                why=DEFAULT_WHY,
                resolves_hypotheses=[h.hypothesis_id for h in live[:2]],
                priority=1,
            )
        )
    return out[:5]


def run_requests(
    verdict: Verdict, hypotheses: list[Hypothesis], llm: Any, tag: str = "requests"
) -> list[EvidenceRequest]:
    """LLM path; deterministic requests are the fallback and the merge base."""
    base = deterministic_requests(hypotheses, verdict)
    if base and verdict != Verdict.hold:
        return base
    if verdict == Verdict.release:
        return []
    system, messages = build_messages(verdict, hypotheses)
    known = {h.hypothesis_id for h in hypotheses}
    try:
        data = llm.complete_json(
            system=system, messages=messages, schema=REQUESTS_SCHEMA,
            temperature=0.1, max_tokens=900, tag=tag,
        )
        items = []
        for raw in (data.get("requests") or [])[:6]:
            if not isinstance(raw, dict) or not str(raw.get("item", "")).strip():
                continue
            try:
                prio = int(raw.get("priority", 2))
            except (TypeError, ValueError):
                prio = 2
            items.append(
                EvidenceRequest(
                    item=str(raw.get("item", "")).strip(),
                    why=str(raw.get("why", "")).strip() or DEFAULT_WHY,
                    resolves_hypotheses=[str(h) for h in (raw.get("resolves_hypotheses") or []) if str(h) in known],
                    priority=max(1, min(3, prio)),
                )
            )
        return items or base
    except Exception:
        return base
