"""Fixture loaders (Part 1 pushes real fixtures to main at T+3h).

Bootstrap shim: raises informative errors until real fixture files exist.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .investigation import ToolResult, ToolSpec
from .trade import AgentCaseView

FIXTURE_ROOT = Path(os.environ.get("INTERPRETEX_FIXTURES", "fixtures"))


class FixtureNotFound(LookupError):
    pass


def load_case(case_id: str) -> AgentCaseView:
    path = FIXTURE_ROOT / "cases" / f"{case_id}.json"
    if not path.exists():
        raise FixtureNotFound(f"No fixture at {path}; Part 1 owns packages/contracts fixtures.")
    return AgentCaseView.model_validate(json.loads(path.read_text()))


def load_tool_specs() -> list[ToolSpec]:
    path = FIXTURE_ROOT / "tool_specs.json"
    if not path.exists():
        raise FixtureNotFound(f"No fixture at {path}; Part 1 owns packages/contracts fixtures.")
    return [ToolSpec.model_validate(s) for s in json.loads(path.read_text())]


def load_tool_result(name: str) -> dict[str, Any]:
    path = FIXTURE_ROOT / "tool_results" / f"{name}.json"
    if not path.exists():
        raise FixtureNotFound(f"No fixture at {path}; Part 1 owns packages/contracts fixtures.")
    return json.loads(path.read_text())


class FixtureToolRegistry:
    """Replays canned tool results from Part 1's fixtures, case-scoped."""

    def __init__(self, case: AgentCaseView) -> None:
        self.case = case
        self._specs = load_tool_specs()

    def specs(self) -> list[ToolSpec]:
        return list(self._specs)

    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        payload = load_tool_result(name)
        return ToolResult.model_validate(payload)
