"""Architectural guard: the agent package must import ONLY the shared contracts
interface (interpretex_contracts) from outside itself, plus the standard library.
It must never reach into a Part 1 world/registry implementation or a Part 3
orchestrator — that coupling is exactly what the contract boundary forbids.
"""
from __future__ import annotations

import ast
import importlib
import pkgutil

# Modules the agent is allowed to depend on beyond the stdlib.
ALLOWED_PREFIXES = ("agent", "interpretex_contracts")


def _is_stdlib(name: str) -> bool:
    try:
        mod = importlib.import_module(name.split(".")[0])
    except Exception:
        return False
    return bool(getattr(mod, "__file__", "") and "site-packages" not in getattr(mod, "__file__", "") and "/lib/python" in getattr(mod, "__file__", ""))


def test_agent_only_imports_contracts():
    import agent

    bad = []
    for _, modname, _ in pkgutil.walk_packages(agent.__path__, prefix="agent."):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        for attr, val in vars(mod).items():
            if isinstance(val, type(agent)) or getattr(val, "__module__", None) is None:
                continue
            mod_of = getattr(val, "__module__", "")
            if not mod_of or mod_of == "builtins":
                continue
            top = mod_of.split(".")[0]
            if top in ALLOWED_PREFIXES or _is_stdlib(top):
                continue
            bad.append(f"{modname}: {attr} -> {mod_of}")
    assert not bad, "agent must not import non-contract, non-stdlib modules:\n" + "\n".join(bad)


def test_contracts_package_is_the_only_external_dep():
    """A static check that no agent source file imports a forbidden module by name."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "packages" / "agent" / "agent"
    forbidden = {"world", "part1", "interpretex_world", "solidity", "orchestrator", "web"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    assert not any(f in n.name.split(".")[0] for f in forbidden), (
                        f"{path.name} imports forbidden {n.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not any(f in node.module.split(".")[0] for f in forbidden), (
                        f"{path.name} imports forbidden {node.module}"
                    )
