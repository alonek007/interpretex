"""The eight investigation tools of Part 1.

Each module exposes a :data:`SPEC` (:class:`ToolSpec`) and a
``run(registry, args) -> ToolOutcome`` function. The registry binds a
:class:`TradeCase` and the :class:`ReferenceWorld` and resolves partial
arguments from the case record.
"""

from . import (
    read_document,
    check_document_consistency,
    check_price_benchmark,
    check_vessel_capacity,
    check_transit_plausibility,
    check_historical_trade,
    check_counterparty_network,
    check_contract_or_supporting_evidence,
)

__all__ = [
    "read_document",
    "check_document_consistency",
    "check_price_benchmark",
    "check_vessel_capacity",
    "check_transit_plausibility",
    "check_historical_trade",
    "check_counterparty_network",
    "check_contract_or_supporting_evidence",
]
