"""Synthetic counterparty network view (Part 3 stub for Part 1 network intel)."""
from __future__ import annotations

from typing import Any

from interpretex_contracts import NetworkEdge, NetworkFinding, NetworkNode, NetworkView


def _entities() -> list[NetworkNode]:
    return [
        NetworkNode(id="E-STRAITS-COMM", label="Straits Commodities Pte Ltd", kind="entity", country="SG",
                    role="seller", sanctions_status="not_listed"),
        NetworkNode(id="E-DECCAN-COPPER", label="Deccan Copper Traders Pvt Ltd", kind="entity", country="IN",
                    role="buyer", sanctions_status="not_listed"),
        NetworkNode(id="E-MERIDIAN-TP", label="Meridian Trade Partners", kind="entity", country="AE",
                    role="broker", sanctions_status="near_match"),
        NetworkNode(id="E-OCEAN-HOLD", label="Ocean Star Holdings Ltd", kind="entity", country="MH",
                    role="vessel_owner", sanctions_status="not_listed"),
        NetworkNode(id="E-AEGEAN-ASSURANCE", label="Aegean Marine Assurance", kind="entity", country="MT",
                    role="insurer", sanctions_status="not_listed"),
        NetworkNode(id="MV-OCEAN-STAR", label="MV Ocean Star (IMO 9277410)", kind="vessel", country="LR",
                    role="vessel"),
    ]


def _edges() -> list[NetworkEdge]:
    return [
        NetworkEdge(source="E-STRAITS-COMM", target="E-MERIDIAN-TP", relation="intermediary_of", label="broker of record"),
        NetworkEdge(source="E-DECCAN-COPPER", target="E-MERIDIAN-TP", relation="intermediary_of", label="broker of record"),
        NetworkEdge(source="E-OCEAN-HOLD", target="MV-OCEAN-STAR", relation="owns", label="registered owner"),
        NetworkEdge(source="E-STRAITS-COMM", target="MV-OCEAN-STAR", relation="shipped_on", label="voyage"),
        NetworkEdge(source="E-MERIDIAN-TP", target="E-OCEAN-HOLD", relation="shared_ubo", label="UBO overlap (Bluewater Ventures)"),
        NetworkEdge(source="E-STRAITS-COMM", target="case_adv_2025_014", relation="co_occurs", label="prior flagged case"),
        NetworkEdge(source="E-STRAITS-COMM", target="case_adv_2026_003", relation="co_occurs", label="prior flagged case"),
    ]


def _findings(entity_id: str | None) -> list[NetworkFinding]:
    findings = [
        NetworkFinding(
            finding_id="NF-1", pattern="intermediary_reuse",
            statement="Broker Meridian Trade Partners is the broker of record on three previously escalated trade-finance cases.",
            entity_ids=["E-MERIDIAN-TP", "E-STRAITS-COMM"],
            case_ids=["case_adv_2025_014", "case_adv_2025_027", "case_adv_2026_003"],
            severity="high", metrics={"prior_escalations": 3},
        ),
        NetworkFinding(
            finding_id="NF-2", pattern="vessel_reuse",
            statement="Vessel MV Ocean Star appears on two prior flagged shipments carrying copper under different exporter names.",
            entity_ids=["E-STRAITS-COMM", "E-OCEAN-HOLD"],
            case_ids=["case_adv_2025_014", "case_adv_2026_003"],
            severity="medium", metrics={"prior_flagged_voyages": 2},
        ),
        NetworkFinding(
            finding_id="NF-3", pattern="shared_ownership",
            statement="Meridian Trade Partners and Ocean Star Holdings share an ultimate beneficial owner (Bluewater Ventures Trust).",
            entity_ids=["E-MERIDIAN-TP", "E-OCEAN-HOLD"],
            case_ids=[],
            severity="medium", metrics={"shared_ubos": 1},
        ),
    ]
    if entity_id:
        findings = [f for f in findings if entity_id in f.entity_ids]
    return findings


def network_view(entity_id: str | None = None, depth: int = 2) -> NetworkView:
    nodes = _entities()
    if entity_id:
        keep = {entity_id}
        for e in _edges():
            if e.source == entity_id:
                keep.add(e.target)
            if e.target == entity_id:
                keep.add(e.source)
        nodes = [n for n in nodes if n.id in keep]
    return NetworkView(
        focus_entity_id=entity_id,
        nodes=nodes,
        edges=_edges(),
        findings=_findings(entity_id),
    )
