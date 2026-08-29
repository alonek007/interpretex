"""Fixture loading helpers for the golden fixtures bundled in this package."""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


def fixtures_root() -> "resources.Traversable":
    return resources.files("interpretex_contracts").joinpath("fixtures")


def load_json(rel: str) -> Any:
    data = fixtures_root().joinpath(rel).read_text(encoding="utf-8")
    return json.loads(data)


@lru_cache(maxsize=64)
def load_json_cached(rel: str) -> Any:
    return load_json(rel)


def load_jsonl(rel: str) -> list[dict]:
    data = fixtures_root().joinpath(rel).read_text(encoding="utf-8")
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def list_dir(rel: str) -> list[str]:
    d = fixtures_root().joinpath(rel)
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_file())


def clear_cache() -> None:
    load_json_cached.cache_clear()
