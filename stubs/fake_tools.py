"""FakeToolRegistry (Part 3 stub for Part 1's eight investigation tools).

Computes plausible ToolResults from the case data so stub mode is live enough
to drive /api/tools and to be inspectable. It never raises: bad args, unknown
tools and internal failure all return ok=False ToolResults, exactly as the
contract requires (the agent must be able to recover and re-plan).
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

from interpretex_contracts import (
    Dimension, Observation, Severity, SourceKind, SourceRef, ToolResult,
    ToolSpec,
)
from interpretex_contracts.trade import TradeCase

# commodity -> {as_of (YYYY-MM): {"price": float, "band_pct": float}}
BENCHMARKS: dict[str, dict[str, dict[str, float]]] = {
    "green coffee beans, arabica": {"2026-07": {"price": 4500.0, "band_pct": 0.06}},
    "aluminium ingots": {"2026-08": {"price": 2400.0, "band_pct": 0.08}},
    "copper cathodes": {"2026-08": {"price": 8900.0, "band_pct": 0.06}},
}

# UN/LOCODE -> (lat, lon)
PORTS: dict[str, tuple[float, float]] = {
    "BRSSZ": (-23.96, -46.33),
    "NLRTM": (51.95, 4.14),
    "AEJEA": (25.01, 55.06),
    "INNSA": (18.95, 72.95),
    "SGSIN": (1.29, 103.85),
}

# entity_id -> prior trades keyed by commodity
HISTORY: dict[str, dict[str, dict[str, Any]]] = {
    "E-ROTTERDAM-ROAST": {"green coffee beans, arabica": {"n": 8, "min": 4380, "median": 4490, "max": 4620}},
    "E-BHARAT-METALS": {"aluminium ingots": {"n": 6, "min": 1940, "median": 1975, "max": 2010}},
    "E-DECCAN-COPPER": {"copper cathodes": {"n": 7, "min": 8600, "median": 8850, "max": 9100}},
}

# entity_id -> network findings
NETWORK: dict[str, list[dict[str, Any]]] = {
    "E-MERIDIAN-TP": [
        {
            "finding_id": "NF-1", "pattern": "intermediary_reuse",
            "statement": "Broker Meridian Trade Partners is the broker of record on three previously escalated trade-finance cases (case_adv_2025_014, case_adv_2025_027, case_adv_2026_003).",
            "entity_ids": ["E-MERIDIAN-TP", "E-STRAITS-COMM"],
            "case_ids": ["case_adv_2025_014", "case_adv_2025_027", "case_adv_2026_003"],
            "severity": "high", "metrics": {"prior_escalations": 3},
        }
    ],
    "E-STRAITS-COMM": [
        {
            "finding_id": "NF-2", "pattern": "vessel_reuse",
            "statement": "Vessel MV Ocean Star appears on two prior flagged shipments carrying copper under different exporter names.",
            "entity_ids": ["E-STRAITS-COMM", "E-OCEAN-HOLD"],
            "case_ids": ["case_adv_2025_014", "case_adv_2026_003"],
            "severity": "medium", "metrics": {"prior_flagged_voyages": 2},
        }
    ],
}

_TOOL_SPECS = [
    ToolSpec(
        name="read_document",
        description="Return the structured fields and raw OCR text for one document, so the agent can read exactly what the file states.",
        dimensions=[Dimension.documentary],
        args_schema={"type": "object", "properties": {"doc_type": {"type": "string"}, "doc_id": {"type": "string"}}},
        cost_units=1, discriminates=[],
    ),
    ToolSpec(
        name="check_document_consistency",
        description="Compare key fields across all documents. Surfaces description drift, quantity mismatches, HS-code mismatches, and whether insurance was issued before shipment.",
        dimensions=[Dimension.documentary],
        args_schema={"type": "object", "properties": {"fields": {"type": "array", "items": {"type": "string"}}}},
        cost_units=1, discriminates=["description_drift", "quantity_mismatch", "hs_code_mismatch", "insurance_after_shipment"],
    ),
    ToolSpec(
        name="check_price_benchmark",
        description="Compare the declared unit price against the reference market benchmark for the as_of month and quantity tier. Separates a genuine under/over-invoice from a benign market-move or volume discount.",
        dimensions=[Dimension.economic],
        args_schema={"type": "object", "properties": {
            "commodity": {"type": "string"}, "grade": {"type": "string"}, "quantity": {"type": "number"},
            "as_of_date": {"type": "string"}, "declared_unit_price": {"type": "number"}},
            "required": ["commodity", "as_of_date", "declared_unit_price"]},
        cost_units=1, discriminates=["under_invoicing", "over_invoicing", "bulk_discount"],
    ),
    ToolSpec(
        name="check_vessel_capacity",
        description="Compare the declared cargo weight against the named vessel's deadweight. Separates a benign full load from a physical impossibility (more cargo than the vessel can carry).",
        dimensions=[Dimension.physical],
        args_schema={"type": "object", "properties": {"vessel_name": {"type": "string"}, "claimed_weight_tons": {"type": "number"}},
                     "required": ["vessel_name", "claimed_weight_tons"]},
        cost_units=1, discriminates=["capacity_exceeded"],
    ),
    ToolSpec(
        name="check_transit_plausibility",
        description="Compare the claimed voyage time against the great-circle distance at the vessel's max speed, including port handling. Separates a benign fast voyage from an impossible one (transit time implying a speed the vessel cannot reach).",
        dimensions=[Dimension.temporal, Dimension.physical],
        args_schema={"type": "object", "properties": {
            "origin_port": {"type": "string"}, "destination_port": {"type": "string"},
            "ship_date": {"type": "string"}, "arrival_date": {"type": "string"}, "vessel_name": {"type": "string"}},
            "required": ["origin_port", "destination_port", "ship_date", "arrival_date"]},
        cost_units=1, discriminates=["impossible_transit", "route_deviation"],
    ),
    ToolSpec(
        name="check_historical_trade",
        description="Look up the entity's prior trades in this commodity: price range, median, z-score of the current price. Separates a benign price the customer genuinely pays from an outlier suggesting mispricing.",
        dimensions=[Dimension.behavioural],
        args_schema={"type": "object", "properties": {
            "entity_id": {"type": "string"}, "commodity": {"type": "string"}, "lookback_months": {"type": "integer"}},
            "required": ["entity_id", "commodity"]},
        cost_units=2, discriminates=["historical_deviation"],
    ),
    ToolSpec(
        name="check_counterparty_network",
        description="Examine the counterparty network for shared intermediaries, shared UBOs, repeated vessels and co-occurring escalated cases. Separates a clean network from one with structural red flags.",
        dimensions=[Dimension.network],
        args_schema={"type": "object", "properties": {"entity_id": {"type": "string"}, "depth": {"type": "integer"}},
                     "required": ["entity_id"]},
        cost_units=2, discriminates=["intermediary_reuse", "shared_ownership", "vessel_reuse"],
    ),
    ToolSpec(
        name="check_contract_or_supporting_evidence",
        description="Check whether a document in the file supports a claimed benign commercial explanation (bulk discount, grade difference, distressed sale, long-term offtake, inspection) and quote the clause, or report an explicit not-found.",
        dimensions=[Dimension.economic, Dimension.documentary],
        args_schema={"type": "object", "properties": {"claim": {"type": "string", "enum": [
            "bulk_discount", "grade_difference", "distressed_sale", "long_term_offtake", "inspection"]}},
            "required": ["claim"]},
        cost_units=1, discriminates=["bulk_discount", "grade_difference", "distressed_sale", "long_term_offtake"],
    ),
]


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371.0
    la1, lo1 = math.radians(a[0]), math.radians(a[1])
    la2, lo2 = math.radians(b[0]), math.radians(b[1])
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(d))


def _as_of(month_date: str) -> str:
    for sep in ("-", "/"):
        parts = month_date.split(sep)
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]}"
    return month_date[:7]


def _norm_commodity(c: str) -> str:
    c = (c or "").lower()
    if "coffee" in c:
        return "green coffee beans, arabica"
    if "aluminium" in c or "aluminum" in c:
        return "aluminium ingots"
    if "copper" in c:
        return "copper cathodes"
    return c


class FakeToolRegistry:
    def __init__(self, case: TradeCase) -> None:
        self._case = case
        self._docs = {d.doc_id: d for d in case.documents}
        self._vessel = case.vessel

    def specs(self) -> list[ToolSpec]:
        return list(_TOOL_SPECS)

    def _weights(self) -> float:
        gw = self._case.record.gross_weight_tons
        return gw if gw is not None else self._case.record.quantity

    def _fail(self, name: str, call_id: str, args: dict, error: str, cost: int) -> ToolResult:
        return ToolResult(tool=name, call_id=call_id, args=args, ok=False, summary=error[:200], error=error, cost_units=cost)

    def call(self, name: str, args: dict) -> ToolResult:
        from uuid import uuid4
        call_id = f"call_{uuid4().hex[:8]}"
        try:
            handler = getattr(self, f"_t_{name}", None)
            if handler is None:
                return self._fail(name, call_id, args, f"unknown tool: {name}", 1)
            return handler(name, call_id, args or {})
        except Exception as exc:  # noqa: BLE001 - contract: never raise
            return self._fail(name, call_id, args or {}, f"{type(exc).__name__}: {exc}", 1)

    def _t_read_document(self, name, call_id, args):
        doc = self._docs.get(args.get("doc_id")) if args.get("doc_id") else None
        if doc is None and args.get("doc_type"):
            for d in self._case.documents:
                if d.doc_type.value == args["doc_type"]:
                    doc = d
                    break
        if doc is None:
            return self._fail(name, call_id, args, "document not found", 1)
        return ToolResult(
            tool=name, call_id=call_id, args=args, ok=True,
            summary=f"Read {doc.doc_type.value} {doc.doc_id} ({doc.extraction_confidence:.0%} confidence)",
            observations=[], raw={"fields": doc.fields, "raw_text": doc.raw_text},
            sources=[SourceRef(kind=SourceKind.document, ref=f"{doc.doc_id}", label=doc.doc_type.value)],
            cost_units=1, latency_ms=8,
        )

    def _t_check_document_consistency(self, name, call_id, args):
        rec = self._case.record
        obs: list[Observation] = []
        raw: dict[str, Any] = {"agreements": [], "disagreements": []}
        commodities = {d.doc_id: d.fields.get("commodity") for d in self._case.documents}
        distinct = {v for v in commodities.values() if v}
        if len(distinct) > 1:
            drift = sorted(distinct)
            obs.append(Observation(
                observation_id=f"O-{call_id}-drift", dimension=Dimension.documentary,
                statement=f"Commodity description differs across documents: {', '.join(drift)}.",
                severity=Severity.high, metrics={"distinct_descriptions": len(distinct)},
                sources=[SourceRef(kind=SourceKind.document, ref=f"{d.doc_id}.commodity", value=str(commodities[d.doc_id]))
                         for d in self._case.documents if commodities[d.doc_id]],
                expected_range="single consistent commodity description",
            ))
            raw["disagreements"].append({"kind": "description_drift", "values": drift})
        q = [d.fields.get("quantity") for d in self._case.documents if d.fields.get("quantity") is not None]
        if q and any(abs(x - rec.quantity) > max(1, rec.quantity * 0.001) for x in q):
            obs.append(Observation(
                observation_id=f"O-{call_id}-qty", dimension=Dimension.documentary,
                statement=f"Quantity disagrees across documents (record {rec.quantity} {rec.unit}).",
                severity=Severity.medium, metrics={"record_quantity": rec.quantity},
                sources=[SourceRef(kind=SourceKind.document, ref=f"{d.doc_id}.quantity", value=str(d.fields.get("quantity")))
                         for d in self._case.documents],
            ))
        if rec.insurance_issue_date and rec.ship_date:
            ins = date.fromisoformat(rec.insurance_issue_date[:10])
            ship = date.fromisoformat(rec.ship_date[:10])
            if ins > ship:
                lag = (ins - ship).days
                obs.append(Observation(
                    observation_id=f"O-{call_id}-ins", dimension=Dimension.documentary,
                    statement=f"Insurance certificate issued {lag} days after the stated shipment date - coverage is retroactive.",
                    severity=Severity.high, metrics={"insurance_lag_days": float(lag)},
                    sources=[
                        SourceRef(kind=SourceKind.document, ref="INS.insurance_issue_date", value=rec.insurance_issue_date),
                        SourceRef(kind=SourceKind.document, ref="BL.ship_date", value=rec.ship_date),
                    ],
                    expected_range="insurance issued on or before shipment",
                ))
                raw["disagreements"].append({"kind": "insurance_after_shipment", "lag_days": lag})
        if not obs:
            obs.append(Observation(
                observation_id=f"O-{call_id}-ok", dimension=Dimension.documentary,
                statement="All documents agree on commodity, quantity, value and chronology; no internal inconsistency found.",
                severity=Severity.none, metrics={},
                sources=[SourceRef(kind=SourceKind.document, ref=f"{d.doc_id}", label=d.doc_type.value) for d in self._case.documents],
            ))
            raw["agreements"].append("all_fields_consistent")
        summary = "; ".join(o.statement for o in obs)[:200]
        return ToolResult(tool=name, call_id=call_id, args=args, ok=True, summary=summary, observations=obs, raw=raw, sources=[], cost_units=1, latency_ms=12)

    def _t_check_price_benchmark(self, name, call_id, args):
        commodity = _norm_commodity(args.get("commodity", self._case.record.commodity))
        as_of = _as_of(args.get("as_of_date", self._case.record.ship_date or ""))
        declared = float(args.get("declared_unit_price", self._case.record.unit_price))
        bench = BENCHMARKS.get(commodity, {}).get(as_of)
        if bench is None:
            return self._fail(name, call_id, args, f"no benchmark for {commodity} @ {as_of}", 1)
        price, band = bench["price"], bench["band_pct"]
        dev = (declared - price) / price
        sev = Severity.none
        if abs(dev) > band:
            sev = Severity.high if abs(dev) > 2 * band else Severity.medium
        obs = Observation(
            observation_id=f"O-{call_id}-price", dimension=Dimension.economic,
            statement=f"Declared unit price {declared:,.0f} {self._case.record.currency}/t vs {as_of} benchmark {price:,.0f} ({dev*100:+.1f}%).",
            severity=sev, metrics={"declared": declared, "benchmark": price, "deviation_pct": round(dev * 100, 2)},
            sources=[SourceRef(kind=SourceKind.reference_db, ref=f"benchmarks/{commodity}/{as_of}", value=str(price), as_of=as_of)],
            expected_range=f"±{band*100:.0f}% of benchmark",
        )
        return ToolResult(tool=name, call_id=call_id, args=args, ok=True,
                          summary=f"Price {declared:,.0f} vs {price:,.0f} benchmark ({dev*100:+.1f}%)",
                          observations=[obs], raw={"declared": declared, "benchmark": price, "deviation_pct": round(dev * 100, 2), "band_pct": band},
                          sources=obs.sources, cost_units=1, latency_ms=15)

    def _t_check_vessel_capacity(self, name, call_id, args):
        vessel_name = args.get("vessel_name", self._case.record.vessel_name)
        claimed = float(args.get("claimed_weight_tons", self._weights()))
        vessel = self._vessel if (self._vessel and (vessel_name is None or self._vessel.vessel_name == vessel_name)) else None
        if vessel is None:
            return self._fail(name, call_id, args, "vessel not found in case", 1)
        dwt = vessel.dwt_tons
        util = claimed / dwt
        sev = Severity.high if util > 1.0 else Severity.none
        obs = Observation(
            observation_id=f"O-{call_id}-cap", dimension=Dimension.physical,
            statement=f"Declared load {claimed:,.0f} t against vessel capacity {dwt:,.0f} t ({util*100:.1f}% utilisation).",
            severity=sev, metrics={"dwt_tons": dwt, "claimed_tons": claimed, "utilisation_pct": round(util * 100, 1)},
            sources=[
                SourceRef(kind=SourceKind.document, ref="BL.gross_weight_tons", value=str(claimed)),
                SourceRef(kind=SourceKind.reference_db, ref=f"vessels/{vessel.vessel_name}", value=str(dwt)),
            ],
            expected_range="load <= deadweight",
        )
        return ToolResult(tool=name, call_id=call_id, args=args, ok=True,
                          summary=f"Capacity {claimed:,.0f}/{dwt:,.0f} t ({util*100:.1f}%)",
                          observations=[obs], raw={"dwt_tons": dwt, "claimed_tons": claimed, "utilisation_pct": round(util * 100, 1)},
                          sources=obs.sources, cost_units=1, latency_ms=10)

    def _t_check_transit_plausibility(self, name, call_id, args):
        o = args.get("origin_port", self._case.record.origin_port)
        d = args.get("destination_port", self._case.record.destination_port)
        ship = args.get("ship_date", self._case.record.ship_date)
        arr = args.get("arrival_date", self._case.record.arrival_date)
        if not (o in PORTS and d in PORTS and ship and arr):
            return self._fail(name, call_id, args, "missing port or date for transit check", 1)
        dist = _haversine(PORTS[o], PORTS[d])
        speed = self._vessel.max_speed_knots if self._vessel else 14.0
        expected_days = dist / (speed * 1.852) / 24.0 + 1.5
        transit_days = (date.fromisoformat(arr[:10]) - date.fromisoformat(ship[:10])).days
        implied_speed = dist / max(transit_days, 0.5) / 24.0
        lo, hi = 0.5 * expected_days, 2.0 * expected_days
        impossible = transit_days < lo * 0.5 or implied_speed > speed * 1.2
        sev = Severity.high if impossible else Severity.none
        obs = Observation(
            observation_id=f"O-{call_id}-transit", dimension=Dimension.temporal,
            statement=f"Claimed transit {transit_days} d over {dist:,.0f} km (great-circle) implies {implied_speed:.0f} kn vs vessel max {speed:.0f} kn.",
            severity=sev,
            metrics={"great_circle_km": round(dist), "expected_days": round(expected_days, 1), "claimed_days": transit_days,
                     "implied_speed_knots": round(implied_speed, 1), "vessel_max_knots": speed},
            sources=[
                SourceRef(kind=SourceKind.reference_db, ref=f"ports/{o}", value=str(PORTS[o])),
                SourceRef(kind=SourceKind.reference_db, ref=f"ports/{d}", value=str(PORTS[d])),
                SourceRef(kind=SourceKind.document, ref="BL.ship_date", value=ship),
                SourceRef(kind=SourceKind.document, ref="BL.arrival_date", value=arr),
            ],
            expected_range=f"{lo:.1f}-{hi:.1f} days plausible",
        )
        return ToolResult(tool=name, call_id=call_id, args=args, ok=True,
                          summary=f"Transit {transit_days} d, implied {implied_speed:.0f} kn (max {speed:.0f})",
                          observations=[obs], raw={"great_circle_km": round(dist), "expected_days": round(expected_days, 1),
                          "claimed_days": transit_days, "implied_speed_knots": round(implied_speed, 1)},
                          sources=obs.sources, cost_units=1, latency_ms=14)

    def _t_check_historical_trade(self, name, call_id, args):
        entity_id = args.get("entity_id", self._case.record.importer_id)
        commodity = _norm_commodity(args.get("commodity", self._case.record.commodity))
        hist = HISTORY.get(entity_id, {}).get(commodity)
        price = self._case.record.unit_price
        if hist is None:
            obs = Observation(
                observation_id=f"O-{call_id}-hist", dimension=Dimension.behavioural,
                statement=f"No prior trades for {entity_id} in {commodity}; no behavioural baseline available.",
                severity=Severity.low, metrics={},
                sources=[SourceRef(kind=SourceKind.reference_db, ref=f"history/{entity_id}/{commodity}", value="none")],
            )
            return ToolResult(tool=name, call_id=call_id, args=args, ok=True, summary="No prior history for this counterparty",
                              observations=[obs], raw={"entity_id": entity_id, "prior_trades": 0}, sources=obs.sources, cost_units=2, latency_ms=16)
        med, lo, hi = hist["median"], hist["min"], hist["max"]
        sd = max((hi - lo) / 4.0, 1.0)
        z = (price - med) / sd
        sev = Severity.medium if abs(z) > 1.5 else Severity.low
        obs = Observation(
            observation_id=f"O-{call_id}-hist", dimension=Dimension.behavioural,
            statement=f"This entity's {hist['n']} prior {commodity} trades ranged {lo:,.0f}-{hi:,.0f} ({med:,.0f} median); current {price:,.0f} is z={z:+.2f}.",
            severity=sev, metrics={"median": med, "min": lo, "max": hi, "n": hist["n"], "z_score": round(z, 2)},
            sources=[SourceRef(kind=SourceKind.reference_db, ref=f"history/{entity_id}/{commodity}", value=f"{lo}-{hi}")],
            expected_range=f"{lo:,.0f}-{hi:,.0f}",
        )
        return ToolResult(tool=name, call_id=call_id, args=args, ok=True,
                          summary=f"History {lo:,.0f}-{hi:,.0f}, z={z:+.2f}", observations=[obs],
                          raw={"median": med, "min": lo, "max": hi, "n": hist["n"], "z_score": round(z, 2)},
                          sources=obs.sources, cost_units=2, latency_ms=18)

    def _t_check_counterparty_network(self, name, call_id, args):
        entity_id = args.get("entity_id", self._case.record.broker_id or self._case.record.exporter_id)
        findings = NETWORK.get(entity_id, [])
        obs: list[Observation] = []
        for f in findings:
            sev = Severity.high if f["severity"] == "high" else Severity.medium
            obs.append(Observation(
                observation_id=f"O-{call_id}-{f['finding_id']}", dimension=Dimension.network,
                statement=f["statement"], severity=sev, metrics=f.get("metrics", {}),
                sources=[SourceRef(kind=SourceKind.reference_db, ref=f"network/{f['pattern']}", value=str(entity_id))],
            ))
        if not obs:
            obs.append(Observation(
                observation_id=f"O-{call_id}-netok", dimension=Dimension.network,
                statement=f"No structural network flags found for {entity_id}.",
                severity=Severity.none, metrics={},
                sources=[SourceRef(kind=SourceKind.reference_db, ref=f"network/{entity_id}", value="clean")],
            ))
        summary = "; ".join(o.statement for o in obs)[:200]
        return ToolResult(tool=name, call_id=call_id, args=args, ok=True, summary=summary, observations=obs,
                          raw={"entity_id": entity_id, "findings": findings},
                          sources=[s for o in obs for s in o.sources], cost_units=2, latency_ms=20)

    def _t_check_contract_or_supporting_evidence(self, name, call_id, args):
        claim = args.get("claim", "")
        keywords = {
            "bulk_discount": ["discount", "tier"],
            "long_term_offtake": ["offtake", "three-year", "master sales contract", "volume-tier"],
            "grade_difference": ["grade", "p1020", "grade a", "screen"],
            "distressed_sale": ["distressed", "urgent sale", "liquidation"],
            "inspection": ["inspection", "survey", "inspector"],
        }.get(claim, [])
        for d in self._case.documents:
            hay = ((d.raw_text or "") + " " + str(d.fields)).lower()
            if any(k in hay for k in keywords):
                obs = Observation(
                    observation_id=f"O-{call_id}-contract", dimension=Dimension.economic,
                    statement=f"Document {d.doc_id} supports '{claim}': clause quoted from the file.",
                    severity=Severity.none,
                    sources=[SourceRef(kind=SourceKind.document, ref=f"{d.doc_id}.raw_text", value=claim, label=d.doc_type.value)],
                )
                return ToolResult(tool=name, call_id=call_id, args=args, ok=True,
                                  summary=f"Supporting document found: {d.doc_id}", observations=[obs],
                                  raw={"found": True, "doc_id": d.doc_id, "claim": claim}, sources=obs.sources, cost_units=1, latency_ms=9)
        obs = Observation(
            observation_id=f"O-{call_id}-contract-nf", dimension=Dimension.economic,
            statement=f"No document in the file supports the claimed '{claim}'.",
            severity=Severity.medium,
            sources=[SourceRef(kind=SourceKind.document, ref="case.documents", value="not_found")],
        )
        return ToolResult(tool=name, call_id=call_id, args=args, ok=True,
                          summary=f"No supporting document for '{claim}'", observations=[obs],
                          raw={"found": False, "claim": claim}, sources=obs.sources, cost_units=1, latency_ms=9)
