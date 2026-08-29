"""check_historical_trade — how does this trade compare to the entity's own past?"""

from __future__ import annotations

from interpretex_contracts import Dimension, Observation, Severity, ToolSpec

from .base import (
    ToolOutcome, clip, derived_source, ref_source, zscore_severity,
)
from ..reference import prices_summary

SPEC = ToolSpec(
    name="check_historical_trade",
    description=(
        "Retrieves the entity's prior trades in this commodity from the reference "
        "history: price range and median, quantity range, distinct counterparties "
        "and vessels, and the z-score of the declared price against that history. "
        "This is how 'unusual for the market' becomes 'unusual for this customer' "
        "— or, when the declared price sits inside the customer's own history, "
        "evidence FOR a consistent long-standing pricing arrangement. Zero history "
        "is reported too: a first transaction is a finding."
    ),
    dimensions=[Dimension.behavioural],
    args_schema={
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
            "commodity": {"type": "string"},
            "lookback_months": {"type": "integer"},
        },
        "additionalProperties": True,
    },
    cost_units=2,
    discriminates=["consistent long-standing pricing arrangement",
                   "anomaly specific to this transaction",
                   "new or unusual trading behaviour"],
)


def run(reg, args: dict) -> ToolOutcome:
    world = reg.world
    record = reg.record
    entity_id = str(args.get("entity_id") or record.importer_id or "")
    entity = world.entity(entity_id)
    if entity is None:
        return ToolOutcome(ok=False, error=f"entity {entity_id!r} not in the reference world")

    commodity_name = str(args.get("commodity") or record.commodity)
    commodity = world.find_commodity(commodity_name)
    commodity_key = commodity.key if commodity else commodity_name
    lookback = args.get("lookback_months")
    before = reg.case.record.ship_date or None

    trades = world.trades_for_entity(entity_id, commodity_key,
                                     before_or_on=before,
                                     lookback_months=int(lookback) if lookback else None)
    sources = [ref_source("entities", entity_id, value=entity["name"],
                          label=entity["name"]),
               derived_source("check_historical_trade", "prior_trade_count",
                              float(len(trades)))]
    raw: dict = {
        "entity_id": entity_id,
        "entity_name": entity["name"],
        "commodity": commodity_key,
        "prior_trade_count": len(trades),
        "prior_trades": [t.trade_id for t in trades],
    }
    observations: list[Observation] = []

    if not trades:
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.behavioural,
            statement=(f"No prior trades in {commodity_key} are recorded for "
                       f"{entity['name']} ({entity_id}) in the reference history; "
                       "this would be the entity's first such transaction."),
            severity=Severity.low,
            metrics={"prior_trade_count": 0.0},
            sources=sources,
        ))
        return ToolOutcome(ok=True,
                           summary=clip(f"No prior {commodity_key} history for "
                                        f"{entity['name']} ({entity_id})."),
                           observations=observations, raw=raw, sources=sources)

    prices = [t.unit_price for t in trades]
    qty = [t.quantity for t in trades]
    stats = prices_summary(prices)
    counterparties = sorted({t.exporter_id if t.importer_id == entity_id else t.importer_id
                             for t in trades})
    vessels = sorted({t.vessel_name for t in trades})
    declared = float(record.unit_price)
    z_score = 0.0
    if stats["std"] > 0.01 * max(stats["median"], 1.0):
        z_score = (declared - stats["mean"]) / stats["std"]
    raw.update({
        "price_min": stats["min"], "price_median": stats["median"],
        "price_max": stats["max"], "price_std": stats["std"],
        "quantity_min": min(qty), "quantity_max": max(qty),
        "distinct_counterparties": counterparties,
        "distinct_vessels": vessels,
        "declared_unit_price": declared,
        "z_score": round(z_score, 2),
    })

    # 1) deviation of the declared price from the entity's own history
    severity = zscore_severity(abs(z_score))
    if severity is not Severity.none:
        direction = "below" if z_score < 0 else "above"
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.behavioural,
            statement=(f"Declared unit price {declared:,.2f} is {abs(z_score):.2f} standard "
                       f"deviations {direction} {entity['name']}'s {len(trades)}-trade history "
                       f"in {commodity_key} (median {stats['median']:,.2f}, range "
                       f"{stats['min']:,.2f}-{stats['max']:,.2f})."),
            severity=severity,
            metrics={"z_score": round(z_score, 2), "prior_trade_count": float(len(trades)),
                     "price_median": stats["median"], "price_min": stats["min"],
                     "price_max": stats["max"], "price_std": round(stats["std"], 2)},
            sources=sources + [ref_source("historical_trades", trades[0].trade_id,
                                          value=trades[0].unit_price)],
        ))

    # 2) consistency with the entity's own history (evidence for a pricing arrangement)
    if len(trades) >= 3 and stats["min"] <= declared <= stats["max"]:
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.behavioural,
            statement=(f"Declared unit price {declared:,.2f} falls within {entity['name']}'s "
                       f"own {len(trades)}-trade history in {commodity_key} "
                       f"({stats['min']:,.2f}-{stats['max']:,.2f}, median "
                       f"{stats['median']:,.2f}); z-score {z_score:+.2f}."),
            severity=Severity.none,
            metrics={"z_score": round(z_score, 2), "prior_trade_count": float(len(trades)),
                     "price_median": stats["median"], "price_min": stats["min"],
                     "price_max": stats["max"]},
            sources=sources + [ref_source("historical_trades", trades[-1].trade_id,
                                          value=trades[-1].unit_price)],
        ))

    # 3) quantity far outside the entity's prior range
    if declared_qty := float(record.quantity):
        if len(trades) >= 2 and declared_qty > 2.0 * max(qty):
            observations.append(Observation(
                observation_id="",
                dimension=Dimension.behavioural,
                statement=(f"Declared quantity {declared_qty:,.1f} {record.unit} exceeds "
                           f"{entity['name']}'s prior maximum of {max(qty):,.1f} in this "
                           f"commodity across {len(trades)} prior trades."),
                severity=Severity.medium,
                metrics={"declared_quantity": declared_qty, "prior_max_quantity": max(qty),
                         "prior_trade_count": float(len(trades))},
                sources=sources,
            ))
            raw["quantity_outlier"] = True

    if observations:
        worst = max(o.severity for o in observations)
        summary = clip(f"{len(trades)} prior {commodity_key} trades for {entity['name']} "
                       f"({stats['min']:,.0f}-{stats['max']:,.0f}); declared {declared:,.0f} "
                       f"(z {z_score:+.2f}); salience {worst.value}.")
    else:
        summary = clip(f"{len(trades)} prior {commodity_key} trades for {entity['name']}; "
                       f"declared price {declared:,.0f} is consistent with that history.")
    return ToolOutcome(ok=True, summary=summary, observations=observations,
                       raw=raw, sources=sources)
