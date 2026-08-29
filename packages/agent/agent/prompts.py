"""Loader for the agent_prompts/*.md templates.

Search order: INTERPRETEX_PROMPTS env var, then an upward directory walk from
this file looking for agent_prompts/<name>.md. Callers format the returned
template with str.format.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

_HERE = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_template(name: str) -> str:
    env_dir = os.environ.get("INTERPRETEX_PROMPTS")
    if env_dir:
        path = Path(env_dir) / f"{name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    for parent in [_HERE, *_HERE.parents]:
        path = parent / "agent_prompts" / f"{name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"Prompt template '{name}.md' not found; set INTERPRETEX_PROMPTS to the agent_prompts directory."
    )
