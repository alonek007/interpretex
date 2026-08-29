"""check_price_benchmark — declared unit price against the monthly reference."""

from __future__ import annotations

from interpretex_contracts import Dimension, Observation, Severity, ToolSpec

from .base import (
    ToolOutcome, clip, derived_source, doc_source, price_deviation_severity,
    ref_source,
)

SPEC = ToolSpec(
    name="check_price_benchmark",
    description=(
        "Compares the declared unit price against the monthly reference benchmark "
        "for the commodity (and grade multiplier when supplied), returning the "
        "benchmark, the plausible band, the deviation percentage and the volume "
        "tier that applies to this quantity. Separates under-invoicing from "
        "over-invoicing from a legitimate bulk discount or grade difference: the "
        "volume tier shows how much of a discount the quantity alone explains."
    ),
    dimensions=[Dimension.economic],
    args_schema={
        "type": "object",
        "properties": {
            "commodity": {"type": "string"},
            "grade": {"type": "string"},
            "quantity": {"type": "number"},
            "as_of_date": {"type": "string",
                           "description": "ISO date; the benchmark month is derived from it"},
            "declared_unit_price": {"type": "number"},
        },
        "additionalProperties": True,
    },
    cost_units=1,
    discriminates=["under-invoicing", "over-invoicing", "legitimate bulk discount",
                   "grade difference", "stale or erroneous price"],
)


def run(reg, args: dict) -> ToolOutcome:
    world = reg.world
    record = reg.record

    commodity_name = str(args.get("commodity") or record.commodity)
    commodity = world.find_commodity(commodity_name)
    if commodity is None:
        return ToolOutcome(ok=False,
                           error=f"commodity {commodity_name!r} is not in the reference world")

    as_of = str(args.get("as_of_date") or record.ship_date or "2026-08-01")
    month = as_of[:7]
    benchmark = commodity.benchmark(month)
    if benchmark is None:
        return ToolOutcome(ok=False,
                           error=f"no reference benchmark for {commodity.key} in {month}")

    declared = float(args.get("declared_unit_price") if args.get("declared_unit_price") is not None
                     else record.unit_price)
    quantity = float(args.get("quantity") if args.get("quantity") is not None
                     else record.quantity)
    grade = args.get("grade") or record.commodity_grade
    multiplier = commodity.grade_multiplier(grade) if grade else None

    effective_benchmark = round(benchmark * (multiplier or 1.0), 2)
    deviation_pct = round((declared - effective_benchmark) / effective_benchmark * 100.0, 1)
    band_pct = commodity.plausible_band_pct * 100.0
    outside = round(abs(deviation_pct) - band_pct, 1)

    tier = commodity.tier_for(quantity)
    tier_discount = float(tier["discount_pct"]) * 100.0 if tier else 0.0

    raw = {
        "commodity": commodity.key,
        "grade": grade,
        "grade_multiplier": multiplier,
        "benchmark_month": month,
        "benchmark_unit_price": benchmark,
        "effective_benchmark_unit_price": effective_benchmark,
        "plausible_band_pct": commodity.plausible_band_pct,
        "deviation_pct": deviation_pct,
        "outside_band_pct": outside,
        "declared_unit_price": declared,
        "quantity": quantity,
        "applicable_volume_tier": tier,
        "tier_discount_pct": tier_discount,
    }
    sources = [
        doc_source(reg.doc_ref_for("unit_price"), "unit_price", declared),
        ref_source("benchmarks", commodity.key, benchmark, as_of=month,
                   label=f"{commodity.display_name} reference, {month}"),
        derived_source("check_price_benchmark", "deviation_pct", deviation_pct),
    ]
    if tier:
        sources.append(ref_source("volume_tiers", commodity.key, tier))

    observations: list[Observation] = []
    severity = price_deviation_severity(outside)
    if severity is not Severity.none:
        direction = "below" if deviation_pct < 0 else "above"
        statement = (
            f"Declared unit price {declared:,.2f} {commodity.currency}/{commodity.unit} is "
            f"{abs(deviation_pct):.1f}% {direction} the {month} reference benchmark of "
            f"{effective_benchmark:,.2f} {commodity.currency} (plausible band ±{band_pct:.1f}%)."
        )
        if tier and tier_discount > 0 and deviation_pct < 0:
            statement += (f" The quantity qualifies for a {tier_discount:.1f}% volume-tier "
                          f"discount (from {tier['min_qty']:,.0f} {commodity.unit}), which "
                          f"explains part of the gap.")
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.economic,
            statement=statement,
            severity=severity,
            metrics={
                "deviation_pct": deviation_pct,
                "benchmark_unit_price": effective_benchmark,
                "plausible_band_pct": band_pct,
                "outside_band_pct": outside,
                "tier_discount_pct": tier_discount,
                "quantity": quantity,
            },
            sources=sources,
            expected_range=[round(effective_benchmark * (1 - commodity.plausible_band_pct), 2),
                            round(effective_benchmark * (1 + commodity.plausible_band_pct), 2)],
        ))
        summary = clip(
            f"Declared {commodity.currency} {declared:,.2f}/{commodity.unit} vs "
            f"{effective_benchmark:,.2f} benchmark ({month}): {deviation_pct:+.1f}%, "
            f"{outside:.1f} points outside the ±{band_pct:.1f}% band"
            + (f"; volume tier {tier_discount:.1f}%" if tier else "") + ".")
    else:
        summary = clip(
            f"Declared {commodity.currency} {declared:,.2f}/{commodity.unit} vs "
            f"{effective_benchmark:,.2f} benchmark ({month}): {deviation_pct:+.1f}%, "
            f"inside the ±{band_pct:.1f}% plausible band.")

    return ToolOutcome(ok=True, summary=summary, observations=observations,
                       raw=raw, sources=sources)
