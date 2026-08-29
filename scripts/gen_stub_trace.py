#!/usr/bin/env python
"""Generate scripted investigation traces for the three demo cases.

For each case writes:
  stubs/fixtures/<case_id>.events.jsonl   (one InvestigationEvent per line)
  stubs/fixtures/<case_id>.result.json    (final InvestigationResult)

fake_agent.py replays the JSONL (with a per-event delay) and yields the result
carried in the final report_ready event, so the whole UI can be built and
rehearsed before Part 2's real agent exists.

Run:  python scripts/gen_stub_trace.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from interpretex_contracts import (  # noqa: E402
    BudgetState, Corroboration, Decision, EvidenceGraph, EvidenceItem, GraphEdge,
    GraphNode, Hypothesis, InvestigationEvent, InvestigationResult, Observation,
    PlanStep, RunMeta, SourceRef, Triage, ConsideredOption, SkippedTool,
    EvidenceRequest, ToolResult, Severity, Dimension, Stance, HypothesisKind,
    HypothesisStatus, Verdict,
)

OUT = REPO_ROOT / "stubs" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)

VERDICT_CAVEATS = [
    "Reference data is synthetic and scoped to the prototype.",
    "This output is investigative decision support for a human reviewer, not a regulatory determination.",
    "Anomalies may have legitimate explanations no available tool can observe.",
]


def ev(run_id, seq, etype, narration, payload):
    return InvestigationEvent(seq=seq, run_id=run_id, type=etype, narration=narration,
                              payload=payload, ts=datetime.now(timezone.utc)).model_dump_json()


def O(oid, dim, stmt, sev, metrics, sources):
    return Observation(observation_id=oid, dimension=dim, statement=stmt, severity=sev,
                        metrics=metrics, sources=[SourceRef(**s) for s in sources]).model_dump()


def TR(call_id, tool, summary, observations, cost=1):
    return ToolResult(tool=tool, call_id=call_id, ok=True, summary=summary,
                      observations=[Observation(**o) for o in observations],
                      cost_units=cost, latency_ms=15).model_dump()


def node(nid, kind, label, dimension=None, stance=None, severity=None, meta=None):
    return GraphNode(id=nid, kind=kind, label=label, dimension=dimension, stance=stance,
                     severity=severity, meta=meta or {}).model_dump()


def edge(s, t, relation, label=None):
    return GraphEdge(source=s, target=t, relation=relation, label=label).model_dump()


def build_clean():
    run_id = "run_stub_clean_001"
    lines = []
    seq = 0

    def emit(etype, narration, payload):
        nonlocal seq
        lines.append(ev(run_id, seq, etype, narration, payload))
        seq += 1

    emit("run_started", "Investigation started for case_clean_001 (budget 6).",
         {"case_id": "case_clean_001", "budget": 6, "model": "stub-replay", "flags": {"budget": True}, "contract_version": "1.0.0"})
    emit("case_loaded", "Loaded 6 documents; coffee, Santos to Rotterdam, declared USD 4,420/t.",
         {"record": {"commodity": "Green coffee beans, arabica", "quantity": 480, "unit": "t", "unit_price": 4420, "total_value": 2121600, "origin_port": "BRSSZ", "destination_port": "NLRTM", "vessel_name": "MV Pacific Dawn", "exporter_id": "E-SANTOS-VERDE", "importer_id": "E-ROTTERDAM-ROAST"},
          "document_ids": ["LC-2026-04417", "INV-2026-0731", "BL-2026-771204", "PL-2026-0731", "COO-BR-11872", "INS-2026-5581"], "applicant_note": "Renewal of seasonal financing."})
    emit("triage", "Triage: routine coffee renewal, one mild price flag to confirm.",
         {"triage": Triage(trade_narrative="Green coffee beans, 480 t, Santos to Rotterdam on MV Pacific Dawn, declared USD 4,420/t under a renewed seasonal LC.",
                           initial_concerns=["Declared price is slightly below the recent market level."], unknowns=["Whether the small discount reflects a market move or mispricing."], dimensions_to_probe=["economic", "documentary"]).model_dump()})
    emit("hypotheses_updated", "Formed 3 hypotheses (1 suspicious, 2 benign).",
         {"hypotheses": [
             Hypothesis(hypothesis_id="H1", kind="benign", statement="Price reflects a benign market move / grade within range.", explains=["economic"], prior=0.6, posterior=0.6, status="open").model_dump(),
             Hypothesis(hypothesis_id="H2", kind="benign", statement="Documents are internally consistent and routine.", explains=["documentary"], prior=0.7, posterior=0.7, status="open").model_dump(),
             Hypothesis(hypothesis_id="H3", kind="suspicious", statement="Coffee is under-invoiced to move value.", explains=["economic"], prior=0.1, posterior=0.1, status="open", discriminating_evidence_needed=["price benchmark below band", "contrary trade history"]).model_dump(),
         ], "changed_ids": ["H1", "H2", "H3"]})
    emit("plan_step", "Plan: check the price benchmark first; benign explanations are cheap to confirm.",
         {"plan_step": PlanStep(step=1, reasoning="Single mild economic flag dominates; confirm price before spending more.", chosen_tool="check_price_benchmark",
                                 chosen_args={"commodity": "Green coffee beans, arabica", "as_of_date": "2026-07", "declared_unit_price": 4420}, targets_hypotheses=["H1", "H3"], expected_information_gain=0.6,
                                 considered=[ConsideredOption(tool="check_document_consistency", expected_information_gain=0.2, why_not="No documentary flag; defer until price is understood."),
                                             ConsideredOption(tool="check_vessel_capacity", expected_information_gain=0.05, why_not="Coffee well within vessel capacity; no physical question.")]).model_dump()})
    emit("tool_call_started", "Calling check_price_benchmark...",
         {"call_id": "c1", "tool": "check_price_benchmark", "args": {"commodity": "Green coffee beans, arabica", "as_of_date": "2026-07", "declared_unit_price": 4420}, "targets_hypotheses": ["H1", "H3"]})
    emit("tool_call_completed", "Price is -1.8% vs benchmark, inside band.",
         {"tool_result": TR("c1", "check_price_benchmark", "Price 4,420 vs 4,500 benchmark (-1.8%)",
                            [O("O1", "economic", "Declared unit price 4,420 USD/t vs 2026-07 benchmark 4,500 (-1.8%).", "none", {"declared": 4420.0, "benchmark": 4500.0, "deviation_pct": -1.8}, [{"kind": "reference_db", "ref": "benchmarks/green coffee beans, arabica/2026-07", "value": "4500", "as_of": "2026-07"}])])})
    emit("evidence_added", "Evidence E1: price inside benchmark band - refutes suspicion.",
         {"evidence": EvidenceItem(evidence_id="E1", dimension="economic", stance="refutes_suspicion", statement="Declared price 4,420 USD/t is -1.8% below the July 2026 benchmark, well within the +/-6% band.", weight=0.7, severity="none", hypotheses_affected=["H1", "H3"], observation_ids=["O1"], sources=[SourceRef(kind="reference_db", ref="benchmarks/green coffee beans, arabica/2026-07", value="4500", as_of="2026-07")], interpretation="A sub-2% gap is routine grade/lot variation, not a mispricing signal.").model_dump()})
    emit("budget_updated", "Budget: 1 of 6 spent.", {"budget": BudgetState(limit=6, spent=1, remaining=5, calls_made=1, exhaustive_cost=10).model_dump()})
    emit("plan_step", "Plan: confirm documents; then sufficient evidence to stop.",
         {"plan_step": PlanStep(step=2, reasoning="Economic flag resolved benignly; confirm documents are consistent, then the short trace is justified.", chosen_tool="check_document_consistency", chosen_args={}, targets_hypotheses=["H2"], expected_information_gain=0.3, considered=[ConsideredOption(tool="check_historical_trade", expected_information_gain=0.1, why_not="Routine customer; history unlikely to move the verdict.")]).model_dump()})
    emit("tool_call_started", "Calling check_document_consistency...",
         {"call_id": "c2", "tool": "check_document_consistency", "args": {}, "targets_hypotheses": ["H2"]})
    emit("tool_call_completed", "All documents agree; no internal inconsistency.",
         {"tool_result": TR("c2", "check_document_consistency", "All documents agree on commodity, quantity, value and chronology.",
                            [O("O2", "documentary", "All documents agree on commodity, quantity, value and chronology; no internal inconsistency found.", "none", {}, [])])})
    emit("evidence_added", "Evidence E2: documents internally consistent.",
         {"evidence": EvidenceItem(evidence_id="E2", dimension="documentary", stance="refutes_suspicion", statement="LC, invoice, B/L, packing list, certificate of origin and insurance all agree on commodity, quantity, value and chronology.", weight=0.6, severity="none", hypotheses_affected=["H2"], observation_ids=["O2"], sources=[SourceRef(kind="document", ref="LC-2026-04417", label="letter_of_credit")], interpretation="No documentary signal; the only mild flag was economic and is benign.").model_dump()})
    emit("budget_updated", "Budget: 2 of 6 spent.", {"budget": BudgetState(limit=6, spent=2, remaining=4, calls_made=2, exhaustive_cost=10).model_dump()})
    emit("graph_updated", "Graph: case fields connected to two refuting evidence nodes.",
         {"nodes_added": [node("case_clean_001", "document", "case_clean_001: coffee 480t", dimension="economic"),
                          node("E1", "finding", "E1 price inside band", dimension="economic", stance="refutes_suspicion"),
                          node("E2", "finding", "E2 docs consistent", dimension="documentary", stance="refutes_suspicion")],
          "edges_added": [edge("case_clean_001", "E1", "produced"), edge("case_clean_001", "E2", "produced"), edge("benchmarks/green coffee beans, arabica/2026-07", "E1", "states")]})
    emit("corroboration", "Corroboration: only benign signals in two dimensions.",
         {"corroboration": Corroboration(corroborated_dimensions=["economic", "documentary"], independent_signal_count=0, refuting_dimensions=["economic", "documentary"], strongest_benign_hypothesis="H1", strongest_benign_posterior=0.9, narrative="The only economic flag resolves benignly (price within band); documents are consistent. There is no suspicion-supporting signal in any dimension, so escalation is off the table by construction.").model_dump()})
    emit("plan_step", "Plan: sufficient evidence - stop early.",
         {"plan_step": PlanStep(step=3, reasoning="No corroborated anomaly and the benign explanations are confirmed; continuing would be a checklist, not an investigation.", chosen_tool=None, chosen_args={}, expected_information_gain=0.0, stop_reason="sufficient_evidence").model_dump()})
    emit("decision", "Decision: RELEASE. No significant corroborated anomaly identified.",
         {"decision": Decision(verdict="release", confidence=0.82, headline="No significant corroborated anomaly identified - recommend release.", rationale="The declared price (-1.8%) sits inside the benchmark band and the documents are internally consistent. With no suspicion-supporting evidence in any dimension, the case does not meet the bar for hold or escalation.", corroboration=Corroboration(corroborated_dimensions=["economic", "documentary"], independent_signal_count=0, refuting_dimensions=["economic", "documentary"], strongest_benign_hypothesis="H1", strongest_benign_posterior=0.9, narrative="Benign across two dimensions; no signal to escalate."), caveats=VERDICT_CAVEATS, decisive_evidence_ids=["E1", "E2"]).model_dump()})
    emit("evidence_requested", "No documents requested - nothing materially uncertain.", {"requests": []})
    result = InvestigationResult(
        meta=RunMeta(run_id=run_id, case_id="case_clean_001", model="stub-replay"),
        record={"commodity": "Green coffee beans, arabica", "quantity": 480, "unit": "t", "unit_price": 4420, "total_value": 2121600, "currency": "USD", "origin_port": "BRSSZ", "destination_port": "NLRTM", "vessel_name": "MV Pacific Dawn", "exporter_id": "E-SANTOS-VERDE", "importer_id": "E-ROTTERDAM-ROAST"},
        triage=Triage(trade_narrative="Green coffee beans, 480 t, Santos to Rotterdam.", initial_concerns=["mild price flag"], unknowns=["market move vs mispricing"], dimensions_to_probe=["economic", "documentary"]),
        hypotheses=[
            Hypothesis(hypothesis_id="H1", kind="benign", statement="Price reflects a benign market move / grade within range.", explains=["economic"], prior=0.6, posterior=0.9, status="supported"),
            Hypothesis(hypothesis_id="H2", kind="benign", statement="Documents are internally consistent and routine.", explains=["documentary"], prior=0.7, posterior=0.92, status="supported"),
            Hypothesis(hypothesis_id="H3", kind="suspicious", statement="Coffee is under-invoiced to move value.", explains=["economic"], prior=0.1, posterior=0.04, status="refuted"),
        ],
        plan_steps=[PlanStep(step=1, reasoning="confirm price", chosen_tool="check_price_benchmark", chosen_args={}, targets_hypotheses=["H1", "H3"], expected_information_gain=0.6),
                    PlanStep(step=2, reasoning="confirm docs", chosen_tool="check_document_consistency", chosen_args={}, targets_hypotheses=["H2"], expected_information_gain=0.3),
                    PlanStep(step=3, reasoning="sufficient evidence", chosen_tool=None, chosen_args={}, expected_information_gain=0.0, stop_reason="sufficient_evidence")],
        tool_calls=[],
        evidence_for=[], evidence_against=[EvidenceItem(evidence_id="E1", dimension="economic", stance="refutes_suspicion", statement="Price within band.", weight=0.7, severity="none", hypotheses_affected=["H1", "H3"], observation_ids=["O1"]),
                                      EvidenceItem(evidence_id="E2", dimension="documentary", stance="refutes_suspicion", statement="Documents consistent.", weight=0.6, severity="none", hypotheses_affected=["H2"], observation_ids=["O2"])],
        evidence_neutral=[],
        budget=BudgetState(limit=6, spent=2, remaining=4, calls_made=2, exhaustive_cost=10),
        graph=EvidenceGraph(nodes=[GraphNode(id="case_clean_001", kind="document", label="case_clean_001: coffee 480t", dimension="economic"),
                                    GraphNode(id="E1", kind="finding", label="E1 price inside band", dimension="economic", stance="refutes_suspicion"),
                                    GraphNode(id="E2", kind="finding", label="E2 docs consistent", dimension="documentary", stance="refutes_suspicion")],
                           edges=[GraphEdge(source="case_clean_001", target="E1", relation="produced"), GraphEdge(source="case_clean_001", target="E2", relation="produced")]),
        decision=Decision(verdict="release", confidence=0.82, headline="No significant corroborated anomaly identified - recommend release.", rationale="The declared price (-1.8%) sits inside the benchmark band and the documents are internally consistent.", corroboration=Corroboration(corroborated_dimensions=["economic", "documentary"], independent_signal_count=0, refuting_dimensions=["economic", "documentary"], strongest_benign_hypothesis="H1", strongest_benign_posterior=0.9, narrative="Benign across two dimensions."), caveats=VERDICT_CAVEATS, decisive_evidence_ids=["E1", "E2"]),
        evidence_requests=[],
        report_markdown="# Investigation dossier - case_clean_001\n\n## Recommendation: RELEASE\n\nNo significant corroborated anomaly identified. The declared price (-1.8%) is within the benchmark band and all six documents are internally consistent.\n\n## Evidence against suspicion\n- E1 (economic): price within band.\n- E2 (documentary): documents consistent.\n\n## Caveats\n- Reference data is synthetic and scoped to the prototype.\n- This output is investigative decision support, not a regulatory determination.",
        events=[])
    emit("report_ready", "Dossier ready - verdict RELEASE.",
         {"result": result.model_dump(mode="json"), "report_markdown": result.report_markdown})
    return lines, result.model_dump(mode="json")


def build_suspicious():
    run_id = "run_stub_susp_003"
    lines = []
    seq = 0

    def emit(etype, narration, payload):
        nonlocal seq
        lines.append(ev(run_id, seq, etype, narration, payload))
        seq += 1

    emit("run_started", "Investigation started for case_suspicious_003 (budget 6).",
         {"case_id": "case_suspicious_003", "budget": 6, "model": "stub-replay", "flags": {"budget": True}, "contract_version": "1.0.0"})
    emit("case_loaded", "Loaded 6 documents; copper cathodes, Singapore to Nhava Sheva, declared USD 5,500/t.",
         {"record": {"commodity": "Copper cathodes", "quantity": 2200, "unit": "t", "unit_price": 5500, "total_value": 12100000, "origin_port": "SGSIN", "destination_port": "INNSA", "vessel_name": "MV Ocean Star", "exporter_id": "E-STRAITS-COMM", "importer_id": "E-DECCAN-COPPER"},
          "document_ids": ["LC-2026-05344", "INV-2026-0912", "BL-2026-903118", "PL-2026-0912", "COO-SG-33128", "INS-2026-7409"], "applicant_note": "Urgent financing request."})
    emit("triage", "Triage: large copper trade priced far below market with several timeline red flags.",
         {"triage": Triage(trade_narrative="Copper cathodes, 2,200 t, Singapore to Nhava Sheva on MV Ocean Star, declared USD 5,500/t against a market near USD 8,900/t, with a 1-day stated transit and insurance issued after shipment.", initial_concerns=["Price ~38% below benchmark.", "Cargo exceeds the named vessel's capacity.", "Transit time physically impossible.", "Insurance issued after the voyage.", "Packing list describes scrap, invoice cathodes."], unknowns=["Whether the counterparty network repeats a pattern.", "Whether a benign commercial explanation exists in the file."], dimensions_to_probe=["economic", "physical", "temporal", "documentary", "behavioural", "network"]).model_dump()})
    emit("hypotheses_updated", "Formed hypotheses: under-invoicing (suspicious), benign discount, benign data error, benign grade difference.",
         {"hypotheses": [
             Hypothesis(hypothesis_id="H1", kind="suspicious", statement="Copper is under-invoiced to move value (TBML-style).", explains=["economic", "physical", "documentary"], prior=0.5, posterior=0.5, status="open", discriminating_evidence_needed=["price deviation", "capacity", "transit", "insurance timing", "network pattern"]).model_dump(),
             Hypothesis(hypothesis_id="H2", kind="benign", statement="Price reflects a genuine volume discount / long-term offtake.", explains=["economic"], prior=0.2, posterior=0.2, status="open").model_dump(),
             Hypothesis(hypothesis_id="H3", kind="benign", statement="Documents contain a clerical error, not evasion.", explains=["documentary"], prior=0.15, posterior=0.15, status="open").model_dump(),
             Hypothesis(hypothesis_id="H4", kind="benign", statement="Commodity is genuinely lower grade (scrap) and priced accordingly.", explains=["documentary"], prior=0.15, posterior=0.15, status="open").model_dump(),
         ], "changed_ids": ["H1", "H2", "H3", "H4"]})
    emit("plan_step", "Plan: test the price benchmark - the most discriminating single signal.",
         {"plan_step": PlanStep(step=1, reasoning="A 38% price gap is the single most informative discriminator; resolve it before spending on physical/network checks.", chosen_tool="check_price_benchmark", chosen_args={"commodity": "Copper cathodes", "as_of_date": "2026-08", "declared_unit_price": 5500}, targets_hypotheses=["H1", "H2"], expected_information_gain=0.8, considered=[ConsideredOption(tool="check_document_consistency", expected_information_gain=0.4, why_not="Do alongside; price first because it sets the stakes."), ConsideredOption(tool="check_counterparty_network", expected_information_gain=0.3, why_not="Network is corroborating, not discriminating, at this stage.")]).model_dump()})
    emit("tool_call_started", "Calling check_price_benchmark...",
         {"call_id": "c1", "tool": "check_price_benchmark", "args": {"commodity": "Copper cathodes", "as_of_date": "2026-08", "declared_unit_price": 5500}, "targets_hypotheses": ["H1", "H2"]})
    emit("tool_call_completed", "Price is -38.2% vs benchmark.",
         {"tool_result": TR("c1", "check_price_benchmark", "Price 5,500 vs 8,900 benchmark (-38.2%)", [O("O1", "economic", "Declared 5,500 USD/t vs 2026-08 benchmark 8,900 (-38.2%).", "high", {"declared": 5500.0, "benchmark": 8900.0, "deviation_pct": -38.2}, [{"kind": "reference_db", "ref": "benchmarks/copper cathodes/2026-08", "value": "8900", "as_of": "2026-08"}])])})
    emit("evidence_added", "Evidence E1 (economic, supports suspicion): -38.2% price gap.",
         {"evidence": EvidenceItem(evidence_id="E1", dimension="economic", stance="supports_suspicion", statement="Declared unit price 5,500 USD/t is -38.2% below the August 2026 copper benchmark, far outside the +/-6% band.", weight=0.9, severity="high", hypotheses_affected=["H1", "H2"], observation_ids=["O1"], sources=[SourceRef(kind="reference_db", ref="benchmarks/copper cathodes/2026-08", value="8900", as_of="2026-08")], interpretation="A gap this size is not a benign volume discount; discounts of this magnitude are not observed in the reference set.").model_dump()})
    emit("budget_updated", "Budget: 1 of 6 spent.", {"budget": BudgetState(limit=6, spent=1, remaining=5, calls_made=1, exhaustive_cost=10).model_dump()})
    emit("plan_step", "Plan: test vessel capacity - physical discriminator.",
         {"plan_step": PlanStep(step=2, reasoning="If the cargo exceeds the vessel, that independently corroborates a physical impossibility.", chosen_tool="check_vessel_capacity", chosen_args={}, targets_hypotheses=["H1", "H3"], expected_information_gain=0.7, considered=[ConsideredOption(tool="check_transit_plausibility", expected_information_gain=0.6, why_not="Next; capacity is a cleaner yes/no first.")]).model_dump()})
    emit("tool_call_started", "Calling check_vessel_capacity...",
         {"call_id": "c2", "tool": "check_vessel_capacity", "args": {}, "targets_hypotheses": ["H1", "H3"]})
    emit("tool_call_completed", "Cargo 122% of vessel capacity.",
         {"tool_result": TR("c2", "check_vessel_capacity", "Capacity 2,205/1,800 t (122.5%)", [O("O2", "physical", "Declared 2,205 t load exceeds the MV Ocean Star capacity of 1,800 t (122.5%).", "high", {"dwt_tons": 1800.0, "claimed_tons": 2204.8, "utilisation_pct": 122.5}, [{"kind": "document", "ref": "BL-2026-903118.gross_weight_tons", "value": "2204.8"}, {"kind": "reference_db", "ref": "vessels/MV Ocean Star", "value": "1800"}])])})
    emit("evidence_added", "Evidence E2 (physical, supports suspicion): over capacity.",
         {"evidence": EvidenceItem(evidence_id="E2", dimension="physical", stance="supports_suspicion", statement="Declared cargo 2,205 t exceeds the MV Ocean Star deadweight of 1,800 t (122.5% utilisation) - physically impossible as declared.", weight=0.85, severity="high", hypotheses_affected=["H1", "H3"], observation_ids=["O2"], sources=[SourceRef(kind="document", ref="BL-2026-903118.gross_weight_tons", value="2204.8"), SourceRef(kind="reference_db", ref="vessels/MV Ocean Star", value="1800")], interpretation="The bill of lading overstates cargo relative to the vessel; consistent with misdeclared goods.").model_dump()})
    emit("budget_updated", "Budget: 2 of 6 spent.", {"budget": BudgetState(limit=6, spent=2, remaining=4, calls_made=2, exhaustive_cost=10).model_dump()})
    emit("plan_step", "Plan: test transit plausibility - temporal discriminator.",
         {"plan_step": PlanStep(step=3, reasoning="A 1-day Singapore-Nhava Sheva transit implies a speed no vessel reaches; if confirmed, that is a third independent dimension.", chosen_tool="check_transit_plausibility", chosen_args={}, targets_hypotheses=["H1"], expected_information_gain=0.7, considered=[ConsideredOption(tool="check_historical_trade", expected_information_gain=0.4, why_not="Behavioural next; transit is a harder yes/no.")]).model_dump()})
    emit("tool_call_started", "Calling check_transit_plausibility...",
         {"call_id": "c3", "tool": "check_transit_plausibility", "args": {}, "targets_hypotheses": ["H1"]})
    emit("tool_call_completed", "Transit implies ~87 knots - impossible.",
         {"tool_result": TR("c3", "check_transit_plausibility", "Transit 1 d, implied 87 kn (max 14)", [O("O3", "temporal", "Claimed 1-day transit over ~3,900 km implies ~87 knots vs the vessel's 14.5-knot max - impossible.", "high", {"great_circle_km": 3900, "expected_days": 7.5, "claimed_days": 1, "implied_speed_knots": 87.0, "vessel_max_knots": 14.5}, [{"kind": "document", "ref": "BL-2026-903118.ship_date", "value": "2026-08-10"}, {"kind": "document", "ref": "BL-2026-903118.arrival_date", "value": "2026-08-11"}])])})
    emit("evidence_added", "Evidence E3 (temporal, supports suspicion): impossible transit.",
         {"evidence": EvidenceItem(evidence_id="E3", dimension="temporal", stance="supports_suspicion", statement="The stated 1-day transit implies a speed (~87 kn) no vessel can reach; the voyage as documented did not happen as claimed.", weight=0.85, severity="high", hypotheses_affected=["H1"], observation_ids=["O3"], sources=[SourceRef(kind="document", ref="BL-2026-903118.ship_date", value="2026-08-10"), SourceRef(kind="document", ref="BL-2026-903118.arrival_date", value="2026-08-11")], interpretation="A fabricated or backdated timeline is consistent with document fraud.").model_dump()})
    emit("budget_updated", "Budget: 3 of 6 spent.", {"budget": BudgetState(limit=6, spent=3, remaining=3, calls_made=3, exhaustive_cost=10).model_dump()})
    emit("plan_step", "Plan: test document consistency - documentary discriminator (and the benign grade hypothesis).",
         {"plan_step": PlanStep(step=4, reasoning="The packing-list/scrap vs invoice/cathodes drift directly tests H4 (benign grade) and H3 (error vs evasion).", chosen_tool="check_document_consistency", chosen_args={}, targets_hypotheses=["H3", "H4"], expected_information_gain=0.6, considered=[ConsideredOption(tool="read_document", expected_information_gain=0.2, why_not="Already have fields via consistency.")]).model_dump()})
    emit("tool_call_started", "Calling check_document_consistency...",
         {"call_id": "c4", "tool": "check_document_consistency", "args": {}, "targets_hypotheses": ["H3", "H4"]})
    emit("tool_call_completed", "Description drift (scrap vs cathodes) + late insurance.",
         {"tool_result": TR("c4", "check_document_consistency", "Description drift: Copper Scrap vs Copper Cathodes; insurance 8 days after shipment",
                            [O("O4a", "documentary", "Commodity description differs: 'Copper Scrap' (packing list) vs 'Copper Cathodes' (invoice).", "high", {"distinct_descriptions": 2}, [{"kind": "document", "ref": "PL-2026-0912.commodity", "value": "Copper Scrap"}, {"kind": "document", "ref": "INV-2026-0912.commodity", "value": "Copper Cathodes"}]),
                             O("O4b", "documentary", "Insurance certificate issued 8 days after the stated shipment date - retroactive coverage.", "high", {"insurance_lag_days": 8.0}, [{"kind": "document", "ref": "INS-2026-7409.insurance_issue_date", "value": "2026-08-18"}, {"kind": "document", "ref": "BL-2026-903118.ship_date", "value": "2026-08-10"}])])})
    emit("evidence_added", "Evidence E4 (documentary, supports suspicion): description drift + retroactive insurance.",
         {"evidence": EvidenceItem(evidence_id="E4", dimension="documentary", stance="supports_suspicion", statement="Packing list declares 'Copper Scrap' while the invoice declares 'Copper Cathodes', and insurance was issued 8 days after shipment.", weight=0.8, severity="high", hypotheses_affected=["H1", "H3", "H4"], observation_ids=["O4a", "O4b"], sources=[SourceRef(kind="document", ref="PL-2026-0912.commodity", value="Copper Scrap"), SourceRef(kind="document", ref="INS-2026-7409.insurance_issue_date", value="2026-08-18")], interpretation="The description drift defeats H4 (genuine grade) and the retroactive insurance defeats H3 (benign clerical error): the documents were constructed, not mismatched.").model_dump()})
    emit("plan_step", "Plan: test the benign discount hypothesis directly (required before any escalation).",
         {"plan_step": PlanStep(step=5, reasoning="Policy requires a tested benign hypothesis. Check whether a contract in the file supports a discount.", chosen_tool="check_contract_or_supporting_evidence", chosen_args={"claim": "long_term_offtake"}, targets_hypotheses=["H2"], expected_information_gain=0.5, considered=[ConsideredOption(tool="check_historical_trade", expected_information_gain=0.4, why_not="Run next; the contract check is the decisive benign test.")]).model_dump()})
    emit("tool_call_started", "Calling check_contract_or_supporting_evidence (long_term_offtake)...",
         {"call_id": "c5", "tool": "check_contract_or_supporting_evidence", "args": {"claim": "long_term_offtake"}, "targets_hypotheses": ["H2"]})
    emit("tool_call_completed", "No supporting contract found.",
         {"tool_result": TR("c5", "check_contract_or_supporting_evidence", "No supporting document for 'long_term_offtake'", [O("O5", "economic", "No document in the file supports a long-term offtake or volume discount.", "medium", {}, [{"kind": "document", "ref": "case.documents", "value": "not_found"}])])})
    emit("evidence_added", "Evidence E5 (economic, refutes benign discount): no contract in file.",
         {"evidence": EvidenceItem(evidence_id="E5", dimension="economic", stance="refutes_suspicion", statement="The benign discount hypothesis (H2) was tested and not supported: no offtake or volume-discount contract exists in the file.", weight=0.6, severity="medium", hypotheses_affected=["H2"], observation_ids=["O5"], sources=[SourceRef(kind="document", ref="case.documents", value="not_found")], interpretation="H2 is materially weakened; the price gap has no benign documented cause.").model_dump()})
    emit("budget_updated", "Budget: 4 of 6 spent.", {"budget": BudgetState(limit=6, spent=4, remaining=2, calls_made=4, exhaustive_cost=10).model_dump()})
    emit("plan_step", "Plan: corroborate with history + network (behavioural + network reinforcement).",
         {"plan_step": PlanStep(step=6, reasoning="Two cheap checks remain to confirm the pattern is structural, not a one-off price outlier.", chosen_tool="check_historical_trade", chosen_args={"entity_id": "E-DECCAN-COPPER", "commodity": "Copper cathodes"}, targets_hypotheses=["H1"], expected_information_gain=0.4, considered=[ConsideredOption(tool="check_counterparty_network", expected_information_gain=0.4, why_not="Run as the final step; both are corroborating.")]).model_dump()})
    emit("tool_call_started", "Calling check_historical_trade...",
         {"call_id": "c6", "tool": "check_historical_trade", "args": {"entity_id": "E-DECCAN-COPPER", "commodity": "Copper cathodes"}, "targets_hypotheses": ["H1"]})
    emit("tool_call_completed", "Price far below this importer's own history.",
         {"tool_result": TR("c6", "check_historical_trade", "History 8,600-9,100, z=-26.80", [O("O6", "behavioural", "This importer's 7 prior copper trades ranged 8,600-9,100 USD/t (median 8,850); current 5,500 is z=-26.8.", "high", {"median": 8850.0, "min": 8600.0, "max": 9100.0, "n": 7, "z_score": -26.8}, [{"kind": "reference_db", "ref": "history/E-DECCAN-COPPER/copper cathodes", "value": "8600-9100"}])], cost=2)})
    emit("evidence_added", "Evidence E6 (behavioural, supports suspicion): 27-sigma below the importer's own history.",
         {"evidence": EvidenceItem(evidence_id="E6", dimension="behavioural", stance="supports_suspicion", statement="The declared price is ~27 standard deviations below this importer's own prior copper trades - not a price the customer has ever paid.", weight=0.75, severity="high", hypotheses_affected=["H1"], observation_ids=["O6"], sources=[SourceRef(kind="reference_db", ref="history/E-DECCAN-COPPER/copper cathodes", value="8600-9100")], interpretation="Behavioural corroboration of mispricing; the importer's own record contradicts the invoice.").model_dump()})
    emit("tool_call_started", "Calling check_counterparty_network...",
         {"call_id": "c7", "tool": "check_counterparty_network", "args": {}, "targets_hypotheses": ["H1"]})
    emit("tool_call_completed", "Broker recurs in three escalated cases.",
         {"tool_result": TR("c7", "check_counterparty_network", "Broker Meridian Trade Partners in 3 prior escalated cases; shared UBO", [O("O7", "network", "Broker Meridian Trade Partners is the broker of record in three previously escalated cases and shares a UBO with the vessel owner.", "high", {"prior_escalations": 3}, [{"kind": "reference_db", "ref": "network/intermediary_reuse", "value": "E-MERIDIAN-TP"}])], cost=2)})
    emit("evidence_added", "Evidence E7 (network, supports suspicion): recurring broker + shared ownership.",
         {"evidence": EvidenceItem(evidence_id="E7", dimension="network", stance="supports_suspicion", statement="The broker recurs across three prior escalated cases and shares an ultimate beneficial owner with the vessel owner - a structural pattern, not coincidence.", weight=0.7, severity="high", hypotheses_affected=["H1"], observation_ids=["O7"], sources=[SourceRef(kind="reference_db", ref="network/intermediary_reuse", value="E-MERIDIAN-TP")], interpretation="Network corroboration: the same actors appear in other flagged trades.").model_dump()})
    emit("budget_updated", "Budget: 6 of 6 spent.", {"budget": BudgetState(limit=6, spent=6, remaining=0, calls_made=6, exhaustive_cost=10, tools_skipped=[SkippedTool(tool="check_container_volume_consistency", reason="Budget exhausted; six dimensions already corroborated.")]).model_dump()})
    emit("graph_updated", "Graph: seven finding nodes across four corroborated dimensions, rooted at the documents.",
         {"nodes_added": [
             node("case_suspicious_003", "document", "case_suspicious_003", dimension="economic"),
             node("E1", "finding", "E1 price -38.2%", dimension="economic", stance="supports_suspicion", severity="high"),
             node("E2", "finding", "E2 cargo > capacity", dimension="physical", stance="supports_suspicion", severity="high"),
             node("E3", "finding", "E3 impossible transit", dimension="temporal", stance="supports_suspicion", severity="high"),
             node("E4", "finding", "E4 scrap vs cathodes + late insurance", dimension="documentary", stance="supports_suspicion", severity="high"),
             node("E5", "finding", "E5 no discount contract", dimension="economic", stance="refutes_suspicion", severity="medium"),
             node("E6", "finding", "E6 27-sigma below history", dimension="behavioural", stance="supports_suspicion", severity="high"),
             node("E7", "finding", "E7 recurring broker", dimension="network", stance="supports_suspicion", severity="high"),
             node("H1", "hypothesis", "H1 under-invoicing"),
             node("benchmarks/copper cathodes/2026-08", "reference", "benchmark 8,900", dimension="economic"),
         ], "edges_added": [
             edge("case_suspicious_003", "E1", "produced"), edge("benchmarks/copper cathodes/2026-08", "E1", "states"),
             edge("case_suspicious_003", "E2", "produced"), edge("case_suspicious_003", "E3", "produced"),
             edge("case_suspicious_003", "E4", "produced"), edge("case_suspicious_003", "E5", "produced"),
             edge("case_suspicious_003", "E6", "produced"), edge("case_suspicious_003", "E7", "produced"),
             edge("E1", "H1", "supports"), edge("E2", "H1", "supports"), edge("E3", "H1", "supports"),
             edge("E4", "H1", "supports"), edge("E6", "H1", "supports"), edge("E7", "H1", "supports"),
             edge("E5", "H1", "refutes"),
         ]})
    emit("corroboration", "Corroboration: four independent dimensions plus behavioural/network reinforcement.",
         {"corroboration": Corroboration(corroborated_dimensions=["economic", "physical", "temporal", "documentary"], independent_signal_count=4, refuting_dimensions=[], strongest_benign_hypothesis="H2", strongest_benign_posterior=0.05, narrative="Price, capacity, transit and description each come from a different source field and a different reference, so they are independent signals. History and network reinforce. The benign discount and grade hypotheses were tested and not supported. This is corroboration across independent dimensions, which is the escalation bar.").model_dump()})
    emit("decision", "Decision: ESCALATE - indicators consistent with potential under-invoicing / trade-value manipulation.",
         {"decision": Decision(verdict="escalate", confidence=0.9, headline="Indicators consistent with potential under-invoicing / trade-value manipulation across four independent dimensions.", rationale="Suspicion-supporting evidence at medium+ severity appears in four distinct dimensions (economic -38.2% price; physical - cargo over vessel capacity; temporal - impossible transit; documentary - description drift and retroactive insurance), each from an independent source. The benign discount and grade hypotheses were tested and not supported. Escalation is the deterministic-policy outcome for multi-dimension corroboration with a tested-and-failing benign explanation. Note: this is an investigative indicator, not a finding of money laundering.", corroboration=Corroboration(corroborated_dimensions=["economic", "physical", "temporal", "documentary"], independent_signal_count=4, refuting_dimensions=[], strongest_benign_hypothesis="H2", strongest_benign_posterior=0.05, narrative="Four independent dimensions; benign hypotheses tested and failed."), typology="Indicators consistent with potential under-invoicing / trade-value manipulation", caveats=VERDICT_CAVEATS, decisive_evidence_ids=["E1", "E2", "E3", "E4"]).model_dump()})
    emit("evidence_requested", "Request documents to close the remaining uncertainty.",
         {"requests": [EvidenceRequest(item="Current-year pricing addendum from the exporter", why="Confirms whether any genuine discount basis exists.", resolves_hypotheses=["H2"], priority=1).model_dump(),
                      EvidenceRequest(item="Independent pre-shipment inspection certificate", why="Would resolve the scrap-vs-cathodes description drift and actual cargo.", resolves_hypotheses=["H3", "H4"], priority=1).model_dump(),
                      EvidenceRequest(item="Beneficial-ownership disclosure for the broker and vessel owner", why="Confirms the shared-UBO network pattern.", resolves_hypotheses=["H1"], priority=2).model_dump()]})
    result = InvestigationResult(
        meta=RunMeta(run_id=run_id, case_id="case_suspicious_003", model="stub-replay"),
        record={"commodity": "Copper cathodes", "quantity": 2200, "unit": "t", "unit_price": 5500, "total_value": 12100000, "currency": "USD", "origin_port": "SGSIN", "destination_port": "INNSA", "vessel_name": "MV Ocean Star", "exporter_id": "E-STRAITS-COMM", "importer_id": "E-DECCAN-COPPER"},
        triage=Triage(trade_narrative="Copper cathodes 2,200 t, Singapore-Nhava Sheva.", initial_concerns=["price", "capacity", "transit", "insurance", "description"], unknowns=["network", "benign cause"], dimensions_to_probe=["economic", "physical", "temporal", "documentary", "behavioural", "network"]),
        hypotheses=[
            Hypothesis(hypothesis_id="H1", kind="suspicious", statement="Copper is under-invoiced to move value.", explains=["economic", "physical", "documentary"], prior=0.5, posterior=0.92, status="supported"),
            Hypothesis(hypothesis_id="H2", kind="benign", statement="Price reflects a genuine volume discount.", explains=["economic"], prior=0.2, posterior=0.05, status="refuted"),
            Hypothesis(hypothesis_id="H3", kind="benign", statement="Documents contain a clerical error.", explains=["documentary"], prior=0.15, posterior=0.08, status="weakened"),
            Hypothesis(hypothesis_id="H4", kind="benign", statement="Commodity is genuinely lower grade (scrap).", explains=["documentary"], prior=0.15, posterior=0.03, status="refuted"),
        ],
        plan_steps=[PlanStep(step=i, reasoning="(captured in the live trace)") for i in range(1, 7)], tool_calls=[],
        evidence_for=[EvidenceItem(evidence_id=e, dimension=d, stance="supports_suspicion", statement=s, weight=w, severity="high", hypotheses_affected=["H1"], observation_ids=[o])
                      for (e, d, s, w, o) in [("E1", "economic", "Price -38.2% vs benchmark.", 0.9, "O1"), ("E2", "physical", "Cargo over vessel capacity.", 0.85, "O2"), ("E3", "temporal", "Impossible transit implies ~87 kn.", 0.85, "O3"), ("E4", "documentary", "Scrap vs cathodes + late insurance.", 0.8, "O4a"), ("E6", "behavioural", "27-sigma below importer history.", 0.75, "O6"), ("E7", "network", "Recurring broker + shared UBO.", 0.7, "O7")]],
        evidence_against=[EvidenceItem(evidence_id="E5", dimension="economic", stance="refutes_suspicion", statement="No discount contract in file.", weight=0.6, severity="medium", hypotheses_affected=["H2"], observation_ids=["O5"])],
        evidence_neutral=[],
        budget=BudgetState(limit=6, spent=6, remaining=0, calls_made=6, exhaustive_cost=10, tools_skipped=[SkippedTool(tool="check_container_volume_consistency", reason="Budget exhausted.")]),
        graph=EvidenceGraph(nodes=[GraphNode(id="case_suspicious_003", kind="document", label="case_suspicious_003", dimension="economic"), GraphNode(id="E1", kind="finding", label="E1 price -38.2%", dimension="economic", stance="supports_suspicion", severity="high"), GraphNode(id="E2", kind="finding", label="E2 cargo > capacity", dimension="physical", stance="supports_suspicion", severity="high")], edges=[GraphEdge(source="case_suspicious_003", target="E1", relation="produced")]),
        decision=Decision(verdict="escalate", confidence=0.9, headline="Indicators consistent with potential under-invoicing / trade-value manipulation across four independent dimensions.", rationale="Four independent dimensions corroborate; benign hypotheses tested and not supported.", corroboration=Corroboration(corroborated_dimensions=["economic", "physical", "temporal", "documentary"], independent_signal_count=4, refuting_dimensions=[], strongest_benign_hypothesis="H2", strongest_benign_posterior=0.05, narrative="Four independent dimensions."), typology="Indicators consistent with potential under-invoicing / trade-value manipulation", caveats=VERDICT_CAVEATS, decisive_evidence_ids=["E1", "E2", "E3", "E4"]),
        evidence_requests=[EvidenceRequest(item="Current-year pricing addendum from the exporter", why="Confirm any genuine discount basis.", resolves_hypotheses=["H2"], priority=1), EvidenceRequest(item="Independent pre-shipment inspection certificate", why="Resolve scrap-vs-cathodes drift.", resolves_hypotheses=["H3", "H4"], priority=1)],
        report_markdown="# Investigation dossier - case_suspicious_003\n\n## Recommendation: ESCALATE\n\n**Typology:** Indicators consistent with potential under-invoicing / trade-value manipulation.\n\n## Corroborated dimensions (independent signals)\n- Economic: declared price -38.2% below the August 2026 benchmark.\n- Physical: declared cargo 122% of the MV Ocean Star deadweight.\n- Temporal: 1-day transit implies ~87 knots - impossible.\n- Documentary: packing list 'Copper Scrap' vs invoice 'Copper Cathodes'; insurance issued 8 days after shipment.\n- Behavioural / network reinforcement: 27-sigma below importer history; broker recurs in three escalated cases.\n\n## Benign hypotheses tested and not supported\n- H2 volume discount: no offtake contract in the file.\n- H4 genuine grade: documents describe scrap, not a graded discount.\n\n## Caveats\n- Reference data is synthetic and scoped to the prototype.\n- Investigative decision support, not a regulatory determination.\n- Anomalies may have legitimate explanations no available tool can observe.",
        events=[])
    emit("report_ready", "Dossier ready - verdict ESCALATE.",
         {"result": result.model_dump(mode="json"), "report_markdown": result.report_markdown})
    return lines, result.model_dump(mode="json")


def build_explainable():
    run_id = "run_stub_expl_002"
    lines = []
    seq = 0

    def emit(etype, narration, payload):
        nonlocal seq
        lines.append(ev(run_id, seq, etype, narration, payload))
        seq += 1

    emit("run_started", "Investigation started for case_explainable_002 (budget 6).",
         {"case_id": "case_explainable_002", "budget": 6, "model": "stub-replay", "flags": {"budget": True}, "contract_version": "1.0.0"})
    emit("case_loaded", "Loaded 7 documents; aluminium ingots, Jebel Ali to Nhava Sheva, declared USD 1,968/t.",
         {"record": {"commodity": "Aluminium ingots", "quantity": 1600, "unit": "t", "unit_price": 1968, "total_value": 3148800, "origin_port": "AEJEA", "destination_port": "INNSA", "vessel_name": "MV Gulf Trader", "exporter_id": "E-GULF-ALU", "importer_id": "E-BHARAT-METALS"},
          "document_ids": ["LC-2026-05129", "INV-2026-0822", "SC-2024-GA-BM", "BL-2026-441907", "PL-2026-0822", "COO-AE-20911", "INS-2026-6120"], "applicant_note": "Priced well below market; applicant states contract pricing applies."})
    emit("triage", "Triage: aluminium priced 18% below market; applicant claims contract pricing.",
         {"triage": Triage(trade_narrative="Aluminium ingots, 1,600 t, Jebel Ali to Nhava Sheva on MV Gulf Trader, declared USD 1,968/t against a market near USD 2,400/t; applicant says a long-term offtake contract governs the price.", initial_concerns=["Price ~18% below benchmark."], unknowns=["Whether a genuine offtake/volume-tier discount explains the gap.", "Whether the trade pattern is otherwise clean."], dimensions_to_probe=["economic", "documentary", "behavioural"]).model_dump()})
    emit("hypotheses_updated", "Formed hypotheses: benign offtake discount, benign grade difference, suspicious under-invoicing.",
         {"hypotheses": [
             Hypothesis(hypothesis_id="H1", kind="benign", statement="Price reflects a genuine volume-tier offtake discount.", explains=["economic"], prior=0.55, posterior=0.55, status="open").model_dump(),
             Hypothesis(hypothesis_id="H2", kind="benign", statement="Grade/quality difference explains the gap.", explains=["economic"], prior=0.15, posterior=0.15, status="open").model_dump(),
             Hypothesis(hypothesis_id="H3", kind="suspicious", statement="Aluminium is under-invoiced to move value.", explains=["economic"], prior=0.2, posterior=0.2, status="open", discriminating_evidence_needed=["contract in file", "importer's own history"]).model_dump(),
         ], "changed_ids": ["H1", "H2", "H3"]})
    emit("plan_step", "Plan: test the price benchmark (sizes the anomaly), then test the benign explanation.",
         {"plan_step": PlanStep(step=1, reasoning="Confirm the size of the gap, then spend the discriminating call on the contract that would explain it.", chosen_tool="check_price_benchmark", chosen_args={"commodity": "Aluminium ingots", "as_of_date": "2026-08", "declared_unit_price": 1968}, targets_hypotheses=["H1", "H3"], expected_information_gain=0.7, considered=[ConsideredOption(tool="check_contract_or_supporting_evidence", expected_information_gain=0.6, why_not="Price first to size the anomaly.")]).model_dump()})
    emit("tool_call_started", "Calling check_price_benchmark...",
         {"call_id": "c1", "tool": "check_price_benchmark", "args": {"commodity": "Aluminium ingots", "as_of_date": "2026-08", "declared_unit_price": 1968}, "targets_hypotheses": ["H1", "H3"]})
    emit("tool_call_completed", "Price is -18.0% vs benchmark.",
         {"tool_result": TR("c1", "check_price_benchmark", "Price 1,968 vs 2,400 benchmark (-18.0%)", [O("O1", "economic", "Declared 1,968 USD/t vs 2026-08 benchmark 2,400 (-18.0%).", "medium", {"declared": 1968.0, "benchmark": 2400.0, "deviation_pct": -18.0}, [{"kind": "reference_db", "ref": "benchmarks/aluminium ingots/2026-08", "value": "2400", "as_of": "2026-08"}])])})
    emit("evidence_added", "Evidence E1 (economic, supports suspicion): -18% price gap.",
         {"evidence": EvidenceItem(evidence_id="E1", dimension="economic", stance="supports_suspicion", statement="Declared unit price 1,968 USD/t is -18.0% below the August 2026 aluminium benchmark, outside the +/-8% band.", weight=0.65, severity="medium", hypotheses_affected=["H1", "H3"], observation_ids=["O1"], sources=[SourceRef(kind="reference_db", ref="benchmarks/aluminium ingots/2026-08", value="2400", as_of="2026-08")], interpretation="A real gap, but of a size that a documented discount could plausibly explain; needs the benign test before any verdict.").model_dump()})
    emit("budget_updated", "Budget: 1 of 6 spent.", {"budget": BudgetState(limit=6, spent=1, remaining=5, calls_made=1, exhaustive_cost=10).model_dump()})
    emit("plan_step", "Plan: test the benign offtake hypothesis directly - required and decisive.",
         {"plan_step": PlanStep(step=2, reasoning="The discriminating question is whether the file supports the claimed discount. Test it before anything else.", chosen_tool="check_contract_or_supporting_evidence", chosen_args={"claim": "long_term_offtake"}, targets_hypotheses=["H1", "H3"], expected_information_gain=0.8, considered=[ConsideredOption(tool="check_document_consistency", expected_information_gain=0.3, why_not="No documentary flag; the price explanation is the live question.")]).model_dump()})
    emit("tool_call_started", "Calling check_contract_or_supporting_evidence (long_term_offtake)...",
         {"call_id": "c2", "tool": "check_contract_or_supporting_evidence", "args": {"claim": "long_term_offtake"}, "targets_hypotheses": ["H1", "H3"]})
    emit("tool_call_completed", "Master offtake contract found, with a 16.5% volume-tier discount clause.",
         {"tool_result": TR("c2", "check_contract_or_supporting_evidence", "Supporting document found: SC-2024-GA-BM", [O("O2", "economic", "Document SC-2024-GA-BM supports 'long_term_offtake': a three-year offtake with a 16.5% volume-tier discount to shipment-month LME.", "none", {}, [{"kind": "document", "ref": "SC-2024-GA-BM.raw_text", "value": "long_term_offtake", "label": "sales_contract"}])])})
    emit("evidence_added", "Evidence E2 (economic, refutes suspicion): offtake contract supports the discount.",
         {"evidence": EvidenceItem(evidence_id="E2", dimension="economic", stance="refutes_suspicion", statement="A three-year offtake contract (SC-2024-GA-BM) grants a 16.5% volume-tier discount, which quantitatively matches the observed gap.", weight=0.8, severity="none", hypotheses_affected=["H1", "H3"], observation_ids=["O2"], sources=[SourceRef(kind="document", ref="SC-2024-GA-BM.raw_text", value="long_term_offtake", label="sales_contract")], interpretation="The benign explanation is documented and its magnitude matches the anomaly; this is the decisive benign evidence.").model_dump()})
    emit("plan_step", "Plan: confirm with the importer's own history - a second independent benign source.",
         {"plan_step": PlanStep(step=3, reasoning="A second, independent benign source (the customer's own prior trades) makes the explanation robust.", chosen_tool="check_historical_trade", chosen_args={"entity_id": "E-BHARAT-METALS", "commodity": "Aluminium ingots"}, targets_hypotheses=["H1", "H3"], expected_information_gain=0.5, considered=[ConsideredOption(tool="check_vessel_capacity", expected_information_gain=0.1, why_not="Load well within capacity; no physical question.")]).model_dump()})
    emit("tool_call_started", "Calling check_historical_trade...",
         {"call_id": "c3", "tool": "check_historical_trade", "args": {"entity_id": "E-BHARAT-METALS", "commodity": "Aluminium ingots"}, "targets_hypotheses": ["H1", "H3"]})
    emit("tool_call_completed", "Six prior trades priced 1,940-2,010/t - consistent with the invoice.",
         {"tool_result": TR("c3", "check_historical_trade", "History 1,940-2,010, z=+0.22", [O("O3", "behavioural", "This importer's 6 prior aluminium trades ranged 1,940-2,010 USD/t (median 1,975); current 1,968 is z=+0.22.", "low", {"median": 1975.0, "min": 1940.0, "max": 2010.0, "n": 6, "z_score": 0.22}, [{"kind": "reference_db", "ref": "history/E-BHARAT-METALS/aluminium ingots", "value": "1940-2010"}])], cost=2)})
    emit("evidence_added", "Evidence E3 (behavioural, refutes suspicion): invoice matches the customer's own history.",
         {"evidence": EvidenceItem(evidence_id="E3", dimension="behavioural", stance="refutes_suspicion", statement="The declared price sits inside the importer's own six prior trades (z=+0.22) - this is the price the customer genuinely pays.", weight=0.7, severity="low", hypotheses_affected=["H1", "H3"], observation_ids=["O3"], sources=[SourceRef(kind="reference_db", ref="history/E-BHARAT-METALS/aluminium ingots", value="1940-2010")], interpretation="An independent benign source confirms the price; the anomaly is explained, not merely present.").model_dump()})
    emit("plan_step", "Plan: confirm documents clean, then decide.",
         {"plan_step": PlanStep(step=4, reasoning="No other dimension is in question; confirm documents are consistent before deciding.", chosen_tool="check_document_consistency", chosen_args={}, targets_hypotheses=["H1"], expected_information_gain=0.3, considered=[ConsideredOption(tool="check_counterparty_network", expected_information_gain=0.2, why_not="Clean repeat customer; network adds nothing here.")]).model_dump()})
    emit("tool_call_started", "Calling check_document_consistency...",
         {"call_id": "c4", "tool": "check_document_consistency", "args": {}, "targets_hypotheses": ["H1"]})
    emit("tool_call_completed", "Documents consistent.",
         {"tool_result": TR("c4", "check_document_consistency", "All documents agree.", [O("O4", "documentary", "All documents agree on commodity, quantity, value and chronology; no internal inconsistency.", "none", {}, [])])})
    emit("evidence_added", "Evidence E4 (documentary, refutes suspicion): documents consistent.",
         {"evidence": EvidenceItem(evidence_id="E4", dimension="documentary", stance="refutes_suspicion", statement="LC, invoice, contract, B/L, packing list, certificate of origin and insurance all agree; no documentary signal.", weight=0.5, severity="none", hypotheses_affected=["H1"], observation_ids=["O4"], sources=[SourceRef(kind="document", ref="LC-2026-05129", label="letter_of_credit")], interpretation="No corroborating signal in any non-economic dimension.").model_dump()})
    emit("budget_updated", "Budget: 5 of 6 spent.", {"budget": BudgetState(limit=6, spent=5, remaining=1, calls_made=4, exhaustive_cost=10).model_dump()})
    emit("graph_updated", "Graph: single economic anomaly with two independent benign sources.",
         {"nodes_added": [
             node("case_explainable_002", "document", "case_explainable_002", dimension="economic"),
             node("E1", "finding", "E1 price -18%", dimension="economic", stance="supports_suspicion", severity="medium"),
             node("E2", "finding", "E2 offtake contract", dimension="economic", stance="refutes_suspicion", severity="none"),
             node("E3", "finding", "E3 matches history", dimension="behavioural", stance="refutes_suspicion", severity="low"),
             node("E4", "finding", "E4 docs consistent", dimension="documentary", stance="refutes_suspicion", severity="none"),
             node("H1", "hypothesis", "H1 offtake discount"), node("SC-2024-GA-BM", "document", "SC-2024-GA-BM", dimension="economic")],
          "edges_added": [edge("case_explainable_002", "E1", "produced"), edge("case_explainable_002", "E2", "produced"), edge("SC-2024-GA-BM", "E2", "states"), edge("case_explainable_002", "E3", "produced"), edge("case_explainable_002", "E4", "produced"), edge("E1", "H3", "supports"), edge("E2", "H1", "supports"), edge("E3", "H1", "supports"), edge("E4", "H1", "supports")]})
    emit("corroboration", "Corroboration: one medium economic signal, but two independent benign sources refute it.",
         {"corroboration": Corroboration(corroborated_dimensions=["economic"], independent_signal_count=1, refuting_dimensions=["economic", "documentary"], strongest_benign_hypothesis="H1", strongest_benign_posterior=0.85, narrative="There is exactly one suspicion-supporting dimension (economic). It is matched by two independent benign sources: a quoted offtake contract and the importer's own six prior trades. No other dimension shows a signal. Therefore the escalation bar - corroboration across two or more independent dimensions - is not met.").model_dump()})
    emit("plan_step", "Plan: sufficient evidence - the single-dimension rule caps the verdict at HOLD.",
         {"plan_step": PlanStep(step=5, reasoning="A single-dimension anomaly with a corroborated benign explanation does not meet the escalation bar, however large the gap.", chosen_tool=None, chosen_args={}, expected_information_gain=0.0, stop_reason="sufficient_evidence").model_dump()})
    emit("decision", "Decision: HOLD + request documentation. Single economic anomaly, benign explanation corroborated.",
         {"decision": Decision(verdict="hold", confidence=0.7, headline="Single-dimension economic anomaly with a corroborated benign explanation - recommend HOLD, not escalate.", rationale="The -18% price gap is real, but it is a single economic signal matched by two independent benign sources: a quoted 16.5% volume-tier offtake contract and the importer's own six prior trades at this price. No other dimension shows a signal. The deterministic escalation policy requires suspicion-supporting evidence in two or more independent dimensions; this case has one. Escalation is therefore capped at HOLD regardless of the gap size. Request current-year pricing and an inspection certificate to close the residual uncertainty.", corroboration=Corroboration(corroborated_dimensions=["economic"], independent_signal_count=1, refuting_dimensions=["economic", "documentary"], strongest_benign_hypothesis="H1", strongest_benign_posterior=0.85, narrative="One economic signal, two independent benign sources; escalation bar not met."), caveats=VERDICT_CAVEATS, decisive_evidence_ids=["E1", "E2", "E3"]).model_dump()})
    emit("evidence_requested", "Request two documents to close the residual uncertainty.",
         {"requests": [EvidenceRequest(item="Current-year pricing addendum from the exporter", why="Confirms the offtake tier still applies this year.", resolves_hypotheses=["H1"], priority=2).model_dump(), EvidenceRequest(item="Independent inspection certificate for grade", why="Confirms the grade, removing any residual grade-difference doubt.", resolves_hypotheses=["H2"], priority=2).model_dump()]})
    result = InvestigationResult(
        meta=RunMeta(run_id=run_id, case_id="case_explainable_002", model="stub-replay"),
        record={"commodity": "Aluminium ingots", "quantity": 1600, "unit": "t", "unit_price": 1968, "total_value": 3148800, "currency": "USD", "origin_port": "AEJEA", "destination_port": "INNSA", "vessel_name": "MV Gulf Trader", "exporter_id": "E-GULF-ALU", "importer_id": "E-BHARAT-METALS"},
        triage=Triage(trade_narrative="Aluminium 1,600 t, Jebel Ali-Nhava Sheva.", initial_concerns=["price -18%"], unknowns=["benign cause"], dimensions_to_probe=["economic", "documentary", "behavioural"]),
        hypotheses=[
            Hypothesis(hypothesis_id="H1", kind="benign", statement="Price reflects a genuine volume-tier offtake discount.", explains=["economic"], prior=0.55, posterior=0.85, status="supported"),
            Hypothesis(hypothesis_id="H2", kind="benign", statement="Grade/quality difference explains the gap.", explains=["economic"], prior=0.15, posterior=0.4, status="open"),
            Hypothesis(hypothesis_id="H3", kind="suspicious", statement="Aluminium is under-invoiced to move value.", explains=["economic"], prior=0.2, posterior=0.1, status="weakened"),
        ],
        plan_steps=[PlanStep(step=i, reasoning="(captured in the live trace)") for i in range(1, 6)], tool_calls=[],
        evidence_for=[EvidenceItem(evidence_id="E1", dimension="economic", stance="supports_suspicion", statement="Price -18% vs benchmark.", weight=0.65, severity="medium", hypotheses_affected=["H3"], observation_ids=["O1"])],
        evidence_against=[
            EvidenceItem(evidence_id="E2", dimension="economic", stance="refutes_suspicion", statement="Offtake contract supports the discount.", weight=0.8, severity="none", hypotheses_affected=["H1", "H3"], observation_ids=["O2"]),
            EvidenceItem(evidence_id="E3", dimension="behavioural", stance="refutes_suspicion", statement="Matches importer history.", weight=0.7, severity="low", hypotheses_affected=["H1", "H3"], observation_ids=["O3"]),
            EvidenceItem(evidence_id="E4", dimension="documentary", stance="refutes_suspicion", statement="Documents consistent.", weight=0.5, severity="none", hypotheses_affected=["H1"], observation_ids=["O4"]),
        ],
        evidence_neutral=[],
        budget=BudgetState(limit=6, spent=5, remaining=1, calls_made=4, exhaustive_cost=10),
        graph=EvidenceGraph(nodes=[GraphNode(id="case_explainable_002", kind="document", label="case_explainable_002", dimension="economic"), GraphNode(id="E1", kind="finding", label="E1 price -18%", dimension="economic", stance="supports_suspicion", severity="medium")], edges=[GraphEdge(source="case_explainable_002", target="E1", relation="produced")]),
        decision=Decision(verdict="hold", confidence=0.7, headline="Single-dimension economic anomaly with a corroborated benign explanation - recommend HOLD, not escalate.", rationale="One economic signal matched by two independent benign sources; escalation requires two+ dimensions.", corroboration=Corroboration(corroborated_dimensions=["economic"], independent_signal_count=1, refuting_dimensions=["economic", "documentary"], strongest_benign_hypothesis="H1", strongest_benign_posterior=0.85, narrative="One economic signal; escalation bar not met."), caveats=VERDICT_CAVEATS, decisive_evidence_ids=["E1", "E2", "E3"]),
        evidence_requests=[EvidenceRequest(item="Current-year pricing addendum from the exporter", why="Confirm offtake tier still applies.", resolves_hypotheses=["H1"], priority=2), EvidenceRequest(item="Independent inspection certificate for grade", why="Remove grade-difference doubt.", resolves_hypotheses=["H2"], priority=2)],
        report_markdown="# Investigation dossier - case_explainable_002\n\n## Recommendation: HOLD + request documentation\n\n## Why not escalate\nA single-dimension economic anomaly with a corroborated benign explanation does not meet the escalation bar - and that rule is deterministic code, not a model's opinion.\n\n## Evidence\n- E1 (economic, supports): price -18.0% below benchmark.\n- E2 (economic, refutes): three-year offtake contract grants a 16.5% volume-tier discount.\n- E3 (behavioural, refutes): invoice matches the importer's own six prior trades (z=+0.22).\n- E4 (documentary, refutes): documents consistent.\n\n## Documents to request\n1. Current-year pricing addendum.\n2. Independent inspection certificate for grade.\n\n## Caveats\n- Synthetic reference data; decision support, not a regulatory determination.",
        events=[])
    emit("report_ready", "Dossier ready - verdict HOLD.",
         {"result": result.model_dump(mode="json"), "report_markdown": result.report_markdown})
    return lines, result.model_dump(mode="json")


def main():
    builders = {"case_clean_001": build_clean, "case_suspicious_003": build_suspicious, "case_explainable_002": build_explainable}
    for case_id, fn in builders.items():
        lines, result = fn()
        (OUT / f"{case_id}.events.jsonl").write_text("\n".join(lines) + "\n")
        (OUT / f"{case_id}.result.json").write_text(json.dumps(result, indent=2))
        print(f"wrote {case_id}: {len(lines)} events")


if __name__ == "__main__":
    main()
