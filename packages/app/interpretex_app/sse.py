"""Server-Sent Events helpers. Plain frames, no extra library.

Frame format (normative):
    id: <seq>
    event: <type>
    data: <event as JSON>
    <blank line>
"""
from __future__ import annotations

from collections.abc import Generator

from interpretex_contracts import InvestigationEvent

SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse_frame(event: InvestigationEvent) -> str:
    return (
        f"id: {event.seq}\n"
        f"event: {event.type.value}\n"
        f"data: {event.model_dump_json()}\n\n"
    )


def keepalive() -> str:
    return ": keepalive\n\n"


def frame_iter(events: list[InvestigationEvent], after_seq: int | None = None) -> Generator[str, None, None]:
    for ev in events:
        if after_seq is not None and ev.seq <= after_seq:
            continue
        yield sse_frame(ev)
