"""Network + attack endpoints.

`GET /api/network` returns the synthetic counterparty network (guarded by
FEATURE_NETWORK). `POST /api/attack` asks the world to synthesise an evasive
case that sits inside every individual threshold and must be caught by
correlation; it returns a runnable case_id (guarded by FEATURE_ATTACKER).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from interpretex_app import config
from wiring import WiringError, get_world

router = APIRouter()


class AttackRequest(BaseModel):
    max_dimensions: int = 2
    target_stealth: float = 0.8
    seed: int = 0


@router.get("/api/network")
async def network(entity_id: str | None = Query(default=None), depth: int = Query(default=2)):
    if not config.FLAGS.get("network", True):
        raise HTTPException(status_code=404, detail={"detail": "network feature disabled", "stage": "network"})
    try:
        world = get_world()
    except WiringError as exc:
        raise HTTPException(status_code=503, detail={"detail": str(exc), "stage": "network"})
    view = world.network_view(entity_id=entity_id, depth=depth)
    return view.model_dump()


@router.post("/api/attack")
async def attack(body: AttackRequest):
    if not config.FLAGS.get("attacker", True):
        raise HTTPException(status_code=404, detail={"detail": "attacker feature disabled", "stage": "attack"})
    try:
        world = get_world()
    except WiringError as exc:
        raise HTTPException(status_code=503, detail={"detail": str(exc), "stage": "attack"})
    try:
        from interpretex_contracts import AttackSpec

        spec = AttackSpec(
            max_dimensions=body.max_dimensions,
            target_stealth=body.target_stealth,
            seed=body.seed,
        )
        case = world.attack(spec, llm=None)
    except Exception as exc:  # noqa: BLE001 - surface as 500 with JSON body
        raise HTTPException(
            status_code=500,
            detail={"detail": f"attack failed: {exc}", "stage": "attack"},
        )
    return {"case_id": case.case_id}
