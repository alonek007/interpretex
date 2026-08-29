"""check_vessel_capacity — claimed cargo weight against the vessel's maximum."""

from __future__ import annotations

from interpretex_contracts import Dimension, Observation, Severity, ToolSpec

from .base import ToolOutcome, capacity_severity, clip, derived_source, ref_source

SPEC = ToolSpec(
    name="check_vessel_capacity",
    description=(
        "Compares the claimed cargo weight against the named vessel's deadweight "
        "capacity, returning capacity, claimed load, utilisation percentage and "
        "excess tonnage. Separates a phantom or inflated shipment from a wrong "
        "vessel being recorded from a misstated quantity. An unlisted vessel is a "
        "finding in itself: 'cannot verify' is reported, not an error."
    ),
    dimensions=[Dimension.physical],
    args_schema={
        "type": "object",
        "properties": {
            "vessel_name": {"type": "string"},
            "claimed_weight_tons": {"type": "number"},
        },
        "additionalProperties": True,
    },
    cost_units=1,
    discriminates=["phantom or inflated shipment", "wrong vessel recorded",
                   "quantity misstated"],
)


def run(reg, args: dict) -> ToolOutcome:
    world = reg.world
    record = reg.record
    vessel_name = str(args.get("vessel_name") or record.vessel_name or "")
    claimed = float(args.get("claimed_weight_tons")
                    if args.get("claimed_weight_tons") is not None
                    else (record.gross_weight_tons or record.quantity))

    vessel = world.vessel(vessel_name) if vessel_name else None
    sources = [derived_source("check_vessel_capacity", "utilisation_pct", None)]
    if vessel:
        sources.append(ref_source("vessels", vessel["vessel_name"],
                                  value=vessel["dwt_tons"],
                                  label=f"{vessel['vessel_name']} capacity"))

    raw: dict = {"vessel_name": vessel_name, "claimed_weight_tons": claimed}
    observations: list[Observation] = []

    if not vessel:
        raw["vessel_in_registry"] = False
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.physical,
            statement=(f"Vessel '{vessel_name}' is not present in the reference vessel "
                       f"registry; its capacity cannot be verified against a claimed "
                       f"load of {claimed:,.1f} t."),
            severity=Severity.medium,
            metrics={"claimed_weight_tons": claimed},
            sources=sources,
        ))
        return ToolOutcome(ok=True,
                           summary=clip(f"Vessel '{vessel_name}' not in registry; claimed "
                                        f"{claimed:,.1f} t cannot be verified."),
                           observations=observations, raw=raw, sources=sources)

    dwt = float(vessel["dwt_tons"])
    utilisation = round(claimed / dwt * 100.0, 1)
    excess = round(max(0.0, claimed - dwt), 1)
    raw.update({
        "vessel_in_registry": True,
        "dwt_tons": dwt,
        "vessel_type": vessel["vessel_type"],
        "max_speed_knots": vessel["max_speed_knots"],
        "utilisation_pct": utilisation,
        "excess_tons": excess,
    })
    sources = [derived_source("check_vessel_capacity", "utilisation_pct", utilisation),
               ref_source("vessels", vessel["vessel_name"], value=dwt,
                          label=f"{vessel['vessel_name']} capacity")]

    severity = capacity_severity(utilisation)
    if severity is not Severity.none:
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.physical,
            statement=(f"Claimed cargo weight {claimed:,.1f} t is {utilisation:.1f}% of "
                       f"{vessel_name}'s {dwt:,.0f} t capacity"
                       + (f", exceeding it by {excess:,.1f} t" if excess > 0 else "")
                       + "."),
            severity=severity,
            metrics={"dwt_tons": dwt, "claimed_weight_tons": claimed,
                     "utilisation_pct": utilisation, "excess_tons": excess},
            sources=sources,
        ))
        summary = clip(f"{vessel_name}: claimed {claimed:,.1f} t vs {dwt:,.0f} t capacity "
                       f"= {utilisation:.1f}% utilisation (excess {excess:,.1f} t).")
    else:
        summary = clip(f"{vessel_name}: claimed {claimed:,.1f} t vs {dwt:,.0f} t capacity "
                       f"= {utilisation:.1f}% utilisation, within capacity.")

    return ToolOutcome(ok=True, summary=summary, observations=observations,
                       raw=raw, sources=sources)
