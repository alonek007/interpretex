"""check_counterparty_network — walk the entity graph for structural patterns."""

from __future__ import annotations

from interpretex_contracts import Dimension, Observation, Severity, ToolSpec

from .base import ToolOutcome, clip, derived_source, ref_source

SPEC = ToolSpec(
    name="check_counterparty_network",
    description=(
        "Walks the entity graph around the named entity to a given depth and "
        "reports structural patterns: shared intermediaries, shared beneficial "
        "owners, repeated vessels and co-occurring counterparties, plus how many "
        "prior trades in the cluster were recorded as escalated. Separates an "
        "isolated transaction from a structured network from an ordinary "
        "commercial group structure. Nothing found is reported as a result."
    ),
    dimensions=[Dimension.network],
    args_schema={
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
            "depth": {"type": "integer", "minimum": 1, "maximum": 3},
        },
        "additionalProperties": True,
    },
    cost_units=2,
    discriminates=["isolated transaction", "structured network activity",
                   "ordinary commercial group structure"],
)


def _network_obs(obs_id, pattern, statement, severity, metrics, sources,
                 entity_ids, case_ids):
    return Observation(
        observation_id=obs_id,
        dimension=Dimension.network,
        statement=statement,
        severity=severity,
        metrics=metrics,
        sources=sources,
    )


