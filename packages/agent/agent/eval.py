"""Evaluation harness (section 14).

    python -m agent.eval --cases all --runs 3 [--budget 6] [--live]

May read CaseLabel ground truth — the agent itself must NEVER import this
module. Default runs use the deterministic fallback path (llm=None), which is
fully reproducible; pass --live (with OPENROUTER_API_KEY set) to run the LLM
path.

Metrics reported:
  - verdict accuracy against expected_verdict per case
  - false-escalation rate on clean / suspicious_but_legitimate cases
  - mean tool calls and mean cost versus the exhaustive cost of 10
  - proportion of runs in which a benign hypothesis was tested before escalation
  - verdict stability across repeated runs of the same case
  - count of degraded runs
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict

from interpretex_contracts import Verdict

from .api import investigate
from .demo_cases import ALL_CASES, build
from .miniregistry import MiniToolRegistry
from .policy import benign_tested

EXHAUSTIVE_COST = 10  # one call to each of the eight tools


def run_case(case_id: str, runs: int, budget: int, llm=None) -> dict:
    agent_view, world, _trade_case = build(case_id)
    registry = MiniToolRegistry(agent_view, world)
    verdicts: list[str] = []
    tool_counts: list[int] = []
    costs: list[int] = []
    degraded = 0
    benign_tested_count = 0
    escalate_runs = 0
    for i in range(runs):
        result = investigate(agent_view, registry, llm=llm, budget=budget, seed=1000 + i)
        verdicts.append(result.decision.verdict.value)
        tool_counts.append(len(result.tool_calls))
        costs.append(sum(t.cost_units for t in result.tool_calls))
        degraded += 1 if result.meta.degraded else 0
        if benign_tested(result.hypotheses, result.plan_steps):
            benign_tested_count += 1
        if result.decision.verdict == Verdict.escalate:
            escalate_runs += 1
    expected = _expected_verdict(case_id)
    return {
        "case_id": case_id,
        "expected": expected,
        "verdicts": verdicts,
        "mean_calls": sum(tool_counts) / runs,
        "mean_cost": sum(costs) / runs,
        "degraded": degraded,
        "benign_tested": benign_tested_count,
        "escalations": escalate_runs,
    }


def _expected_verdict(case_id: str) -> str:
    _, _, trade_case = build(case_id)
    label = trade_case.label
    assert label is not None, "demo cases always carry labels"
    return label.expected_verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent.eval", description="Interpretex Part 2 evaluation harness")
    parser.add_argument("--cases", default="all",
                        help="'all' or a comma-separated list of case ids")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--budget", type=int, default=6)
    parser.add_argument("--live", action="store_true",
                        help="use the real LLM (requires OPENROUTER_API_KEY); default is the deterministic path")
    args = parser.parse_args(argv)

    case_ids = list(ALL_CASES) if args.cases == "all" else [c.strip() for c in args.cases.split(",")]
    llm = None
    if args.live:
        from interpretex_contracts import LLMError, OpenRouterLLM

        try:
            llm = OpenRouterLLM()
        except Exception as exc:  # pragma: no cover
            print(f"could not build LLM client ({exc}); running deterministic instead", file=sys.stderr)

    rows = [run_case(cid, args.runs, args.budget, llm) for cid in case_ids]

    clean_rows = [r for r in rows if r["expected"] in ("release", "hold")
                  and _case_class(r["case_id"]) in ("clean", "suspicious_but_legitimate")]
    false_escalations = sum(r["escalations"] for r in clean_rows)
    clean_runs = args.runs * len(clean_rows)

    print("\n=== Interpretex Part 2 eval ===")
    print(f"runs per case: {args.runs}  budget: {args.budget}  mode: {'live LLM' if llm else 'deterministic'}\n")
    for r in rows:
        verdict_counts = dict(Counter(r["verdicts"]))
        accuracy = sum(1 for v in r["verdicts"] if _verdict_ok(r["case_id"], v)) / len(r["verdicts"])
        stability = max(verdict_counts.values()) / len(r["verdicts"])
        print(f"{r['case_id']}")
        print(f"  expected={r['expected']}  verdicts={verdict_counts}  accuracy={accuracy:.0%}  stability={stability:.0%}")
        print(f"  mean tool calls={r['mean_calls']:.1f}  mean cost={r['mean_cost']:.1f} "
              f"(exhaustive baseline {EXHAUSTIVE_COST})  efficiency={1 - r['mean_cost'] / EXHAUSTIVE_COST:.0%}")
        print(f"  benign hypothesis tested in {r['benign_tested']}/{len(r['verdicts'])} runs  "
              f"escalations={r['escalations']}  degraded runs={r['degraded']}")
    print()
    print(f"False-escalation rate on clean / explainable cases: {false_escalations}/{clean_runs}"
          f" ({(false_escalations / clean_runs if clean_runs else 0):.0%})")
    ok = all(_verdict_ok(r["case_id"], r["verdicts"][0]) for r in rows) and false_escalations == 0
    print(f"\nOverall: {'PASS' if ok else 'CHECK ABOVE'}")
    return 0


def _case_class(case_id: str) -> str:
    _, _, trade_case = build(case_id)
    assert trade_case.label is not None
    return trade_case.label.case_class.value


def _verdict_ok(case_id: str, actual: str) -> bool:
    """Class-aware acceptance: clean -> release; suspicious_but_legitimate ->
    hold or release (ESCALATE is a failure); illicit/adversarial -> escalate."""
    expected = _expected_verdict(case_id)
    klass = _case_class(case_id)
    if klass == "suspicious_but_legitimate":
        return actual in ("hold", "release")
    return actual == expected


if __name__ == "__main__":
    raise SystemExit(main())
