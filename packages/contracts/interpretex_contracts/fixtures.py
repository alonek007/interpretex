"""Fixture loaders + FixtureToolRegistry.

Golden fixtures ship inside the package (``interpretex_contracts/fixtures/``)
so Parts 2 and 3 can build and render against real-shaped data before Part 1's
world exists. Layout::

    fixtures/
      cases/case_*.json                 full TradeCase incl. label
      tool_specs.json                   all 8 ToolSpec objects
      tool_results/case_*.json          { "<tool_name>": <ToolResult>, ... }
      runs/case_*.events.jsonl          one InvestigationEvent per line
      runs/case_*.result.json           one full InvestigationResult

A fixture that does not validate is worse than no fixture: the CI-style test
in tests/contracts asserts every file parses through its pydantic model.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .investigation import (
    InvestigationEvent,
    InvestigationResult,
    ToolResult,
    ToolSpec,
)
from .trade import TradeCase

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class FixtureError(RuntimeError):
    """Raised when a fixture is missing or does not validate."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FixtureError(f"missing fixture: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FixtureError(f"invalid JSON in fixture: {path}: {exc}") from exc


# ------------------------------------------------------------------- cases ---


def list_case_fixture_ids() -> list[str]:
    cases_dir = FIXTURES_DIR / "cases"
    if not cases_dir.exists():
        return []
    return sorted(p.stem for p in cases_dir.glob("case_*.json"))


@lru_cache(maxsize=None)
def load_case_fixture(case_id: str) -> TradeCase:
    path = FIXTURES_DIR / "cases" / f"{case_id}.json"
    data = _load_json(path)
    try:
        return TradeCase.model_validate(data)
    except ValidationError as exc:
        raise FixtureError(f"fixture {path} failed TradeCase validation: {exc}") from exc


def load_case_fixture_raw(case_id: str) -> dict[str, Any]:
    return _load_json(FIXTURES_DIR / "cases" / f"{case_id}.json")


# -------------------------------------------------------------- tool specs ---


@lru_cache(maxsize=None)
def load_tool_specs() -> list[ToolSpec]:
    data = _load_json(FIXTURES_DIR / "tool_specs.json")
    specs = data.get("tools", data) if isinstance(data, dict) else data
    try:
        return [ToolSpec.model_validate(s) for s in specs]
    except ValidationError as exc:
        raise FixtureError(f"tool_specs.json failed validation: {exc}") from exc


# ------------------------------------------------------------- tool results --


def list_tool_result_case_ids() -> list[str]:
    d = FIXTURES_DIR / "tool_results"
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("case_*.json"))


@lru_cache(maxsize=None)
def load_tool_results(case_id: str) -> dict[str, ToolResult]:
    path = FIXTURES_DIR / "tool_results" / f"{case_id}.json"
    data = _load_json(path)
    out: dict[str, ToolResult] = {}
    for name, raw in data.items():
        try:
            out[name] = ToolResult.model_validate(raw)
        except ValidationError as exc:
            raise FixtureError(
                f"tool result {name!r} in {path} failed validation: {exc}") from exc
    return out


# ------------------------------------------------------------------- runs ----


def list_run_case_ids() -> list[str]:
    d = FIXTURES_DIR / "runs"
    if not d.exists():
        return []
    return sorted({p.stem.split(".")[0] for p in d.glob("case_*.events.jsonl")})


@lru_cache(maxsize=None)
def load_events_fixture(case_id: str) -> list[InvestigationEvent]:
    path = FIXTURES_DIR / "runs" / f"{case_id}.events.jsonl"
    events: list[InvestigationEvent] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise FixtureError(f"missing fixture: {path}") from exc
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            events.append(InvestigationEvent.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise FixtureError(
                f"event line {i + 1} of {path} failed validation: {exc}") from exc
    return events


@lru_cache(maxsize=None)
def load_result_fixture(case_id: str) -> InvestigationResult:
    path = FIXTURES_DIR / "runs" / f"{case_id}.result.json"
    data = _load_json(path)
    try:
        return InvestigationResult.model_validate(data)
    except ValidationError as exc:
        raise FixtureError(f"fixture {path} failed validation: {exc}") from exc


# ------------------------------------------------- FixtureToolRegistry -------


class FixtureToolRegistry:
    """Satisfies the ToolRegistry protocol entirely from canned JSON.

    Construct per case: ``FixtureToolRegistry("case_suspicious_003")``. Used
    by Part 2 (loop development before the world exists) and Part 3 (UI
    before the agent exists). ``call()`` never raises, mirroring the real
    registry's contract; unknown tools return ``ok=False``.
    """

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self._specs = {s.name: s for s in load_tool_specs()}
        self._results = load_tool_results(case_id)
        self._seq = 0

    def specs(self) -> list[ToolSpec]:
        return list(load_tool_specs())

    def call(self, name: str, args: dict) -> ToolResult:
        self._seq += 1
        spec = self._specs.get(name)
        result = self._results.get(name)
        if result is None:
            return ToolResult(
                tool=name,
                call_id=f"FIX-{self._seq:03d}",
                args=dict(args or {}),
                ok=False,
                summary=f"no canned result for tool {name!r} on case {self.case_id!r}",
                observations=[],
                raw={"fixture_case": self.case_id},
                sources=[],
                cost_units=spec.cost_units if spec else 0,
                latency_ms=0,
                error="unknown tool or missing fixture result",
            )
        return result.model_copy(update={"call_id": f"FIX-{self._seq:03d}"})


__all__ = [
    "FIXTURES_DIR", "FixtureError",
    "list_case_fixture_ids", "load_case_fixture", "load_case_fixture_raw",
    "load_tool_specs", "list_tool_result_case_ids", "load_tool_results",
    "list_run_case_ids", "load_events_fixture", "load_result_fixture",
    "FixtureToolRegistry",
]
