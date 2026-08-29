"""Case generator: clean shipment construction + anomaly injection + labelling.

Core invariant: every anomaly is applied by mutating the underlying Shipment
and re-rendering the documents — never by editing one document's text — so the
anomaly is visible to every tool that should see it.

Two construction paths share the same injection/rendering pipeline:

- ``generate_case(spec)`` — public, deterministic on (spec, seed): builds a
  coherent clean shipment from the seed, then applies ``spec.anomalies``.
- ``build_case_from_blueprint`` — pinned construction used for the demo cases
  (CaseSpec cannot carry ports/vessel/dates by contract; the blueprint pins
  them explicitly and records the same seed in the label).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from interpretex_contracts import (
    DEFAULT_TOOL_NAMES,
    AnomalyKind,
    CaseClass,
    CaseLabel,
    CaseSpec,
    Flags,
    TradeCase,
)

from .documents import render_documents
from .extraction import extract
from .reference import Commodity, ReferenceWorld, load_world, prices_summary, transit_band_days
from .shipment import Shipment

RECURRING_BROKER_ID = "ENT-003"   # broker reused across previously escalated trades
SHARED_UBO_SELLER_ID = "ENT-002"  # shares a UBO with ENT-012 (Nimbus Freight)

#: default parties per commodity (exporter, importer) in the reference world
DEFAULT_PARTIES: dict[str, tuple[str, str]] = {
    "copper_cathode": ("ENT-002", "ENT-004"),
    "aluminium_ingot": ("ENT-005", "ENT-001"),
    "coffee_arabica": ("ENT-006", "ENT-007"),
    "wheat": ("ENT-014", "ENT-007"),
    "zinc": ("ENT-013", "ENT-017"),
    "palm_oil": ("ENT-013", "ENT-017"),
    "cotton": ("ENT-014", "ENT-012"),
    "polyethylene_resin": ("ENT-013", "ENT-012"),
}

#: tonnes per shipping package, for package-count realism
PKG_UNIT_T = {"coffee_arabica": 0.06, "cotton": 0.227}

CLASS_PREFIX = {
    "clean": "clean",
    "suspicious_but_legitimate": "explainable",
    "illicit": "suspicious",
    "adversarial": "adv",
}
EXPECTED_VERDICT = {
    "clean": "release",
    "suspicious_but_legitimate": "hold",
    "illicit": "escalate",
    "adversarial": "hold",
}

#: magnitude applied when a spec requests an anomaly without one
MAGNITUDE_DEFAULTS: dict[str, float] = {
    "under_invoicing": 0.20,
    "over_invoicing": 0.20,
    "capacity_exceeded": 0.15,
    "impossible_transit": 1.0,
    "insurance_after_shipment": 8.0,
    "description_drift": 1.0,
    "quantity_mismatch": 0.05,
    "hs_code_mismatch": 1.0,
    "route_deviation": 1.0,
    "historical_deviation": 0.15,
    "intermediary_reuse": 1.0,
    "shared_ownership": 1.0,
}


# ---------------------------------------------------------------- injection --

@dataclass
class _Ctx:
    world: ReferenceWorld
    commodity: Commodity
    vessel: dict[str, Any]
    benchmark: float


def _reprice(s: Shipment) -> None:
    s.total_value = round(s.unit_price * s.quantity, 2)


def _inject_under_invoicing(s: Shipment, m: float, ctx: _Ctx) -> None:
    s.unit_price = round(ctx.benchmark * (1.0 - m), 2)
    _reprice(s)


def _inject_over_invoicing(s: Shipment, m: float, ctx: _Ctx) -> None:
    s.unit_price = round(ctx.benchmark * (1.0 + m), 2)
    _reprice(s)


def _inject_capacity_exceeded(s: Shipment, m: float, ctx: _Ctx) -> None:
    target = round(ctx.vessel["dwt_tons"] * (1.0 + m), 1)
    if abs(s.gross_weight_tons - target) > ctx.vessel["dwt_tons"] * 0.01:
        s.gross_weight_tons = target
        s.net_weight_tons = round(target / (1.0 + ctx.commodity.packing_factor), 1)


def _inject_impossible_transit(s: Shipment, m: float, ctx: _Ctx) -> None:
    days = max(1, int(round(m)))
    s.arrival_date = (date.fromisoformat(s.ship_date) + timedelta(days=days)).isoformat()


def _inject_insurance_after_shipment(s: Shipment, m: float, ctx: _Ctx) -> None:
    days = max(0, int(round(m)))
    s.insurance_issue_date = (date.fromisoformat(s.ship_date) + timedelta(days=days)).isoformat()


def _inject_description_drift(s: Shipment, m: float, ctx: _Ctx) -> None:
    s.packing_description = ctx.commodity.drift_description


def _inject_quantity_mismatch(s: Shipment, m: float, ctx: _Ctx) -> None:
    s.packing_quantity = round(s.quantity * (1.0 + m), 2)


def _inject_hs_code_mismatch(s: Shipment, m: float, ctx: _Ctx) -> None:
    s.coo_hs_code = ctx.commodity.alt_hs_code


def _inject_route_deviation(s: Shipment, m: float, ctx: _Ctx) -> None:
    alt = ctx.commodity.alt_destination(s.destination_port)
    if alt:
        s.bl_destination_port = alt


def _inject_historical_deviation(s: Shipment, m: float, ctx: _Ctx) -> None:
    hist = ctx.world.trades_for_entity(s.importer_id, s.commodity_key,
                                       before_or_on=s.ship_date)
    if not hist:
        return  # no history to deviate from; label still records the intent
    med = prices_summary([t.unit_price for t in hist])["median"]
    s.unit_price = round(med * (1.0 - m), 2)
    _reprice(s)


def _inject_intermediary_reuse(s: Shipment, m: float, ctx: _Ctx) -> None:
    s.broker_id = RECURRING_BROKER_ID


def _inject_shared_ownership(s: Shipment, m: float, ctx: _Ctx) -> None:
    if ctx.world.entity(s.exporter_id)["role"] == "seller":
        s.exporter_id = SHARED_UBO_SELLER_ID
    else:
        s.importer_id = SHARED_UBO_SELLER_ID


INJECTORS = {
    AnomalyKind.under_invoicing: _inject_under_invoicing,
    AnomalyKind.over_invoicing: _inject_over_invoicing,
    AnomalyKind.capacity_exceeded: _inject_capacity_exceeded,
    AnomalyKind.impossible_transit: _inject_impossible_transit,
    AnomalyKind.insurance_after_shipment: _inject_insurance_after_shipment,
    AnomalyKind.description_drift: _inject_description_drift,
    AnomalyKind.quantity_mismatch: _inject_quantity_mismatch,
    AnomalyKind.hs_code_mismatch: _inject_hs_code_mismatch,
    AnomalyKind.route_deviation: _inject_route_deviation,
    AnomalyKind.historical_deviation: _inject_historical_deviation,
    AnomalyKind.intermediary_reuse: _inject_intermediary_reuse,
    AnomalyKind.shared_ownership: _inject_shared_ownership,
    AnomalyKind.none: lambda s, m, ctx: None,
}


def apply_anomalies(s: Shipment, anomalies: list[AnomalyKind],
                    magnitudes: dict[str, float], world: ReferenceWorld,
                    rng: random.Random) -> None:
    """Apply every requested anomaly to the shipment, in list order."""
    commodity = world.commodity(s.commodity_key)
    vessel = world.vessel(s.vessel_name) or {}
    month = s.ship_date[:7]
    benchmark = commodity.benchmark(month) or commodity.benchmark("2026-08") or 0.0
    ctx = _Ctx(world=world, commodity=commodity, vessel=vessel, benchmark=benchmark)
    for kind in anomalies:
        magnitude = magnitudes.get(kind.value,
                                   magnitudes.get(kind, MAGNITUDE_DEFAULTS[kind.value]))
        INJECTORS[kind](s, float(magnitude), ctx)


# ------------------------------------------------------------- construction --


def _doc_ids(rng: random.Random, with_contract: bool, with_inspection: bool) -> dict[str, str]:
    base = rng.randint(1000, 8900)

    def n(off: int) -> str:
        return f"{base + off:04d}"

    ids = {
        "letter_of_credit": f"LC-2026-{n(0)}",
        "commercial_invoice": f"INV-2026-{n(1)}",
        "bill_of_lading": f"BL-{n(2)}",
        "packing_list": f"PL-{n(3)}",
        "certificate_of_origin": f"COO-{n(4)}",
        "insurance_certificate": f"INS-{n(5)}",
    }
    if with_contract:
        ids["sales_contract"] = f"SC-2024-{n(6)}"
    if with_inspection:
        ids["inspection_certificate"] = f"INSP-{n(7)}"
    return ids


def _derive_weights_and_counts(s: Shipment, packing_factor: float) -> None:
    s.net_weight_tons = round(s.quantity, 1)
    s.gross_weight_tons = round(s.quantity * (1.0 + packing_factor), 1)
    s.container_count = max(1, int(round(s.quantity / 25.0)))
    pkg_unit = PKG_UNIT_T.get(s.commodity_key, 1.0)
    s.package_count = max(1, int(round(s.quantity / pkg_unit)))


def _build_shipment(
    *,
    case_id: str,
    commodity: Commodity,
    exporter_id: str,
    importer_id: str,
    broker_id: str | None,
    quantity: float,
    unit_price: float,
    grade: str,
    origin_port: str,
    destination_port: str,
    vessel_name: str,
    ship_date: str,
    arrival_date: str,
    insurance_issue_date: str,
    lc_issue_date: str,
    incoterm: str,
    month: str,
    title: str,
    received_at: datetime,
    contract_claims: list[str],
    inspect_before_shipment: bool,
    bank_reference: str,
    applicant_note: str,
    doc_ids: dict[str, str],
) -> Shipment:
    world = load_world()
    exporter = world.entity(exporter_id)
    total = round(unit_price * quantity, 2)
    s = Shipment(
        case_id=case_id,
        title=title,
        received_at=received_at,
        bank_reference=bank_reference,
        applicant_note=applicant_note,
        exporter_id=exporter_id,
        importer_id=importer_id,
        broker_id=broker_id,
        insurer_id="ENT-009",
        commodity_key=commodity.key,
        commodity_display=commodity.display_name,
        commodity_grade=grade,
        hs_code=commodity.hs_code,
        description=commodity.display_name,
        packing_description=commodity.display_name,
        quantity=round(float(quantity), 2),
        unit=commodity.unit,
        unit_price=round(float(unit_price), 2),
        currency=commodity.currency,
        total_value=total,
        incoterm=incoterm,
        country_of_origin=exporter["country"],
        vessel_name=vessel_name,
        imo=(world.vessel(vessel_name) or {}).get("imo", ""),
        origin_port=origin_port,
        destination_port=destination_port,
        bl_destination_port=destination_port,
        coo_hs_code=commodity.hs_code,
        packing_quantity=round(float(quantity), 2),
        ship_date=ship_date,
        arrival_date=arrival_date,
        lc_issue_date=lc_issue_date,
        insurance_issue_date=insurance_issue_date,
        lc_number=doc_ids["letter_of_credit"],
        bl_number=doc_ids["bill_of_lading"],
        contract_reference=doc_ids.get("sales_contract"),
        contract_claims=list(contract_claims),
        inspect_before_shipment=inspect_before_shipment,
        doc_ids=doc_ids,
    )
    _derive_weights_and_counts(s, commodity.packing_factor)
    return s


def _construct_clean(spec: CaseSpec, world: ReferenceWorld,
                     rng: random.Random) -> tuple[Shipment, dict[str, Any]]:
    """Deterministic clean-shipment construction from a CaseSpec + seed."""
    if spec.commodity:
        commodity = world.commodity(spec.commodity)
        if commodity is None:
            raise KeyError(f"unknown commodity key: {spec.commodity!r}")
    else:
        commodity = world.commodities[
            sorted(world.commodities)[rng.randrange(len(world.commodities))]]

    month = rng.choice(["2026-07", "2026-08"])
    benchmark = commodity.monthly_benchmarks[month]
    band = commodity.plausible_band_pct
    unit_price = round(benchmark * (1.0 + rng.uniform(-0.6 * band, 0.6 * band)), 2)
    quantity = spec.quantity if spec.quantity else round(
        rng.uniform(*commodity.typical_qty_tons), 0)

    exporter_id = spec.exporter_id or DEFAULT_PARTIES[commodity.key][0]
    importer_id = spec.importer_id or DEFAULT_PARTIES[commodity.key][1]

    origin, destination = rng.choice(commodity.routes)
    gross = round(quantity * (1.0 + commodity.packing_factor), 1)
    adequate = [v for v in world.vessels.values() if v["dwt_tons"] >= gross * 1.15]
    vessel = min(adequate, key=lambda v: v["dwt_tons"]) if adequate else \
        max(world.vessels.values(), key=lambda v: v["dwt_tons"])

    distance = world.distance_nm(origin, destination) or 1000.0
    band_low, band_high = transit_band_days(distance, vessel["max_speed_knots"])
    transit_days = rng.randint(band_low, band_high)

    ship = date(int(month[:4]), int(month[5:7]), rng.randint(2, 24))
    arrival = ship + timedelta(days=transit_days)
    insurance = ship - timedelta(days=rng.randint(1, 3))
    lc = ship - timedelta(days=rng.randint(5, 8))
    received = datetime.combine(ship - timedelta(days=rng.randint(2, 5)),
                                datetime.min.time()).replace(
        hour=9, tzinfo=timezone.utc)

    contract_claims = (["long_term_offtake", "bulk_discount"]
                       if spec.plant_supporting_contract else [])
    with_inspection = spec.plant_supporting_contract and rng.random() < 0.5
    incoterm = rng.choice(["CIF", "CFR", "FOB"])
    doc_ids = _doc_ids(rng, bool(contract_claims), with_inspection)
    origin_name = world.port(origin)["name"]
    dest_name = world.port(destination)["name"]

    meta = {"benchmark": benchmark, "month": month}
    shipment = _build_shipment(
        case_id=_spec_case_id(spec),
        commodity=commodity,
        exporter_id=exporter_id,
        importer_id=importer_id,
        broker_id="ENT-008",
        quantity=quantity,
        unit_price=unit_price,
        grade=commodity.default_grade,
        origin_port=origin,
        destination_port=destination,
        vessel_name=vessel["vessel_name"],
        ship_date=ship.isoformat(),
        arrival_date=arrival.isoformat(),
        insurance_issue_date=insurance.isoformat(),
        lc_issue_date=lc.isoformat(),
        incoterm=incoterm,
        month=month,
        title=(f"{commodity.display_name} shipment — {origin_name} → {dest_name} "
               f"({doc_ids['letter_of_credit']})"),
        received_at=received,
        contract_claims=contract_claims,
        inspect_before_shipment=with_inspection,
        bank_reference=f"TRF/{doc_ids['letter_of_credit']}",
        applicant_note=("Documentary presentation received under the above LC; "
                        "please examine documents and advise."),
        doc_ids=doc_ids,
    )
    return shipment, meta


def _spec_case_id(spec: CaseSpec) -> str:
    return f"case_{CLASS_PREFIX[spec.case_class.value]}_{spec.seed % 1000:03d}"


# ---------------------------------------------------------------- assembly ---


def _assemble(s: Shipment, case_class: CaseClass, injected: list[AnomalyKind],
              seed: int, benign_explanation: str | None,
              evasion_notes: str | None) -> TradeCase:
    world = load_world()
    documents = render_documents(s)
    record = extract(documents)

    flags = Flags()
    tools = list(DEFAULT_TOOL_NAMES)
    if not flags.enabled("FEATURE_HISTORICAL"):
        tools.remove("check_historical_trade")
    if not flags.enabled("FEATURE_NETWORK"):
        tools.remove("check_counterparty_network")

    entities = []
    for eid in {s.exporter_id, s.importer_id, s.broker_id, s.insurer_id}:
        if eid and eid in world.entities:
            entities.append(world.entity(eid))
    if s.vessel_name:
        owner = (world.vessel(s.vessel_name) or {}).get("owner_entity_id")
        if owner and owner not in {e["entity_id"] for e in entities}:
            entities.append(world.entity(owner))

    from interpretex_contracts import Entity, Vessel
    vessel = Vessel(**world.vessel(s.vessel_name)) if s.vessel_name else None
    label = CaseLabel(
        case_class=case_class,
        injected_anomalies=injected,
        expected_verdict=EXPECTED_VERDICT[case_class.value],
        benign_explanation=benign_explanation,
        evasion_notes=evasion_notes,
        generator_seed=seed,
    )
    return TradeCase(
        case_id=s.case_id,
        received_at=s.received_at,
        bank_reference=s.bank_reference,
        applicant_note=s.applicant_note,
        documents=documents,
        record=record,
        available_tool_names=tools,
        title=s.title,
        entities=[Entity(**e) for e in entities],
        vessel=vessel,
        label=label,
    )


# ------------------------------------------------------------------ public ---


def generate_case(spec: CaseSpec, world: ReferenceWorld | None = None) -> TradeCase:
    """Deterministic on (spec, seed): same spec and seed -> byte-identical case."""
    world = world or load_world()
    rng = random.Random(spec.seed)
    shipment, _meta = _construct_clean(spec, world, rng)
    applied = [a for a in spec.anomalies if a is not AnomalyKind.none]
    if applied:
        apply_anomalies(shipment, applied, spec.anomaly_magnitudes, world, rng)
    return _assemble(shipment, spec.case_class, applied, spec.seed,
                     spec.benign_explanation, None)


def build_case_from_blueprint(bp: dict[str, Any]) -> TradeCase:
    """Pinned construction for the demo cases.

    ``bp`` keys mirror _build_shipment parameters plus ``case_class``,
    ``anomalies`` (list[AnomalyKind]), ``anomaly_magnitudes``, ``seed``,
    ``benign_explanation``, ``evasion_notes``. Everything is explicit; no
    randomness is consulted, so the demo cases are stable by construction.
    """
    world = load_world()
    commodity = world.commodity(bp["commodity_key"])
    if commodity is None:
        raise KeyError(f"unknown commodity key: {bp['commodity_key']!r}")
    case_class = CaseClass(bp["case_class"])
    seed = int(bp["seed"])
    anomalies = [AnomalyKind(a) for a in bp.get("anomalies", [])]
    magnitudes = dict(bp.get("anomaly_magnitudes", {}))
    shipment = _build_shipment(
        case_id=bp["case_id"],
        commodity=commodity,
        exporter_id=bp["exporter_id"],
        importer_id=bp["importer_id"],
        broker_id=bp.get("broker_id", "ENT-008"),
        quantity=bp["quantity"],
        unit_price=bp["unit_price"],
        grade=bp.get("grade", commodity.default_grade),
        origin_port=bp["origin_port"],
        destination_port=bp["destination_port"],
        vessel_name=bp["vessel_name"],
        ship_date=bp["ship_date"],
        arrival_date=bp["arrival_date"],
        insurance_issue_date=bp["insurance_issue_date"],
        lc_issue_date=bp["lc_issue_date"],
        incoterm=bp.get("incoterm", "CIF"),
        month=bp["ship_date"][:7],
        title=bp["title"],
        received_at=bp["received_at"],
        contract_claims=list(bp.get("contract_claims", [])),
        inspect_before_shipment=bool(bp.get("inspect_before_shipment", False)),
        bank_reference=bp["bank_reference"],
        applicant_note=bp["applicant_note"],
        doc_ids=bp["doc_ids"],
    )
    if anomalies:
        rng = random.Random(seed)
        apply_anomalies(shipment, anomalies, magnitudes, world, rng)
    return _assemble(shipment, case_class, anomalies, seed,
                     bp.get("benign_explanation"), bp.get("evasion_notes"))
