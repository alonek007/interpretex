"""Interpretex integration layer (Part 3, lives on main).

Reads two environment variables and returns either the stub implementations
or the real Part 1 / Part 2 modules. Integration is a config flip, never a
refactor:

    INTERPRETEX_WORLD=stub|real
    INTERPRETEX_AGENT=stub|real

No route handler imports `world` or `agent` directly — only this file does.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from interpretex_contracts import Investigator, LLMClient, WorldAPI

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WORLD_MODE = os.environ.get("INTERPRETEX_WORLD", "stub").strip().lower()
AGENT_MODE = os.environ.get("INTERPRETEX_AGENT", "stub").strip().lower()

# Stub implementations are stateful (e.g. attacker-generated cases live in the
# world's in-memory registry), so a single instance must be shared across every
# request. The real modules are already singletons (imported once).
_WORLD: WorldAPI | None = None
_AGENT: Investigator | None = None


class WiringError(RuntimeError):
    """Raised when a real implementation is requested but not importable."""


def get_llm() -> LLMClient | None:
    from interpretex_contracts import client_from_env

    return client_from_env()


def get_world() -> WorldAPI:
    global _WORLD
    if WORLD_MODE == "real":
        try:
            module = importlib.import_module("world.api")
        except ImportError as exc:  # pragma: no cover - part 1 not landed
            raise WiringError(
                "INTERPRETEX_WORLD=real but packages/world is not installed. "
                "pip install -e packages/world or set INTERPRETEX_WORLD=stub."
            ) from exc
        return module  # type: ignore[return-value]
    if _WORLD is None:
        from stubs.fake_world import FakeWorld

        _WORLD = FakeWorld()
    return _WORLD


def get_agent() -> Investigator:
    global _AGENT
    if AGENT_MODE == "real":
        try:
            module = importlib.import_module("agent.api")
        except ImportError as exc:  # pragma: no cover - part 2 not landed
            raise WiringError(
                "INTERPRETEX_AGENT=real but packages/agent is not installed. "
                "pip install -e packages/agent or set INTERPRETEX_AGENT=stub."
            ) from exc
        return module  # type: ignore[return-value]
    if _AGENT is None:
        from stubs.fake_agent import FakeAgent

        _AGENT = FakeAgent()
    return _AGENT


def status() -> dict:
    return {"world": WORLD_MODE, "agent": AGENT_MODE}
