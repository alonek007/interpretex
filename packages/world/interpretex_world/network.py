"""network_view — the Part 1 counterparty-network surface.

Builds a :class:`NetworkView` (GraphNode / GraphEdge / NetworkFinding) from a
case record plus the reference world. This is the shared graph Parts 2 and 3
render; Part 1 produces it deterministically so the demo and fixtures are
stable. Never uses verdict language in findings.
"""

from __future__ import annotations

from typing import Optional

from interpretex_contracts import (
    Dimension, GraphEdge, GraphNode, NetworkFinding, NetworkPattern, NetworkView,
    Severity, TradeCase,
)
from interpretex_contracts.helpers import IdCounter

from .reference import ReferenceWorld

_FINDING_ID = IdCounter("NF")


def _entity_node(world: ReferenceWorld, eid: str, role: Optional[str]) -> GraphNode:
    e = world.entity(eid)
    meta: dict = {"role": role}
    if e is None:
        return GraphNode(id=eid, kind="entity", label=eid, meta=meta)
    meta["jurisdiction"] = e["country"]
    meta["ultimate_beneficial_owners"] = e["ultimate_beneficial_owners"]
    meta["sanctions_listed"] = e["sanctions_status"] != "not_listed"
    risk: list[str] = []
    if meta["sanctions_listed"]:
        risk.append("sanctions_listed")
    esc = world.escalated_trades_for_broker(eid)
    if esc:
        risk.append(f"{len(esc)} prior escalated trades")
    if risk:
        meta["risk_flags"] = risk
    return GraphNode(id=eid, kind="entity", label=e["name"], meta=meta)


def network_view(case: TradeCase,
                 world: Optional[ReferenceWorld] = None,
                 focus_entity_id: Optional[str] = None,
                 depth: int = 2) -> NetworkView:
    world = world or ReferenceWorld.default()
    rec = case.record
    focus = focus_entity_id or rec.importer_id

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    findings: list[NetworkFinding] = []

    def node(eid: str, role: Optional[str] = None) -> None:
        if eid and eid not in nodes:
            nodes[eid] = _entity_node(world, eid, role)

    node(focus, "focal")
    for eid in (rec.exporter_id, rec.importer_id, rec.broker_id):
        node(eid)

    for eid in (rec.exporter_id, rec.importer_id):
        if eid:
            edges.append(GraphEdge(source=focus, target=eid,
                                   relation="linked_to", label="trades_with"))
    if rec.broker_id:
        edges.append(GraphEdge(source=focus, target=rec.broker_id,
                               relation="linked_to", label="brokered_by"))

    # shared beneficial ownership, scoped to the case's own parties (so an
    # unrelated reference-world UBO cluster never paints a clean case).
    focal = world.entity(focus)
    focal_ubos = set(focal["ultimate_beneficial_owners"]) if focal else set()
    parties = {focus, rec.exporter_id, rec.importer_id, rec.broker_id} - {None}
    party_ids = sorted(p for p in parties if p)
    for i, a in enumerate(party_ids):
        for b in party_ids[i + 1:]:
            ea, eb = world.entity(a), world.entity(b)
            if ea is None or eb is None:
                continue
            overlap = set(ea["ultimate_beneficial_owners"]) & set(eb["ultimate_beneficial_owners"])
            if overlap:
                edges.append(GraphEdge(source=a, target=b,
                                        relation="linked_to", label="shares_ubo"))
                findings.append(NetworkFinding(
                    finding_id=_FINDING_ID(),
                    pattern="shared_ownership",
                    statement=(f"{ea['name']} shares beneficial owner "
                               f"'{sorted(overlap)[0]}' with {eb['name']} within the case parties "
                               f"in the reference world."),
                    entity_ids=[a, b],
                    case_ids=[],
                    severity=Severity.medium,
                    metrics={"shared_ubos": float(len(overlap))},
                ))

    # depth-2: broker escalation (kept broad — a broker's prior escalations are
    # directly case-relevant regardless of which counterparty surfaced them)
    broker_ids = {rec.broker_id, *(t.broker_id for t in world.trades_for_entity(focus))}
    broker_ids.discard(None)
    for bid in sorted(broker_ids):
        if not bid:
            continue
        b = world.entity(bid)
        brokered = world.trades_for_broker(bid)
        esc = world.escalated_trades_for_broker(bid)
        if not brokered:
            continue
        node(bid)
        case_ids = sorted({t.prior_case_ref for t in esc if t.prior_case_ref})
        findings.append(NetworkFinding(
            finding_id=_FINDING_ID(),
            pattern="intermediary_reuse",
            statement=(f"Broker {b['name'] if b else bid} appears on {len(brokered)} prior "
                       f"trade(s) in the reference world, of which {len(esc)} were recorded as "
                       f"escalated" + (f" ({', '.join(case_ids)})." if case_ids else ".")),
            entity_ids=[bid],
            case_ids=case_ids,
            severity=Severity.high if len(esc) >= 2 else (Severity.medium if esc else Severity.low),
            metrics={"brokered_trades": float(len(brokered)), "escalated_trades": float(len(esc))},
        ))

    # repeated vessels across counterparty pairs
    vessel_pairs: dict[str, set] = {}
    for t in world.trades:
        vessel_pairs.setdefault(t.vessel_name, set()).add(
            tuple(sorted((t.exporter_id, t.importer_id))))
    for vname, pairs in vessel_pairs.items():
        if len(pairs) >= 2:
            cnt = sum(1 for t in world.trades if t.vessel_name == vname)
            findings.append(NetworkFinding(
                finding_id=_FINDING_ID(),
                pattern="vessel_reuse",
                statement=(f"Vessel {vname} appears on {cnt} historical trades spanning "
                           f"{len(pairs)} distinct counterparty pairs (pattern: repeated vessel)."),
                entity_ids=[],
                case_ids=[],
                severity=Severity.low,
                metrics={"vessel_trades": float(cnt), "counterparty_pairs": float(len(pairs))},
            ))

    return NetworkView(
        focus_entity_id=focus,
        nodes=list(nodes.values()),
        edges=edges,
        findings=findings,
    )
