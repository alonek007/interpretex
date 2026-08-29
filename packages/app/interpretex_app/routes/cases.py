"""Case endpoints: list, agent view (no label), document, judge reveal."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from interpretex_app.runs import REGISTRY
from wiring import get_world, WiringError

router = APIRouter()


@router.get("/api/cases")
async def list_cases():
    try:
        world = get_world()
    except WiringError as exc:
        raise HTTPException(status_code=503, detail={"detail": str(exc), "stage": "cases"})
    return [s.model_dump() for s in world.list_cases()]


@router.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    try:
        world = get_world()
    except WiringError as exc:
        raise HTTPException(status_code=503, detail={"detail": str(exc), "stage": "cases"})
    try:
        case = world.load_case(case_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"detail": "case not found", "stage": "cases"})
    view = case.to_agent_view()
    payload = view.model_dump()
    assert "label" not in payload, "label must never be serialised to the agent/browser"
    return payload


@router.get("/api/cases/{case_id}/documents/{doc_id}")
async def get_document(case_id: str, doc_id: str):
    try:
        world = get_world()
    except WiringError as exc:
        raise HTTPException(status_code=503, detail={"detail": str(exc), "stage": "documents"})
    try:
        case = world.load_case(case_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"detail": "case not found", "stage": "documents"})
    for d in case.documents:
        if d.doc_id == doc_id:
            return d.model_dump()
    raise HTTPException(status_code=404, detail={"detail": "document not found", "stage": "documents"})


@router.get("/api/cases/{case_id}/label")
async def get_label(case_id: str):
    # Judge-only: 409 until a completed run for this case exists.
    if not REGISTRY.case_has_completed_run(case_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "label locked until a completed run exists for this case", "stage": "label"},
        )
    try:
        world = get_world()
    except WiringError as exc:
        raise HTTPException(status_code=503, detail={"detail": str(exc), "stage": "label"})
    try:
        case = world.load_case(case_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"detail": "case not found", "stage": "label"})
    if case.label is None:
        raise HTTPException(status_code=404, detail={"detail": "no label for case", "stage": "label"})
    return case.label.model_dump()
