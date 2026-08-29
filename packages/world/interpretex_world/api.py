"""Part 1 public surface (:class:`WorldAPI`).

A single :class:`World` object implements every method Part 2 and Part 3 call.
It owns the reference world, the deterministic demo/attacker cases, and the
per-case tool registry. Nothing here raises for a known case id; unknown ids
raise ``KeyError`` (callers decide how to surface that).
"""

from __future__ import annotations

from typing import Optional

from interpretex_contracts import (
    AttackSpec, CaseSpec, CaseSummary, NetworkView, TradeCase,
)
from interpretex_contracts.helpers import Flags

from . import demo
from .attacker import attack as _attack
from .generator import generate_case as _generate_case
from .network import network_view as _network_view
from .reference import ReferenceWorld
from .registry import CaseToolRegistry, build_tool_registry


class World:
    """The configured world: reference data + deterministic demo cases."""

    def __init__(self, world: Optional[ReferenceWorld] = None) -> None:
        self._world = world or ReferenceWorld.default()
        self._cache: dict[str, TradeCase] = {}
        self._current: Optional[TradeCase] = None

    # -- cases --------------------------------------------------------------
    def list_cases(self) -> list[CaseSummary]:
        out = []
        for case in self._demo_and_attacker():
            out.append(self._summary(case))
        return out

    def load_case(self, case_id: str) -> TradeCase:
        case = self._get(case_id)
        self._current = case
        return case

    def generate_case(self, spec: CaseSpec) -> TradeCase:
        case = _generate_case(spec)
        self._current = case
        return case

    # -- tools / network ----------------------------------------------------
    def build_tool_registry(self, case: TradeCase) -> CaseToolRegistry:
        return CaseToolRegistry(case, self._world)

    def network_view(self, entity_id: Optional[str] = None,
                     depth: int = 2) -> NetworkView:
        case = self._current
        focus = entity_id or (case.record.importer_id if case else entity_id)
        if case is None or focus is None:
            return NetworkView(focus_entity_id=focus, nodes=[], edges=[], findings=[])
        return _network_view(case, self._world, focus_entity_id=focus, depth=depth)

    def attack(self, spec: Optional[AttackSpec] = None, llm=None) -> TradeCase:
        case = _attack(spec, llm)
        self._current = case
        return case

    # -- helpers ------------------------------------------------------------
    def _demo_and_attacker(self) -> list[TradeCase]:
        return [*demo.build_demo_cases(), demo.build_attacker_fallback()]

    def _get(self, case_id: str) -> TradeCase:
        if case_id not in self._cache:
            for case in self._demo_and_attacker():
                self._cache[case.case_id] = case
        if case_id not in self._cache:
            raise KeyError(case_id)
        return self._cache[case_id]

    def _summary(self, case: TradeCase) -> CaseSummary:
        rec = case.record
        comm = self._world.find_commodity(rec.commodity)
        exp = self._world.entity(rec.exporter_id)
        imp = self._world.entity(rec.importer_id)
        return CaseSummary(
            case_id=case.case_id,
            title=case.title or case.case_id,
            commodity=comm.display_name if comm else rec.commodity,
            quantity=float(rec.quantity),
            unit=comm.unit if comm else (rec.unit or ""),
            total_value=round(float(rec.total_value), 2),
            currency=comm.currency if comm else "USD",
            exporter_name=exp["name"] if exp else (rec.exporter_id or ""),
            importer_name=imp["name"] if imp else (rec.importer_id or ""),
            origin_port=rec.origin_port,
            destination_port=rec.destination_port,
            document_count=len(case.documents),
            received_at=case.received_at,
            is_adversarial=(case.label.case_class.value == "adversarial"
                            if case.label else False),
        )


# ---- module-level convenience (the documented entry points) ----

_DEFAULT_WORLD: Optional[World] = None


def _default() -> World:
    global _DEFAULT_WORLD
    if _DEFAULT_WORLD is None:
        _DEFAULT_WORLD = World()
    return _DEFAULT_WORLD


def list_cases() -> list[CaseSummary]:
    return _default().list_cases()


def load_case(case_id: str) -> TradeCase:
    return _default().load_case(case_id)


def generate_case(spec: CaseSpec) -> TradeCase:
    return _default().generate_case(spec)


def build_tool_registry(case: TradeCase) -> CaseToolRegistry:
    return _default().build_tool_registry(case)


def network_view(entity_id: Optional[str] = None, depth: int = 2) -> NetworkView:
    return _default().network_view(entity_id, depth)


def attack(spec: Optional[AttackSpec] = None, llm=None) -> TradeCase:
    return _default().attack(spec, llm)
