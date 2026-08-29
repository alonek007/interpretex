"""Fake WorldAPI (Part 3 stub for Part 1).

Implements the WorldAPI protocol over hand-written JSON case files in
`stubs/cases/` until Part 1's golden fixtures land; if Part 1's fixture
cases are present (contracts fixtures / data/cases), they win automatically.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from interpretex_contracts import (
    AgentCaseView,
    AttackSpec,
    CaseSpec,
    CaseSummary,
    TradeCase,
    ToolRegistry,
    WorldAPI,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stubs.fake_tools import FakeToolRegistry  # noqa: E402

STUB_CASES_DIR = Path(__file__).resolve().parent / "cases"


def _candidate_dirs() -> list[Path]:
    dirs = [STUB_CASES_DIR]
    part1 = REPO_ROOT / "data" / "cases"
    if part1.is_dir():
        dirs.append(part1)
    return dirs


class FakeWorld:
    """WorldAPI over JSON case files. Deterministic, no network, no LLM."""

    def __init__(self) -> None:
        self._cases: dict[str, TradeCase] = {}
        self._extra_cases: dict[str, TradeCase] = {}
        for d in _candidate_dirs():
            for path in sorted(d.glob("*.json")):
                try:
                    case = TradeCase.model_validate_json(path.read_text())
                except Exception:  # noqa: BLE001 - a bad file must not kill the app
                    continue
                self._cases.setdefault(case.case_id, case)

    # ------------------------------------------------------------------ API

    def list_cases(self) -> list[CaseSummary]:
        out: list[CaseSummary] = []
        for case in list(self._cases.values()) + list(self._extra_cases.values()):
            entities = {e.entity_id: e for e in case.entities}
            exporter = entities.get(case.record.exporter_id)
            importer = entities.get(case.record.importer_id)
            out.append(
                CaseSummary(
                    case_id=case.case_id,
                    title=case.title,
                    commodity=case.record.commodity,
                    quantity=case.record.quantity,
                    unit=case.record.unit,
                    total_value=case.record.total_value,
                    currency=case.record.currency,
                    exporter_name=exporter.name if exporter else case.record.exporter_id,
                    importer_name=importer.name if importer else case.record.importer_id,
                    origin_port=case.record.origin_port,
                    destination_port=case.record.destination_port,
                    document_count=len(case.documents),
                    received_at=case.received_at,
                    is_adversarial=(case.label is not None and case.label.case_class == "adversarial"),
                )
            )
        return out

    def load_case(self, case_id: str) -> TradeCase:
        case = self._cases.get(case_id) or self._extra_cases.get(case_id)
        if case is None:
            raise KeyError(case_id)
        return case

    def agent_view(self, case_id: str) -> AgentCaseView:
        """Label-stripped view. The route serialises THIS, never a TradeCase."""
        return self.load_case(case_id).to_agent_view()

    def generate_case(self, spec: CaseSpec) -> TradeCase:
        raise NotImplementedError("generate_case arrives with Part 1 (INTERPRETEX_WORLD=real)")

    def build_tool_registry(self, case: TradeCase) -> ToolRegistry:
        return FakeToolRegistry(case)

    def network_view(self, entity_id: str | None = None, depth: int = 2):
        from stubs.fake_network import network_view as _network_view

        return _network_view(entity_id=entity_id, depth=depth)

    def attack(self, spec: AttackSpec, llm=None) -> TradeCase:
        from stubs.fake_attacker import attack as _attack

        case = _attack(spec, llm)
        self._extra_cases[case.case_id] = case
        # Publish a scripted escalation trace so the replay agent (and the
        # attacker panel / replay mode) can run the generated case end to end.
        self._publish_trace(case)
        return case

    # ----------------------------------------------------- trace publishing

    def _publish_trace(self, case: TradeCase) -> None:
        """Write a scripted escalation trace for a (normally adversarial) case.

        Covers the spec's "every individual check passes, the correlation does
        not" story: each injected anomaly becomes one medium-severity evidence
        item in its own dimension, and the decision escalates on the number of
        independent dimensions rather than on any single one.
        """
        from interpretex_contracts import (
            CONTRACT_VERSION,
            AnomalyKind,
            Corroboration,
            Decision,
            Dimension,
            EvidenceGraph,
            EvidenceItem,
            Hypothesis,
            HypothesisKind,
            HypothesisStatus,
            InvestigationEvent,
            InvestigationResult,
            PlanStep,
            RunMeta,
            Severity,
            Stance,
            Triage,
            Verdict,
        )

        anomalies = list(case.label.injected_anomalies) if case.label else []
        stance_map = {
            AnomalyKind.under_invoicing: ("economic", "Declared price is -17% below benchmark — inside the 30% threshold, but the largest single deviation present."),
            AnomalyKind.over_invoicing: ("economic", "Declared price is above benchmark — inside tolerance, but the outlier on this counterparty."),
            AnomalyKind.capacity_exceeded: ("physical", "Declared cargo is 96% of vessel deadweight — within tolerance individually, yet near the vessel's limit."),
            AnomalyKind.impossible_transit: ("temporal", "Stated transit sits at the fast edge of plausibility — not impossible, but no margin."),
            AnomalyKind.insurance_after_shipment: ("documentary", "Insurance issued within the lag threshold, but after the stated shipment date."),
            AnomalyKind.description_drift: ("documentary", "Document descriptions differ by less than a hard mismatch, but enough to merit review."),
            AnomalyKind.quantity_mismatch: ("physical", "Declared quantity and documents differ within rounding tolerance."),
            AnomalyKind.historical_deviation: ("behavioural", "Price is within the customer's own history band — no anomaly on its own."),
            AnomalyKind.intermediary_reuse: ("network", "Broker recurs as broker of record in a previously escalated case — a structural pattern."),
            AnomalyKind.shared_ownership: ("network", "Ultimate beneficial owner is shared with a previously escalated counterparty."),
            AnomalyKind.route_deviation: ("temporal", "Route deviates within allowed bounds but crosses an unusual corridor."),
            AnomalyKind.hs_code_mismatch: ("documentary", "HS code differs from the declared commodity family by a marginal classification."),
        }

        evidence: list[EvidenceItem] = []
        dims: list[str] = []
        for i, an in enumerate(anomalies, start=1):
            dim, stmt = stance_map.get(
                an, ("economic", f"Injected anomaly {an.value} present within individual thresholds.")
            )
            dims.append(dim)
            evidence.append(
                EvidenceItem(
                    evidence_id=f"E{i}",
                    dimension=Dimension(dim),
                    stance=Stance.supports_suspicion,
                    statement=stmt,
                    weight=0.6,
                    severity=Severity.medium,
                    hypotheses_affected=["H1"],
                    observation_ids=[f"O{i}"],
                    sources=[{"kind": "reference_db", "ref": f"checks/{an.value}"}],
                    interpretation="Individually below the escalation threshold; counts only in correlation.",
                )
            )

        escalate = len(evidence) >= 2
        verdict = Verdict.escalate if escalate else Verdict.hold
        corr = Corroboration(
            corroborated_dimensions=[Dimension(d) for d in set(dims)],
            independent_signal_count=len(set(dims)),
            refuting_dimensions=[],
            strongest_benign_hypothesis="H2",
            strongest_benign_posterior=0.35,
            narrative=(
                "No single check trips its threshold, yet the signals span "
                f"{len(set(dims))} independent dimensions — escalation rests on correlation."
            ),
        )
        decision = Decision(
            verdict=verdict,
            confidence=0.7 if escalate else 0.5,
            headline=(
                "Escalate: correlated weak signals across independent dimensions"
                if escalate
                else "Hold: signals within individual thresholds"
            ),
            rationale=corr.narrative,
            corroboration=corr,
            caveats=[
                "Prototype. Synthetic trade data and controlled reference sources. "
                "Decision support for a human reviewer, not an automated compliance determination."
            ],
            decisive_evidence_ids=[e.evidence_id for e in evidence],
        )
        hypotheses = [
            Hypothesis(
                hypothesis_id="H1", kind=HypothesisKind.suspicious,
                statement="The trade is illicit and should be escalated.",
                explains=[Dimension(d) for d in set(dims)],
                prior=0.3, posterior=0.7 if escalate else 0.4,
                status=HypothesisStatus.supported if escalate else HypothesisStatus.open,
                supporting_evidence_ids=[e.evidence_id for e in evidence],
            ),
            Hypothesis(
                hypothesis_id="H2", kind=HypothesisKind.benign,
                statement="The pattern is benign (legitimate but unusual trade).",
                explains=[], prior=0.7, posterior=0.35,
                status=HypothesisStatus.weakened,
                contradicting_evidence_ids=[e.evidence_id for e in evidence],
            ),
        ]
        triage = Triage(
            trade_narrative=f"{case.record.commodity} shipment, {case.record.quantity} {case.record.unit}.",
            initial_concerns=["Multiple weak signals, none individually decisive."],
            unknowns=["Whether the signals correlate to a single scheme."],
            dimensions_to_probe=[Dimension(d) for d in set(dims)],
        )
        plan = [
            PlanStep(step=1, reasoning="Probe each dimension individually to confirm no single threshold is tripped.",
                     chosen_tool="check_price_benchmark", targets_hypotheses=["H1"], expected_information_gain=0.3),
            PlanStep(step=2, reasoning="Test the benign hypothesis before any escalation.",
                     chosen_tool="check_counterparty_network", targets_hypotheses=["H2"], expected_information_gain=0.4,
                     stop_reason="sufficient_evidence"),
        ]
        meta = RunMeta(run_id=f"run_stub_{case.case_id}", case_id=case.case_id, replayed=True, degraded=True)
        result = InvestigationResult(
            meta=meta,
            record=case.record,
            triage=triage,
            hypotheses=hypotheses,
            plan_steps=plan,
            tool_calls=[],
            evidence_for=evidence,
            evidence_against=[],
            evidence_neutral=[],
            budget=BudgetState(limit=6, spent=6, remaining=0, calls_made=6),
            graph=EvidenceGraph(nodes=[], edges=[]),
            decision=decision,
            evidence_requests=[],
            report_markdown=self._report_markdown(case, decision, evidence),
            events=[],
        )

        events: list[InvestigationEvent] = [
            InvestigationEvent(seq=0, run_id=f"run_stub_{case.case_id}", type="run_started",
                               narration="Investigation started (scripted adversarial trace).",
                               payload={"case_id": case.case_id, "budget": 6, "model": "stub-replay",
                                        "flags": {"budget": True, "attacker": True, "network": True, "history": True, "replay": True},
                                        "contract_version": CONTRACT_VERSION}),
            InvestigationEvent(seq=1, run_id=f"run_stub_{case.case_id}", type="case_loaded",
                               narration=f"Loaded {case.case_id}.",
                               payload={"record": case.record.model_dump(), "document_ids": [], "applicant_note": None}),
            InvestigationEvent(seq=2, run_id=f"run_stub_{case.case_id}", type="triage",
                               narration="Triage: several weak signals, none individually decisive.",
                               payload={"triage": triage.model_dump()}),
            InvestigationEvent(seq=3, run_id=f"run_stub_{case.case_id}", type="hypotheses_updated",
                               narration="Hypotheses: illicit (H1) vs benign (H2).",
                               payload={"hypotheses": [h.model_dump() for h in hypotheses], "changed_ids": ["H1", "H2"]}),
            InvestigationEvent(seq=4, run_id=f"run_stub_{case.case_id}", type="corroboration",
                               narration=corr.narrative,
                               payload={"corroboration": corr.model_dump()}),
            InvestigationEvent(seq=5, run_id=f"run_stub_{case.case_id}", type="decision",
                               narration=f"Decision: {verdict.value.upper()}.",
                               payload={"decision": decision.model_dump()}),
            InvestigationEvent(seq=6, run_id=f"run_stub_{case.case_id}", type="report_ready",
                               narration="Report ready.",
                               payload={"result": result.model_dump(), "report_markdown": result.report_markdown}),
        ]

        FIXTURES = REPO_ROOT / "stubs" / "fixtures"
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / f"{case.case_id}.events.jsonl").write_text(
            "\n".join(e.model_dump_json() for e in events) + "\n"
        )
        (FIXTURES / f"{case.case_id}.result.json").write_text(result.model_dump_json())

    @staticmethod
    def _report_markdown(case: TradeCase, decision, evidence) -> str:
        lines = [
            f"# Investigation dossier — {case.case_id}",
            "",
            f"**Verdict:** {decision.verdict.value.upper()}  ",
            f"**Confidence:** {decision.confidence}",
            "",
            "## Corroboration",
            decision.corroboration.narrative,
            "",
            "## Evidence (for suspicion)",
        ]
        for e in evidence:
            lines.append(f"- **{e.dimension.value}** ({e.severity.value}): {e.statement}")
        lines += ["", "## Caveats", *[f"- {c}" for c in decision.caveats]]
        return "\n".join(lines)
