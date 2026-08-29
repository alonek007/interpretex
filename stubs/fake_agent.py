"""FakeAgent (Part 3 stub for Part 2 investigator).

Replays a pre-recorded trace for a case from stubs/fixtures/<case_id>.events.jsonl
(with an optional per-event delay so the reasoning reads as live on stage), and
yields the final report_ready event whose payload carries the full result.

If a recorded run exists at runs/<case_id>.events.jsonl it is preferred (so a
real recording can be replayed). Missing case -> yields a run_failed frame.

The real Part 2 agent is swapped in by wiring.py (INTERPRETEX_AGENT=real);
nothing else in the app changes.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Iterator

from interpretex_contracts import AgentCaseView, InvestigationEvent, ToolRegistry
from interpretex_contracts.trade import TradeCase

from interpretex_app import config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "stubs" / "fixtures"
RECORDED = REPO_ROOT / "runs"


def _trace_path(case_id: str) -> Path | None:
    recorded = RECORDED / f"{case_id}.events.jsonl"
    if recorded.is_file():
        return recorded
    stub = FIXTURES / f"{case_id}.events.jsonl"
    return stub if stub.is_file() else None


def _rewrite(event: dict, run_id: str) -> InvestigationEvent:
    event["run_id"] = run_id
    return InvestigationEvent.model_validate(event)


class FakeAgent:
    def investigate_stream(self, case: AgentCaseView, tools: ToolRegistry, *,
                            llm: Any = None, budget: int = 6,
                            seed: int | None = None) -> Iterator[InvestigationEvent]:
        case_id = case.case_id
        run_id = f"run_stub_{case_id}"
        path = _trace_path(case_id)
        if path is None:
            yield InvestigationEvent(seq=0, run_id=run_id, type="run_failed",
                                    narration=f"No scripted trace for {case_id}.",
                                    payload={"error": f"no trace for {case_id}", "stage": "replay", "degraded": True})
            return
        delay = max(0, config.FAKE_AGENT_DELAY_MS) / 1000.0
        with path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                event = _rewrite(json.loads(raw), run_id)
                if delay:
                    time.sleep(delay)
                yield event
