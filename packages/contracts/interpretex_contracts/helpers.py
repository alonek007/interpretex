"""Small shared helpers: ids, clock, event sequencing, SSE framing, flags.

Everything here is dependency-free and safe to import from any part.
"""

import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from .enums import EventType
from .investigation import InvestigationEvent

#: The three caveats carried on every Decision, every run, without exception.
STANDARD_CAVEATS: list[str] = [
    "Reference data is synthetic and scoped to this prototype; it is not market, "
    "maritime or sanctions intelligence.",
    "The output is investigative decision support and not a regulatory determination; "
    "the human investigator decides.",
    "Anomalies may have legitimate commercial explanations that no available tool "
    "can observe.",
]


def utcnow() -> datetime:
    """Timezone-aware UTC now (the only clock helper; keeps ts formats uniform)."""
    return datetime.now(timezone.utc)


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


def stable_hash(*parts: Any) -> str:
    """Deterministic sha256 hex digest of arbitrarily typed parts."""
    blob = repr(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


class IdCounter:
    """Sequential id generator: ``IdCounter('TC')() -> 'TC-001'``."""

    def __init__(self, prefix: str, width: int = 3, start: int = 1) -> None:
        self._prefix = prefix
        self._width = width
        self._n = start - 1

    def __call__(self) -> str:
        self._n += 1
        return f"{self._prefix}-{self._n:0{self._width}d}"

    def peek_next(self) -> str:
        return f"{self._prefix}-{self._n + 1:0{self._width}d}"


class SeqEmitter:
    """Wraps an emit callback and guarantees gapless event ``seq``.

    ``SeqEmitter()`` collects into ``.events``; ``SeqEmitter(fn)`` forwards
    each stamped event to ``fn`` as well. ``seq`` starts at 0 and increments
    by exactly 1 with no gaps.
    """

    def __init__(self, emit: Callable[[InvestigationEvent], None] | None = None) -> None:
        self._emit = emit
        self._seq = -1
        self.events: list[InvestigationEvent] = []

    def emit(self, event: InvestigationEvent) -> InvestigationEvent:
        self._seq += 1
        stamped = event.model_copy(update={"seq": self._seq})
        self.events.append(stamped)
        if self._emit is not None:
            self._emit(stamped)
        return stamped

    def next_seq(self) -> int:
        return self._seq + 1


def sse_frame(event: InvestigationEvent) -> str:
    """Serialise one event as an SSE frame, exactly:

    ``id: <seq>\\nevent: <type value>\\ndata: <event.model_dump_json()>\\n\\n``

    ``id:`` carrying ``seq`` gives EventSource Last-Event-ID resume for free.
    """
    return (
        f"id: {event.seq}\n"
        f"event: {event.type.value}\n"
        f"data: {event.model_dump_json()}\n\n"
    )


def sse_stream(events: Iterator[InvestigationEvent]) -> Iterator[str]:
    """Map an event iterator onto SSE frames."""
    for event in events:
        yield sse_frame(event)


def _env_flag(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return 1 if raw.strip().lower() in {"1", "true", "yes", "on"} else 0


class Flags:
    """Feature-flag reader. Env vars win; defaults encode the shipped state.

    ``FEATURE_NETWORK`` / ``FEATURE_ATTACKER`` / ``FEATURE_HISTORICAL`` are
    Part 1's flags (defaults on). Unknown ``FEATURE_*`` vars are surfaced so
    Part 3 can render a flag panel without knowing the names.
    """

    DEFAULTS: dict[str, int] = {
        "FEATURE_NETWORK": 1,
        "FEATURE_ATTACKER": 1,
        "FEATURE_HISTORICAL": 1,
    }

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        env = dict(os.environ if environ is None else environ)
        self._values: dict[str, int] = {
            name: _env_flag(name, default) for name, default in self.DEFAULTS.items()
        }
        self.extras: dict[str, int] = {
            key: _env_flag(key, 0)
            for key in sorted(env)
            if key.startswith("FEATURE_") and key not in self.DEFAULTS
        }

    def enabled(self, name: str) -> bool:
        if name in self._values:
            return bool(self._values[name])
        return bool(self.extras.get(name, 0))

    def as_dict(self) -> dict[str, int]:
        out = dict(self._values)
        out.update(self.extras)
        return out

    def __contains__(self, name: str) -> bool:
        return self.enabled(name)


def event(run_id: str, type_: EventType, narration: str, payload: dict[str, Any] | None = None,
          ts: datetime | None = None) -> InvestigationEvent:
    """Convenience constructor used by Part 2 and by the scripted demo trace."""
    return InvestigationEvent(
        seq=0,  # stamped by SeqEmitter
        ts=ts or utcnow(),
        run_id=run_id,
        type=type_,
        narration=narration,
        payload=payload or {},
    )
