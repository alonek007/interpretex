"""Interpretex API — FastAPI app factory (Part 3).

Owns both sides of the HTTP boundary. Every route gets the world/agent through
wiring.get_world() / wiring.get_agent(); no route imports `world` or `agent`
directly. The starter logs CONTRACT_VERSION, the world/agent mode, the model
and the feature flags — the team's shared "is the stack alive" signal.
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv()

from interpretex_contracts import CONTRACT_VERSION  # noqa: E402
from wiring import get_agent, get_world  # noqa: E402
from interpretex_app import config  # noqa: E402
from interpretex_app.routes import cases, meta, network, runs  # noqa: E402

app = FastAPI(title="Interpretex API", version=CONTRACT_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    status = get_world() and get_agent()
    print(
        f"[interpretex] contract={CONTRACT_VERSION} world={config.WORLD_MODE} "
        f"agent={config.AGENT_MODE} model={config.LLM_MODEL} flags={config.FLAGS}"
    )


app.include_router(meta.router)
app.include_router(cases.router)
app.include_router(runs.router)
app.include_router(network.router)


@app.get("/api")
async def root():
    return {"service": "interpretex", "contract_version": CONTRACT_VERSION}
