"""Environment, feature flags and paths for the app."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from interpretex_contracts import CONTRACT_VERSION

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _flag(name: str, default: str = "1") -> bool:
    return _env(name, default).strip().lower() in {"1", "true", "yes", "on"}


WORLD_MODE = _env("INTERPRETEX_WORLD", "stub").strip().lower()
AGENT_MODE = _env("INTERPRETEX_AGENT", "stub").strip().lower()
LLM_MODEL = _env("LLM_MODEL", "stub-replay")
AGENT_BUDGET_DEFAULT = int(_env("AGENT_BUDGET_DEFAULT", "6"))
FAKE_AGENT_DELAY_MS = int(_env("FAKE_AGENT_DELAY_MS", "550"))

FLAGS: dict[str, bool] = {
    "budget": _flag("FEATURE_BUDGET"),
    "attacker": _flag("FEATURE_ATTACKER"),
    "network": _flag("FEATURE_NETWORK"),
    "history": _flag("FEATURE_HISTORY"),
    "replay": _flag("FEATURE_REPLAY"),
}

STUB_CASES_DIR = Path(_env("STUB_CASES_DIR", REPO_ROOT / "stubs" / "cases"))
STUB_TRACES_DIR = Path(_env("STUB_TRACES_DIR", REPO_ROOT / "stubs" / "fixtures"))
RECORDED_RUNS_DIR = Path(_env("RECORDED_RUNS_DIR", REPO_ROOT / "runs"))


def as_health_dict() -> dict:
    return {
        "status": "ok",
        "contract_version": CONTRACT_VERSION,
        "model": LLM_MODEL,
        "flags": FLAGS,
        "world": WORLD_MODE,
        "agent": AGENT_MODE,
    }
