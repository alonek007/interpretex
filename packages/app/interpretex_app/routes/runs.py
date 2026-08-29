"""Run endpoints: create a run, stream its events (SSE), fetch the result.

`POST /api/runs` returns immediately with a run id. The investigation is driven
by the SSE handler: every event is appended to the registry (the single source
of truth) and emitted as a frame. `Last-Event-ID` resume is supported — a
reconnect replays retained events after that id, then continues the live stream
without restarting the investigation.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from interpretex_app import config, report
from interpretex_app.runs import REGISTRY
from interpretex_app.sse import SSE_HEADERS, keepalive, sse_frame
from interpretex_contracts import InvestigationEvent
from wiring import WiringError, get_agent, get_llm, get_world

router = APIRouter()


class RunRequest(BaseModel):
    case_id: str
    budget: int | None = None
    mode: str = "live"  # live | replay
    seed: int | None = None


@router.post("/api/runs")
async def create_run(body: RunRequest):
    try:
        world = get_world()
    except WiringError as exc:
        raise HTTPException(status_code=503, detail={"detail": str(exc), "stage": "runs"})
    try:
        world.load_case(body.case_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"detail": "unknown case", "stage": "runs"})
    budget = body.budget if body.budget is not None else config.AGENT_BUDGET_DEFAULT
    rec = REGISTRY.create(body.case_id, budget, body.mode, body.seed)
    return {"run_id": rec.run_id}


def _parse_last_id(req: Request) -> int | None:
    raw = req.headers.get("Last-Event-ID")
    if raw is None:
        raw = req.query_params.get("last_id")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _stream(rec, last_id: int | None):
    world = get_world()
    agent = get_agent()
    seen = {e.seq for e in rec.events}

    # 1. Replay retained events after last_id (covers resume / reconnect).
    for ev in rec.events:
        if last_id is None or ev.seq > last_id:
            yield sse_frame(ev)
    if rec.terminal:
        return

    # 2. Claim the driver slot if free; otherwise poll for new events.
    became_driver = False
    with rec.lock:
        if not rec.driving:
            rec.driving = True
            became_driver = True

    if became_driver:
        try:
            rec.status = "streaming"
            case = world.load_case(rec.case_id)
            tools = world.build_tool_registry(case)
            for event in agent.investigate_stream(
                case.to_agent_view(), tools, llm=get_llm(), budget=rec.budget, seed=rec.seed
            ):
                if event.seq in seen:
                    continue
                seen.add(event.seq)
                with rec.lock:
                    rec.append(event)
                yield sse_frame(event)
                if rec.terminal:
                    break
        except Exception as exc:  # pragma: no cover - defensive
            failed = InvestigationEvent(
                seq=len(rec.events), run_id=rec.run_id, type="run_failed",
                narration=f"Stream error: {exc}",
                payload={"error": str(exc), "stage": "stream", "degraded": True},
            )
            with rec.lock:
                rec.append(failed)
            yield sse_frame(failed)
        finally:
            with rec.lock:
                rec.driving = False
        return

    # 3. Late joiner: poll the registry until terminal, emitting new events.
    last_sent = last_id if last_id is not None else -1
    last_yield = time.time()
    while True:
        fresh = [e for e in rec.events if e.seq > last_sent]
        for ev in fresh:
            yield sse_frame(ev)
            last_sent = ev.seq
        if fresh:
            last_yield = time.time()
        if rec.terminal:
            break
        if time.time() - last_yield > 15:
            yield keepalive()
            last_yield = time.time()
        time.sleep(0.2)


@router.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, req: Request):
    rec = REGISTRY.get(run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail={"detail": "unknown run", "stage": "runs"})
    last_id = _parse_last_id(req)
    return StreamingResponse(_stream(rec, last_id), headers=SSE_HEADERS, media_type="text/event-stream")


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    rec = REGISTRY.get(run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail={"detail": "unknown run", "stage": "runs"})
    if not rec.terminal or rec.result is None:
        raise HTTPException(status_code=404, detail={"detail": "run not complete", "stage": "runs"})
    return rec.result.model_dump()


@router.get("/api/runs/{run_id}/report.md")
async def get_report(run_id: str):
    rec = REGISTRY.get(run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail={"detail": "unknown run", "stage": "runs"})
    if rec.result is None:
        raise HTTPException(status_code=404, detail={"detail": "run not complete", "stage": "runs"})
    return PlainTextResponse(
        rec.result.report_markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.report.md"'},
    )


@router.get("/api/runs/{run_id}/baseline")
async def get_baseline(run_id: str):
    rec = REGISTRY.get(run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail={"detail": "unknown run", "stage": "runs"})
    if rec.result is None:
        raise HTTPException(status_code=404, detail={"detail": "run not complete", "stage": "runs"})
    return report.baseline_for(rec.result)
