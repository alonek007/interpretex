"""Meta endpoints: /api/health, /api/flags, /api/tools."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from interpretex_app import config
from interpretex_app.runs import REGISTRY
from wiring import get_world, WiringError

router = APIRouter()


@router.get("/api/health")
async def health():
    try:
        get_world()
    except WiringError:
        raise HTTPException(status_code=503, detail={"detail": "world unavailable", "stage": "startup"})
    return config.as_health_dict()


@router.get("/api/flags")
async def flags():
    return config.FLAGS


@router.get("/api/tools")
async def tools():
    try:
        world = get_world()
    except WiringError as exc:
        raise HTTPException(status_code=503, detail={"detail": str(exc), "stage": "tools"})
    first = next((c.case_id for c in world.list_cases()), None)
    if first is None:
        return []
    case = world.load_case(first)
    return [s.model_dump() for s in world.build_tool_registry(case).specs()]