def run(reg, args: dict) -> ToolOutcome:
    world = reg.world
    record = reg.record
    entity_id = str(args.get("entity_id") or record.importer_id or "")
    depth = min(max(int(args.get("depth") or 2), 1), 3)
    entity = world.entity(entity_id)
    if entity is None:
        return ToolOutcome(ok=False, error=f"entity {entity_id!r} not in the reference world")

    sources = [ref_source("entities", entity_id, value=entity["name"],
                          label=entity["name"]),
               derived_source("check_counterparty_network", "depth", float(depth))]

    # counterparties: from case record + reference history
    counterparties: set[str] = set()
    for eid in (record.exporter_id, record.broker_id, record.importer_id):
        if eid and eid != entity_id:
            counterparties.add(eid)
    for t in world.trades_for_entity(entity_id):
        cid = t.exporter_id if t.importer_id == entity_id else t.importer_id
        if cid and cid != entity_id:
            counterparties.add(cid)

    observations: list[Observation] = []
    raw: dict = {"focal_entity_id": entity_id, "depth": depth,
                 "counterparties": sorted(counterparties)}

    ubo_members: dict[str, set[str]] = {}

    def _find_shared_ubo(focal_id, other_id, scope_label) -> bool:
        f_ubos = set(world.entity(focal_id)["ultimate_beneficial_owners"])
        o_ubos = set(world.entity(other_id)["ultimate_beneficial_owners"]) if world.entity(other_id) else set()
        overlap = f_ubos & o_ubos
        if overlap:
            others = sorted(o_ubos and {other_id} | ubo_members.get(next(iter(overlap)), set()) or {other_id})
            # collect all entities sharing each overlapping ubo
            shared: list[str] = []
            for ubo in overlap:
                shared = world.entities_with_ubo(ubo)
            shared_here = sorted(s for s in set(shared) if s != focal_id)
            ubo_members.update(overlap and {next(iter(overlap)): set(shared_here)} or {})
            if shared_here:
                observations.append(Observation(
                    observation_id="",
                    dimension=Dimension.network,
                    statement=(f"Beneficial owner(s) {sorted(overlap)} of {world.entity(focal_id)['name']} "
                               f"also appear on {', '.join(world.entity(s)['name'] for s in shared_here)} "
                               f"({', '.join(shared_here)}) in the reference world ({scope_label})."),
                    severity=Severity.medium,
                    metrics={"shared_ubos": float(len(overlap)), "shared_entity_count": float(len(shared_here))},
                    sources=sources + [ref_source("entities", s, label=world.entity(s)["name"]) for s in shared_here],
                ))
                return True
        return False

    # (a) focal's own shared UBOs
    for ubo in entity["ultimate_beneficial_owners"]:
        members = world.entities_with_ubo(ubo)
        members_here = sorted(m for m in members if m != entity_id)
        if members_here:
            observations.append(Observation(
                observation_id="",
                dimension=Dimension.network,
                statement=(f"Beneficial owner '{ubo}' of {entity['name']} also appears on "
                           f"{', '.join(world.entity(m)['name'] for m in members_here)} "
                           f"({', '.join(members_here)}) in the reference world."),
                severity=Severity.medium,
                metrics={"shared_ubos": 1.0, "shared_entity_count": float(len(members_here))},
                sources=sources + [ref_source("entities", m, label=world.entity(m)["name"]) for m in members_here],
            ))

    # (b) depth-2: counterparties' shared UBOs
    for cid in sorted(counterparties):
        c_other = cid
        f_ubos = set(entity["ultimate_beneficial_owners"])
        c = world.entity(cid)
        if not c:
            continue
        overlap = f_ubos & set(c["ultimate_beneficial_owners"])
        if overlap:
            # find all entities (beyond cid) sharing this ubo
            shared = sorted(m for m in world.entities_with_ubo(next(iter(overlap))) if m != entity_id and m != cid)
            if shared:
                observations.append(Observation(
                    observation_id="",
                    dimension=Dimension.network,
                    statement=(f"Counterparty {c['name']} ({cid}) shares beneficial owner "
                               f"'{sorted(overlap)[0]}' with {', '.join(world.entity(s)['name'] for s in shared)} "
                               f"({', '.join(shared)}) in the reference world."),
                    severity=Severity.medium,
                    metrics={"shared_ubos": float(len(overlap)), "shared_entity_count": float(len(shared))},
                    sources=sources + [ref_source("entities", s, label=world.entity(s)["name"]) for s in shared],
                ))

    # (c) broker reuse / escalation
    broker_ids = {b for b in {record.broker_id} if b}
    for t in world.trades_for_entity(entity_id):
        if t.broker_id:
            broker_ids.add(t.broker_id)
    for bid in sorted(broker_ids):
        b = world.entity(bid)
        bname = b["name"] if b else bid
        brokered = world.trades_for_broker(bid)
        esc = world.escalated_trades_for_broker(bid)
        if not brokered:
            continue
        severity = Severity.high if len(esc) >= 2 else (Severity.medium if len(esc) == 1 else Severity.low)
        case_ids = [t.prior_case_ref for t in esc if t.prior_case_ref]
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.network,
            statement=(f"Broker {bname} ({bid}) appears on {len(brokered)} prior trade(s) in the "
                       f"reference history, of which {len(esc)} were recorded as escalated"
                       + (f" ({', '.join(case_ids)})." if case_ids else ".")),
            severity=severity,
            metrics={"brokered_trades": float(len(brokered)), "escalated_trades": float(len(esc))},
            sources=sources + [ref_source("historical_trades", t.trade_id, t.outcome, label=t.outcome)
                               for t in esc[:3]],
        ))
        raw.setdefault("brokers", {})[bid] = {"brokered": len(brokered), "escalated": len(esc)}

    # (d) repeated vessel across >=2 counterparty pairs
    vessel_pairs: dict[str, set[str]] = {}
    for t in world.trades:
        pair = tuple(sorted((t.exporter_id, t.importer_id)))
        vessel_pairs.setdefault(t.vessel_name, set()).add(pair)
    for vname, pairs in vessel_pairs.items():
        if len(pairs) >= 2:
            cnt = sum(1 for t in world.trades if t.vessel_name == vname)
            observations.append(Observation(
                observation_id="",
                dimension=Dimension.network,
                statement=(f"Vessel {vname} appears on {cnt} historical trade(s) spanning "
                           f"{len(pairs)} distinct counterparty pairs in the reference world "
                           f"(pattern: repeated vessel)."),
                severity=Severity.low,
                metrics={"vessel_trades": float(cnt), "counterparty_pairs": float(len(pairs))},
                sources=sources + [ref_source("vessels", vname)],
            ))
    raw["repeated_vessels"] = {v: len(p) for v, p in vessel_pairs.items() if len(p) >= 2}

    if not observations:
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.network,
            statement=(f"No shared intermediaries, shared beneficial owners or repeated vessels "
                       f"were found for {entity['name']} within depth {depth} of the reference "
                       f"world."),
            severity=Severity.none,
            metrics={"prior_trade_count": 0.0},
            sources=sources,
        ))
        summary = clip(f"No network patterns found for {entity['name']} within depth {depth}.")
    else:
        worst = max(o.severity for o in observations)
        summary = clip(f"{len(observations)} network pattern(s) for {entity['name']} "
                       f"within depth {depth}; highest salience {worst.value}.")
    return ToolOutcome(ok=True, summary=summary, observations=observations,
                       raw=raw, sources=sources)
