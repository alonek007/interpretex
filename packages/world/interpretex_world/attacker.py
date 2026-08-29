"""attacker — the adversarial case generator.

Deterministic fallback (``case_adv_004``) keeps every individual signal low or
medium so the demo shows exactly why naive single-signal screening misses a
structured scheme. Honours ``FEATURE_ATTACKER``. The LLM path (when
configured) would attempt a more evasive case; we keep the deterministic
fallback stable and reproducible, and validate it against the known thresholds
so a regression can never silently push a signal into the high band.
"""

from __future__ import annotations

from typing import Optional

from interpretex_contracts import AttackSpec, TradeCase
from interpretex_contracts.helpers import Flags

from . import demo
from .registry import build_tool_registry


def _self_check(case: TradeCase) -> list[str]:
    """Re-run the relevant tools and report any observation above medium."""
    reg = build_tool_registry(case)
    problems: list[str] = []
    # price, capacity, transit, network — the four signals the fallback must hold
    checks = [
        ("check_price_benchmark", {}),
        ("check_vessel_capacity", {}),
        ("check_transit_plausibility", {}),
        ("check_counterparty_network", {}),
    ]
    for name, args in checks:
        result = reg.call(name, args)
        for o in result.observations:
            if o.severity.value in ("high",):
                problems.append(f"{name}: {o.statement}")
    return problems


def attack(spec: Optional[AttackSpec] = None, llm=None) -> TradeCase:
    """Generate an adversarial trade case.

    ``spec`` is accepted for protocol compatibility; the deterministic fallback
    is used so the demo and fixtures are byte-stable. When ``FEATURE_ATTACKER``
    is off the same fallback is returned (the attacker is a data author, not a
    feature that can silently disappear).
    """
    _ = (spec, llm)  # reserved: deterministic fallback ignores tuning for stability
    case = demo.build_attacker_fallback()
    problems = _self_check(case)
    if problems:
        # defensive: never ship an attacker case that trips a high signal
        import warnings
        warnings.warn("attacker fallback self-check found high-severity signals: "
                      + "; ".join(problems))
    return case
