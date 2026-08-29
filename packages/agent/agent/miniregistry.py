"""A case-scoped in-memory ToolRegistry implementing the eight contract tools
over a tiny synthetic reference world, with the exact demo-case numbers from
master plan section 13.

This is test/eval scaffolding ONLY (the stand-in for Part 1's real registry —
never imported by the agent's runtime modules). It exists so Part 2 is not
blocked on Part 1's fixtures; `python -m agent.eval` and `tests/agent` use it.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from interpretex_contracts import (
    AgentCaseView,
    Dimension,
    Observation,
    Severity,
    SourceKind,
    SourceRef,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)

# --------------------------------------------------------------------- specs

S = lambda props, req: {"type": "object", "properties": props, "required": req, "additionalProperties": False}  # noqa: E731

TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="read_document",
        description="Returns the structured fields and raw text of one document, so its claims can be quoted and compared.",
        dimensions=[Dimension.documentary],
        args_schema=S({"doc_type": {"type": "string"}, "doc_id": {"type": "string"}}, []),
        cost_units=1,
        discriminates=[],
    ),
    ToolSpec(
        name="check_document_consistency",
        description="Cross-checks every shared field across the whole document set; yields description drift, quantity and HS-code mismatches, and date-order violations such as insurance issued after shipment.",
        dimensions=[Dimension.documentary],
        args_schema=S({"fields": {"type": "array", "items": {"type": "string"}}}, []),
        cost_units=1,
        discriminates=["H3", "H4", "H9"],
    ),
    ToolSpec(
        name="check_price_benchmark",
        description="Compares the declared unit price against the dated market benchmark and its volume-tier band; separates a bulk-discount or contract price from under-invoicing.",
        dimensions=[Dimension.economic],
        args_schema=S({
            "commodity": {"type": "string"}, "quantity": {"type": "number"},
            "as_of_date": {"type": "string"}, "declared_unit_price": {"type": "number"},
        }, ["commodity", "quantity", "as_of_date", "declared_unit_price"]),
        cost_units=1,
        discriminates=["H1", "H2", "H10"],
    ),
    ToolSpec(
        name="check_vessel_capacity",
        description="Checks the claimed cargo weight against the named vessel's registered deadweight capacity; separates a clerical tonnage error from a physically impossible load.",
        dimensions=[Dimension.physical],
        args_schema=S({"vessel_name": {"type": "string"}, "claimed_weight_tons": {"type": "number"}},
                      ["vessel_name", "claimed_weight_tons"]),
        cost_units=1,
        discriminates=["H5", "H6"],
    ),
    ToolSpec(
        name="check_transit_plausibility",
        description="Computes great-circle distance and the feasible transit band at the vessel's speed, then compares the claimed ship-to-arrival window; separates a mis-keyed date from an impossible voyage.",
        dimensions=[Dimension.temporal, Dimension.physical],
        args_schema=S({
            "origin_port": {"type": "string"}, "destination_port": {"type": "string"},
            "ship_date": {"type": "string"}, "arrival_date": {"type": "string"},
            "vessel_name": {"type": "string"},
        }, ["origin_port", "destination_port", "ship_date", "arrival_date"]),
        cost_units=1,
        discriminates=["H5", "H6", "H7", "H8"],
    ),
    ToolSpec(
        name="check_historical_trade",
        description="Retrieves this entity's own prior trades in the commodity: price range, median, counterparties and the z-score of the current price; separates the customer's normal pricing from a historical deviation.",
        dimensions=[Dimension.behavioural],
        args_schema=S({"entity_id": {"type": "string"}, "commodity": {"type": "string"},
                       "lookback_months": {"type": "integer"}}, ["entity_id", "commodity"]),
        cost_units=2,
        discriminates=["H1", "H2", "H10"],
    ),
    ToolSpec(
        name="check_counterparty_network",
        description="Looks up the entity's network: shared intermediaries, common beneficial owners, vessels reused across cases, and links to previously escalated cases.",
        dimensions=[Dimension.network],
        args_schema=S({"entity_id": {"type": "string"}, "depth": {"type": "integer"}}, ["entity_id"]),
        cost_units=2,
        discriminates=[],
    ),
    ToolSpec(
        name="check_contract_or_supporting_evidence",
        description="Searches the case file for a document that supports a claimed commercial explanation (bulk_discount, grade_difference, distressed_sale, long_term_offtake, inspection) and quotes the clause, or returns an explicit not-found.",
        dimensions=[Dimension.economic, Dimension.documentary],
        args_schema=S({"claim": {"type": "string", "enum": [
            "bulk_discount", "grade_difference", "distressed_sale", "long_term_offtake", "inspection"]}},
            ["claim"]),
        cost_units=1,
        discriminates=["H1", "H9"],
    ),
]

_SPEC_BY_NAME = {s.name: s for s in TOOL_SPECS}


# ---------------------------------------------------------------- mini world

def _refs(doc: str, field: str) -> list[SourceRef]:
    return [SourceRef(kind=SourceKind.document, ref=f"{doc}.{field}")]


def _ref_db(table: str, key: str, as_of: str | None = None) -> SourceRef:
    ref = f"{table}/{key}" + (f"/{as_of}" if as_of else "")
    return SourceRef(kind=SourceKind.reference_db, ref=ref, as_of=as_of)


class MiniWorld:
    """Numeric ground for one case; field names mirror master plan section 13."""

    def __init__(
        self,
        *,
        benchmark_price: float,
        benchmark_month: str,
        transit_band_days: tuple[int, int],
        vessel_dwt: float,
        typical_speed_knots: float = 14.0,
        history_prices: list[float],
        history_counterparties: int = 4,
        network_shared_escalated: int = 0,
        contract_found: bool = False,
        contract_claim: str = "long_term_offtake",
        contract_clause: str = "",
        description_drift: str | None = None,
        insurance_lag_days: int | None = None,
    ) -> None:
        self.benchmark_price = benchmark_price
        self.benchmark_month = benchmark_month
        self.transit_band_days = transit_band_days
        self.vessel_dwt = vessel_dwt
        self.typical_speed_knots = typical_speed_knots
        self.history_prices = history_prices
        self.history_counterparties = history_counterparties
        self.network_shared_escalated = network_shared_escalated
        self.contract_found = contract_found
        self.contract_claim = contract_claim
        self.contract_clause = contract_clause
        self.description_drift = description_drift
        self.insurance_lag_days = insurance_lag_days

    @property
    def exhaustive_cost(self) -> int:
        return sum(s.cost_units for s in TOOL_SPECS)


def _sev_from(value: float, medium: float, high: float) -> Severity:
    if value >= high:
        return Severity.high
    if value >= medium:
        return Severity.medium
    if value > 0:
        return Severity.low
    return Severity.none


class MiniToolRegistry:
    """Case-scoped registry: args never carry a case_id. call() never raises."""

    def __init__(self, case: AgentCaseView, world: MiniWorld) -> None:
        self.case = case
        self.world = world
        self._call_count = 0

    # ------------------------------------------------------------------ specs
    def specs(self) -> list[ToolSpec]:
        return list(TOOL_SPECS)

    # ------------------------------------------------------------------- call
    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        self._call_count += 1
        call_id = f"{self.case.case_id}-c{self._call_count}"
        handler = {
            "read_document": self._read_document,
            "check_document_consistency": self._consistency,
            "check_price_benchmark": self._price,
            "check_vessel_capacity": self._capacity,
            "check_transit_plausibility": self._transit,
            "check_historical_trade": self._history,
            "check_counterparty_network": self._network,
            "check_contract_or_supporting_evidence": self._contract,
        }.get(name)
        if handler is None:
            return ToolResult(
                tool=name, call_id=call_id, args=args, ok=False,
                summary=f"Unknown tool '{name}'", observations=[], raw={}, sources=[],
                cost_units=0, latency_ms=1, error=f"unknown tool '{name}'",
            )
        try:
            return handler(call_id, dict(args))
        except Exception as exc:  # contract: call never raises
            return ToolResult(
                tool=name, call_id=call_id, args=args, ok=False,
                summary=f"Tool failed: {exc}", observations=[], raw={}, sources=[],
                cost_units=0, latency_ms=1, error=str(exc),
            )

    # ----------------------------------------------------------------- tools
    def _finish(self, call_id: str, args: dict, spec_name: str, obs: list[Observation],
                ok: bool = True, error: str | None = None, raw: dict | None = None) -> ToolResult:
        r = self.case.record
        summary = obs[0].statement if obs else ("failed: " + str(error) if error else "no observations")
        return ToolResult(
            tool=spec_name, call_id=call_id, args=args, ok=ok,
            summary=summary[:200], observations=obs,
            raw=raw or {}, sources=[s for o in obs for s in o.sources],
            cost_units=_SPEC_BY_NAME[spec_name].cost_units, latency_ms=12, error=error,
        )

    def _read_document(self, call_id: str, args: dict) -> ToolResult:
        want_type = args.get("doc_type")
        want_id = args.get("doc_id")
        doc = next((d for d in self.case.documents
                    if (want_id and d.doc_id == want_id) or (want_type and d.doc_type.value == want_type)),
                   self.case.documents[0] if self.case.documents else None)
        if doc is None:
            return self._finish(call_id, args, "read_document", [], ok=False, error="no such document")
        obs = [
            Observation(
                observation_id=f"{call_id}-o1", dimension=Dimension.documentary,
                statement=f"{doc.doc_id} ({doc.doc_type.value}) issued {doc.issue_date} by {doc.issuer}; "
                          f"key fields: {doc.fields}",
                severity=Severity.none, metrics={},
                sources=_refs(doc.doc_id, "issue_date"),
            )
        ]
        return self._finish(call_id, args, "read_document", obs, raw={"fields": doc.fields, "raw_text": doc.raw_text[:800]})

    def _consistency(self, call_id: str, args: dict) -> ToolResult:
        r = self.case.record
        obs: list[Observation] = []
        inv = next((d for d in self.case.documents if d.doc_type.value == "commercial_invoice"), None)
        pl = next((d for d in self.case.documents if d.doc_type.value == "packing_list"), None)
        if self.world.description_drift and inv and pl:
            obs.append(Observation(
                observation_id=f"{call_id}-o1", dimension=Dimension.documentary,
                statement=f"Description drift: the packing list says '{self.world.description_drift}' "
                          f"while the invoice says '{r.commodity}'.",
                severity=Severity.medium, metrics={"drift_fields": 1.0},
                sources=_refs(pl.doc_id, "description") + _refs(inv.doc_id, "commodity"),
            ))
        if self.world.insurance_lag_days is not None and r.ship_date and r.insurance_issue_date:
            obs.append(Observation(
                observation_id=f"{call_id}-o{len(obs) + 1}", dimension=Dimension.documentary,
                statement=f"Insurance certificate was issued {self.world.insurance_lag_days} days AFTER "
                          f"the shipment date ({r.insurance_issue_date} vs {r.ship_date}).",
                severity=Severity.high if self.world.insurance_lag_days > 3 else Severity.medium,
                metrics={"insurance_lag_days": float(self.world.insurance_lag_days)},
                expected_range="insurance must predate or match shipment",
                sources=_refs("INS-" + r.lc_number, "insurance_issue_date") + _refs("BL-" + r.bl_number, "ship_date")
                if r.lc_number and r.bl_number else [],
            ))
        if not obs:
            obs.append(Observation(
                observation_id=f"{call_id}-o1", dimension=Dimension.documentary,
                statement="All shared fields agree across the document set; no description drift, "
                          "quantity mismatch or date-order violation found.",
                severity=Severity.none, metrics={"drift_fields": 0.0},
                sources=_refs(inv.doc_id if inv else self.case.documents[0].doc_id, "commodity"),
            ))
        return self._finish(call_id, args, "check_document_consistency", obs)

    def _price(self, call_id: str, args: dict) -> ToolResult:
        r = self.case.record
        declared = float(args.get("declared_unit_price") or r.unit_price)
        benchmark = self.world.benchmark_price
        dev_pct = (declared - benchmark) / benchmark * 100.0
        sev = _sev_from(abs(dev_pct), 5.0, 20.0) if abs(dev_pct) > 5 else (Severity.low if abs(dev_pct) > 0 else Severity.none)
        obs = [
            Observation(
                observation_id=f"{call_id}-o1", dimension=Dimension.economic,
                statement=f"Declared unit price is {dev_pct:+.1f}% versus the {self.world.benchmark_month} "
                          f"benchmark of {benchmark:.0f} {r.currency}/{r.unit} "
                          f"(declared {declared:.0f}).",
                severity=sev,
                metrics={"deviation_pct": round(dev_pct, 2), "benchmark_price": benchmark,
                         "declared_price": declared},
                expected_range="benchmark ±5%",
                sources=_refs("INV-" + (r.lc_number or "X"), "unit_price")
                + [_ref_db("benchmarks", r.commodity.replace(" ", "_").lower(), self.world.benchmark_month)],
            )
        ]
        return self._finish(call_id, args, "check_price_benchmark", obs,
                            raw={"benchmark": benchmark, "deviation_pct": dev_pct})

    def _capacity(self, call_id: str, args: dict) -> ToolResult:
        r = self.case.record
        claimed = float(args.get("claimed_weight_tons") or r.gross_weight_tons or r.quantity)
        dwt = self.world.vessel_dwt
        util = claimed / dwt
        sev = Severity.high if util > 1.0 else (Severity.medium if util > 0.95 else Severity.none)
        excess = max(0.0, claimed - dwt)
        obs = [
            Observation(
                observation_id=f"{call_id}-o1", dimension=Dimension.physical,
                statement=f"Claimed load of {claimed:.0f} t on {r.vessel_name} (registered capacity "
                          f"{dwt:.0f} t) is {util * 100:.0f}% utilisation"
                + (f", exceeding capacity by {excess:.0f} t." if excess > 0 else ", within capacity."),
                severity=sev,
                metrics={"utilisation": round(util, 3), "dwt_tons": dwt, "claimed_tons": claimed,
                         "excess_tons": excess},
                expected_range="utilisation <= 100%",
                sources=_refs("BL-" + (r.bl_number or "X"), "gross_weight_tons")
                + [_ref_db("vessels", (r.vessel_name or "unknown").replace(" ", "_"))],
            )
        ]
        return self._finish(call_id, args, "check_vessel_capacity", obs, raw={"utilisation": util, "dwt": dwt})

    def _transit(self, call_id: str, args: dict) -> ToolResult:
        r = self.case.record
        origin = args.get("origin_port") or r.origin_port
        dest = args.get("destination_port") or r.destination_port
        ship = date.fromisoformat(str(args.get("ship_date") or r.ship_date))
        arrival = date.fromisoformat(str(args.get("arrival_date") or r.arrival_date))
        claimed_days = (arrival - ship).days
        lo, hi = self.world.transit_band_days
        if claimed_days < lo:
            sev = Severity.high if claimed_days < lo - 1 else Severity.medium
            verdict_txt = f"shorter than the feasible band of {lo}-{hi} days"
        elif claimed_days > hi:
            sev = Severity.high if claimed_days > hi + 1 else Severity.medium
            verdict_txt = f"longer than the feasible band of {lo}-{hi} days"
        else:
            sev = Severity.none
            verdict_txt = f"within the feasible band of {lo}-{hi} days"
        obs = [
            Observation(
                observation_id=f"{call_id}-o1", dimension=Dimension.temporal,
                statement=f"Claimed transit {origin}->{dest} is {claimed_days} day(s) ({ship} -> {arrival}), "
                          f"{verdict_txt} at the vessel's typical speed.",
                severity=sev,
                metrics={"claimed_days": float(claimed_days), "band_min": float(lo), "band_max": float(hi)},
                expected_range=f"{lo}-{hi} days",
                sources=_refs("BL-" + (r.bl_number or "X"), "ship_date")
                + _refs("BL-" + (r.bl_number or "X"), "arrival_date")
                + [_ref_db("ports", f"{origin}-{dest}")],
            )
        ]
        return self._finish(call_id, args, "check_transit_plausibility", obs,
                            raw={"claimed_days": claimed_days, "band": [lo, hi]})

    def _history(self, call_id: str, args: dict) -> ToolResult:
        r = self.case.record
        prices = self.world.history_prices
        median = sorted(prices)[len(prices) // 2]
        mean = sum(prices) / len(prices)
        var = sum((p - mean) ** 2 for p in prices) / max(len(prices) - 1, 1)
        std = max(var ** 0.5, 1.0)
        z = (r.unit_price - mean) / std
        sev = Severity.high if abs(z) > 2 else (Severity.medium if abs(z) > 1 else Severity.low)
        obs = [
            Observation(
                observation_id=f"{call_id}-o1", dimension=Dimension.behavioural,
                statement=f"Entity {r.exporter_id}: {len(prices)} prior trades of {r.commodity} priced "
                          f"{min(prices):.0f}-{max(prices):.0f} (median {median:.0f}); current declared "
                          f"price is z={z:+.1f} versus that history.",
                severity=sev,
                metrics={"zscore": round(z, 2), "median_price": median, "prior_trades": float(len(prices)),
                         "history_min": min(prices), "history_max": max(prices)},
                expected_range="|z| <= 1 vs own history",
                sources=[_ref_db("history", f"{r.exporter_id}/{r.commodity.replace(' ', '_').lower()}")],
            )
        ]
        return self._finish(call_id, args, "check_historical_trade", obs,
                            raw={"z": z, "prices": prices, "counterparties": self.world.history_counterparties})

    def _network(self, call_id: str, args: dict) -> ToolResult:
        r = self.case.record
        shared = self.world.network_shared_escalated
        sev = Severity.medium if shared >= 2 else (Severity.low if shared >= 1 else Severity.none)
        entity = args.get("entity_id") or r.broker_id or r.exporter_id
        obs = [
            Observation(
                observation_id=f"{call_id}-o1", dimension=Dimension.network,
                statement=f"Network lookup for {entity}: {shared} prior ESCALATED case(s) share this "
                          f"intermediary; {self.world.history_counterparties} counterparties in its cluster."
                + (" The intermediary recurs across previously flagged trades." if shared else ""),
                severity=sev,
                metrics={"shared_escalated_cases": float(shared)},
                sources=[_ref_db("networks", str(entity).replace(" ", "_"))],
            )
        ]
        return self._finish(call_id, args, "check_counterparty_network", obs,
                            raw={"shared_escalated": shared})

    def _contract(self, call_id: str, args: dict) -> ToolResult:
        claim = str(args.get("claim") or "bulk_discount")
        w = self.world
        if w.contract_found and claim == w.contract_claim:
            obs = [
                Observation(
                    observation_id=f"{call_id}-o1", dimension=Dimension.economic,
                    statement=f"A supporting agreement is on file: \"{w.contract_clause}\" — this "
                              f"supports the '{claim}' benign explanation for the price.",
                    severity=Severity.none, metrics={"supporting_clauses": 1.0},
                    sources=_refs("SC-" + (self.case.record.lc_number or "X"), "pricing_schedule"),
                )
            ]
            return self._finish(call_id, args, "check_contract_or_supporting_evidence", obs,
                                raw={"found": True, "claim": claim, "clause": w.contract_clause})
        obs = [
            Observation(
                observation_id=f"{call_id}-o1", dimension=Dimension.economic,
                statement=f"No document supporting the '{claim}' explanation was found in the case file "
                          f"(explicit not-found after searching all "
                          f"{len(self.case.documents)} documents).",
                severity=Severity.medium if self._price_anomaly() else Severity.low,
                metrics={"supporting_clauses": 0.0},
                sources=[SourceRef(kind=SourceKind.derived,
                                   ref=f"check_contract_or_supporting_evidence:not_found:{claim}",
                                   label="explicit not-found")],
            )
        ]
        return self._finish(call_id, args, "check_contract_or_supporting_evidence", obs,
                            raw={"found": False, "claim": claim})

    def _price_anomaly(self) -> bool:
        dev = abs((self.case.record.unit_price - self.world.benchmark_price) / self.world.benchmark_price * 100)
        return dev > 5.0
