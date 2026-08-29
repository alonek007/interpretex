"""Interpretex — Part 1: The World.

Synthetic reference world, document layer, eight investigation tools, the
adversary, and the public :class:`WorldAPI` surface. Part 2 (agent) and Part 3
(app) import only the frozen ``interpretex_contracts`` package plus this
surface.
"""

from __future__ import annotations

from .api import (
    World,
    attack,
    build_tool_registry,
    generate_case,
    list_cases,
    load_case,
    network_view,
)
from .attacker import attack as _attack
from .generator import (
    build_case_from_blueprint,
    generate_case as generate_case_raw,
)
from .reference import ReferenceWorld
from .registry import CaseToolRegistry

__all__ = [
    "World",
    "ReferenceWorld",
    "CaseToolRegistry",
    "list_cases",
    "load_case",
    "generate_case",
    "build_tool_registry",
    "network_view",
    "attack",
]
