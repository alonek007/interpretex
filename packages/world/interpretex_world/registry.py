"""Per-case tool registry.

Wraps a :class:`TradeCase` and the :class:`ReferenceWorld` and exposes a
callable interface for the eight investigation tools. Arguments may be
supplied partially; any missing argument is resolved from the case record.
:method:`call` never raises: failures are returned as ``ok=False`` tool
results, and observations are assigned stable ids *after* the call returns, so
an exception cannot leave a tool result without ids.
"""

from __future__ import annotations

from typing import Any, Optional

from interpretex_contracts import (
    Dimension, Severity, ToolResult, ToolSpec, TradeCase,
)
from interpretex_contracts.helpers import IdCounter, SeqEmitter

from .reference import ReferenceWorld
from . import tools as tool_modules
from .tools.base import ToolOutcome

_CALL_ID = IdCounter("CALL")

DEFAULT_MODULES = [
    tool_modules.read_document,
    tool_modules.check_document_consistency,
    tool_modules.check_price_benchmark,
    tool_modules.check_vessel_capacity,
    tool_modules.check_transit_plausibility,
    tool_modules.check_historical_trade,
    tool_modules.check_counterparty_network,
    tool_modules.check_contract_or_supporting_evidence,
]


class CaseToolRegistry:
    """A registry bound to a single trade case."""

    def __init__(self, case: TradeCase, world: Optional[ReferenceWorld] = None):
        self.case = case
        self.world = world or ReferenceWorld.default()
        self._outcomes: dict[str, ToolOutcome] = {}
        self._specs: dict[str, ToolSpec] = {}
        for mod in DEFAULT_MODULES:
            spec = getattr(mod, "SPEC", None)
            if spec is not None:
                self._specs[spec.name] = spec
        self._all_specs = [m.SPEC for m in DEFAULT_MODULES if getattr(m, "SPEC", None)]

    # ---- case accessors used by tools ----
    @property
    def record(self):
        return self.case.record

    @property
    def documents(self):
        return self.case.documents

    def doc_by_id(self, doc_id: str):
        for d in self.documents:
            if d.doc_id == doc_id:
                return d
        return None

    def doc_by_type(self, doc_type):
        from interpretex_contracts import DocType
        if isinstance(doc_type, DocType):
            dt = doc_type
        else:
            dt = DocType(doc_type)
        for d in self.documents:
            if d.doc_type is dt:
                return d
        return None

    def doc_ref_for(self, field: str) -> str:
        for d in self.documents:
            if field in d.fields:
                return d.doc_id
        return self.documents[0].doc_id if self.documents else "case_file"

    # ---- registry interface ----
    def names(self) -> list[str]:
        from interpretex_contracts import DEFAULT_TOOL_NAMES
        ordered = [n for n in DEFAULT_TOOL_NAMES if n in self._specs]
        extra = [n for n in self._specs if n not in ordered]
        return ordered + extra

    def specs(self, data_class: Optional[str] = None) -> list[ToolSpec]:
        return [self._specs[n] for n in self.names()]

    def call(self, name: str, args: Optional[dict] = None) -> ToolResult:
        mod = {m.SPEC.name: m for m in DEFAULT_MODULES if getattr(m, "SPEC", None)}.get(name)
        args = dict(args or {})
        latency_ms = 0.0
        cost_units = 1
        emitter = SeqEmitter()

        if mod is None:
            outcome = ToolOutcome(ok=False, error=f"unknown tool {name!r}")
        else:
            cost_units = mod.SPEC.cost_units
            latency_ms = 10.0 + 2.0 * cost_units
            try:
                outcome = mod.run(self, args)
            except Exception as exc:  # never leak exceptions into the api surface
                outcome = ToolOutcome(ok=False, error=f"{type(exc).__name__}: {exc}")

        # assign observation ids now that we know the call succeeded
        call_id = _CALL_ID()
        obs = []
        for i, o in enumerate(outcome.observations, start=1):
            o.observation_id = f"OBS-{call_id}-{i:02d}"
            obs.append(o)

        return ToolResult(
            tool=name,
            call_id=call_id,
            args=args,
            ok=outcome.ok,
            summary=outcome.summary,
            observations=obs,
            raw=outcome.raw,
            sources=outcome.sources,
            error=outcome.error,
            latency_ms=int(round(latency_ms)),
            cost_units=cost_units,
        )


def build_tool_registry(case: TradeCase,
                        world: Optional[ReferenceWorld] = None) -> CaseToolRegistry:
    return CaseToolRegistry(case, world)
