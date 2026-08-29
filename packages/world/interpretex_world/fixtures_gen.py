"""Generate the golden fixtures consumed by Parts 2 and 3.

Writes into ``interpretex_contracts/fixtures/``:

    cases/case_*.json            full TradeCase (incl. label) for the 3 demo cases
    tool_specs.json              the 8 ToolSpec objects
    tool_results/case_*.json     {tool_name: ToolResult} for all 8 tools x 3 cases

``demo_trace.py`` writes the run trace (events + result) separately. Run both::

    python -m interpretex_world.fixtures_gen
    python -m interpretex_world.demo_trace

The output is deterministic: the same world build always produces byte-equal
fixtures, so they double as regression snapshots.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from interpretex_contracts import ToolSpec

from .api import World
from .tools import (
    check_contract_or_supporting_evidence,
    check_document_consistency,
    check_historical_trade,
    check_price_benchmark,
    check_counterparty_network,
    check_transit_plausibility,
    check_vessel_capacity,
    read_document,
)

DEMO_IDS = ["case_clean_001", "case_explainable_002", "case_suspicious_003"]

SPEC_MODULES = [
    read_document, check_document_consistency, check_price_benchmark,
    check_vessel_capacity, check_transit_plausibility, check_historical_trade,
    check_counterparty_network, check_contract_or_supporting_evidence,
]

# a claim per case so the contract/supporting-evidence tool has valid input
CLAIM_BY_CASE = {
    "case_clean_001": "grade Washed arabica",
    "case_explainable_002": "offtake relationship",
    "case_suspicious_003": "grade LME Grade A standard",
}


def _this_repo() -> Path:
    return Path(os.path.abspath(__file__)).resolve().parents[3]


def _fixtures_dir() -> Path:
    return _this_repo() / "packages" / "contracts" / "interpretex_contracts" / "fixtures"


def main() -> None:
    out = _fixtures_dir()
    (out / "cases").mkdir(parents=True, exist_ok=True)
    (out / "tool_results").mkdir(parents=True, exist_ok=True)

    w = World()

    # 1) tool specs
    specs = [m.SPEC for m in SPEC_MODULES]
    (out / "tool_specs.json").write_text(
        json.dumps({"tools": [s.model_dump(mode="json") for s in specs]}, indent=2),
        encoding="utf-8")
    print(f"wrote {len(specs)} tool specs")

    # 2) per-case: TradeCase + tool results
    for case_id in DEMO_IDS:
        case = w.load_case(case_id)
        (out / "cases" / f"{case_id}.json").write_text(
            case.model_dump_json(indent=2), encoding="utf-8")

        reg = w.build_tool_registry(case)
        claim = CLAIM_BY_CASE.get(case_id, "grade A")
        results: dict[str, dict] = {}
        for spec in reg.specs():
            args = {"claim": claim} if spec.name == "check_contract_or_supporting_evidence" else {}
            res = reg.call(spec.name, args)
            results[spec.name] = res.model_dump(mode="json")
        (out / "tool_results" / f"{case_id}.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8")
        print(f"wrote case + {len(results)} tool results for {case_id}")


if __name__ == "__main__":
    main()
