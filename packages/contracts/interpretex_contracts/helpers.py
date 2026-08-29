"""Shared helpers: SeqEmitter, run ids, canonical JSON (section 8.7)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .enums import EventType
from .investigation import InvestigationEvent


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json(obj: Any) -> str:
    """Stable serialisation — used for repeat-call detection and cache keys."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


class SeqEmitter:
    """Gapless event sequencer: seq starts at 0, increments by exactly 1."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.seq = -1

    def emit(self, type: EventType | str, narration: str, payload: dict[str, Any] | None = None) -> InvestigationEvent:
        self.seq += 1
        return InvestigationEvent(
            seq=self.seq,
            ts=utcnow(),
            run_id=self.run_id,
            type=EventType(type),
            narration=narration,
            payload=payload or {},
        )

    @property
    def next_seq(self) -> int:
        return self.seq + 1
