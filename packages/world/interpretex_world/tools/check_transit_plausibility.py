"""check_transit_plausibility — can this voyage have happened as claimed?"""

from __future__ import annotations

from datetime import date

from interpretex_contracts import Dimension, Observation, Severity, ToolSpec

from .base import (
    ToolOutcome, clip, derived_source, ref_source, transit_severity,
)
from ..reference import implied_speed_knots

SPEC = ToolSpec(
    name="check_transit_plausibility",
    description=(
        "Computes the great-circle distance between the declared ports, the "
        "expected transit band from the vessel's speed, the claimed transit time "
        "and the average speed the voyage would have to imply. Separates an "
        "impossible or fictitious voyage from a date-recording error from "
        "transhipment or an undeclared route."
    ),
    dimensions=[Dimension.temporal, Dimension.physical],
    args_schema={
        "type": "object",
        "properties": {
            "origin_port": {"type": "string"},
            "destination_port": {"type": "string"},
            "ship_date": {"type": "string"},
            "arrival_date": {"type": "string"},
            "vessel_name": {"type": "string"},
        },
        "additionalProperties": True,
    },
    cost_units=1,
    discriminates=["impossible or fictitious voyage", "date recording error",
                   "transhipment or undeclared route", "vessel substitution"],
)


def run(reg, args: dict) -> ToolOutcome:
    world = reg.world
    record = reg.record
    origin_code = str(args.get("origin_port") or record.origin_port or "")
    dest_code = str(args.get("destination_port") or record.destination_port or "")
    ship_iso = str(args.get("ship_date") or record.ship_date or "")
    arrival_iso = str(args.get("arrival_date") or record.arrival_date or "")
    vessel_name = str(args.get("vessel_name") or record.vessel_name or "")

    observations: list[Observation] = []
    raw: dict = {"origin_port": origin_code, "destination_port": dest_code,
                 "ship_date": ship_iso, "arrival_date": arrival_iso,
                 "vessel_name": vessel_name}
    sources = [derived_source("check_transit_plausibility", "implied_speed_knots", None)]

    origin, dest = world.find_port(origin_code), world.find_port(dest_code)
    unknown = [(c, p) for c, p in ((origin_code, origin), (dest_code, dest)) if p is None]
    for code, _p in unknown:
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.temporal,
            statement=(f"Port '{code}' is not present in the reference port registry; "
                       "the voyage cannot be geographically verified."),
            severity=Severity.medium,
            metrics={},
            sources=sources,
        ))
        raw[f"{code}_in_registry"] = False
    if unknown:
        return ToolOutcome(ok=True,
                           summary=clip(f"Unknown port(s): {', '.join(c for c, _ in unknown)}; "
                                        "voyage cannot be verified."),
                           observations=observations, raw=raw, sources=sources)

    vessel = world.vessel(vessel_name) if vessel_name else None
    if vessel:
        sources.append(ref_source("vessels", vessel["vessel_name"],
                                  value=vessel["max_speed_knots"],
                                  label=f"{vessel_name} speed"))
    distance = world.distance_nm(origin_code, dest_code)
    if distance is None:
        return ToolOutcome(ok=False, error="ports present but distance lookup failed")
    raw["distance_nm"] = round(distance, 1)
    if vessel:
        raw["max_speed_knots"] = vessel["max_speed_knots"]

    if not ship_iso or not arrival_iso:
        return ToolOutcome(ok=True,
                           summary="Ship or arrival date missing; transit cannot be checked.",
                           observations=observations, raw=raw, sources=sources)
    try:
        claimed_days = (date.fromisoformat(arrival_iso) - date.fromisoformat(ship_iso)).days
    except ValueError:
        return ToolOutcome(ok=False, error=f"unparseable dates {ship_iso!r}/{arrival_iso!r}")
    claimed_days = max(claimed_days, 0)
    raw["claimed_transit_days"] = float(claimed_days)

    if not vessel:
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.temporal,
            statement=(f"Vessel '{vessel_name}' is not in the reference registry; the "
                       f"expected transit band cannot be derived for the "
                       f"{distance:,.1f} nm voyage, claimed transit {claimed_days} day(s)."),
            severity=Severity.medium,
            metrics={"distance_nm": round(distance, 1), "claimed_transit_days": float(claimed_days)},
            sources=sources,
        ))
        return ToolOutcome(ok=True,
                           summary=clip(f"Vessel unknown; {distance:,.0f} nm claimed in "
                                        f"{claimed_days} day(s) unverified."),
                           observations=observations, raw=raw, sources=sources)

    band_low, band_high = world.transit_band(distance, vessel["max_speed_knots"])
    implied = round(implied_speed_knots(distance, claimed_days), 1)
    raw["expected_band_days"] = [band_low, band_high]
    raw["implied_speed_knots"] = implied
    sources = [derived_source("check_transit_plausibility", "implied_speed_knots", implied),
               ref_source("ports", origin["port_code"], value=None, label=origin["name"]),
               ref_source("ports", dest["port_code"], value=None, label=dest["name"])]

    severity = transit_severity(float(claimed_days), band_low, band_high)
    if severity is Severity.none:
        summary = clip(f"{distance:,.0f} nm in {claimed_days} day(s) implies "
                       f"{implied} kn; expected band {band_low}-{band_high} days; plausible.")
    else:
        observations.append(Observation(
            observation_id="",
            dimension=Dimension.temporal,
            statement=(f"Claimed transit of {claimed_days} day(s) for the "
                       f"{distance:,.1f} nm voyage {origin['name']} → {dest['name']} implies an "
                       f"average speed of {implied} knots, against an expected band of "
                       f"{band_low}-{band_high} days at up to "
                       f"{vessel['max_speed_knots']:.1f} knots."),
            severity=severity,
            metrics={
                "distance_nm": round(distance, 1),
                "claimed_transit_days": float(claimed_days),
                "expected_band_low_days": float(band_low),
                "expected_band_high_days": float(band_high),
                "implied_speed_knots": implied,
                "max_speed_knots": vessel["max_speed_knots"],
            },
            sources=sources,
            expected_range=[float(band_low), float(band_high)],
        ))
        summary = clip(f"{distance:,.0f} nm in {claimed_days} day(s) implies {implied} kn; "
                       f"expected band {band_low}-{band_high} days; outside plausible range.")
    return ToolOutcome(ok=True, summary=summary, observations=observations,
                       raw=raw, sources=sources)
