"""In-memory run registry: one entry per POST /api/runs.

A dict is the right implementation; no database. Every event yielded on the
stream is appended here, so /runs/{id}, /report.md and Last-Event-ID resume
all read from this single source of truth.
"""
from __future__ import annotations

import itertools
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from interpretex_contracts import InvestigationEvent, InvestigationResult


@dataclass
class RunRecord:
    run_id: str
    case_id: str
    budget: int
    mode: str  # live | replay
    seed: int | None
    status: str = "pending"  # pending | streaming | done | failed
    events: list[InvestigationEvent] = field(default_factory=list)
    result: InvestigationResult | None = None
    error: dict[str, Any] | None = None
    terminal: bool = False
    driving: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, event: InvestigationEvent) -> None:
        self.events.append(event)
        if event.type in {"report_ready", "run_failed"}:
            self.terminal = True
            self.status = "done" if event.type == "report_ready" else "failed"
            if event.type == "run_failed":
                self.error = {
                    "error": event.payload.get("error", "unknown error"),
                    "stage": event.payload.get("stage", "unknown"),
                }
            else:
                result = event.payload.get("result")
                if isinstance(result, dict):
                    self.result = InvestigationResult.model_validate(result)


class RunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._seq = itertools.count(1)

    def create(self, case_id: str, budget: int, mode: str, seed: int | None) -> RunRecord:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        rec = RunRecord(run_id=run_id, case_id=case_id, budget=budget, mode=mode, seed=seed)
        self._runs[run_id] = rec
        return rec

    def get(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    def all(self) -> list[RunRecord]:
        return list(self._runs.values())

    def case_has_completed_run(self, case_id: str) -> bool:
        return any(r.case_id == case_id and r.status == "done" for r in self._runs.values())

    def completed_run_for_case(self, case_id: str) -> RunRecord | None:
        for r in self._runs.values():
            if r.case_id == case_id and r.status == "done" and r.result is not None:
                return r
        return None


REGISTRY = RunRegistry()
