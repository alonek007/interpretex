"""Flat JSON Schemas for the structured LLM calls (kept small; validated locally)."""
from __future__ import annotations

DIMENSIONS = ["economic", "physical", "temporal", "documentary", "behavioural", "network"]
SEVERITIES = ["none", "low", "medium", "high"]
STANCES = ["supports_suspicion", "refutes_suspicion", "neutral"]
HYP_KINDS = ["benign", "suspicious"]
HYP_STATUSES = ["open", "supported", "weakened", "refuted", "untestable"]
STOP_REASONS = ["sufficient_evidence", "budget_exhausted", "no_informative_tool_left"]

OBJECT = "object"
ARRAY = "array"
STRING = "string"
NUMBER = "number"
BOOL = "boolean"
NULL = "null"


def _obj(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": OBJECT, "properties": properties, "required": required or [], "additionalProperties": False}


def _str() -> dict:
    return {"type": STRING}


def _arr(items: dict) -> dict:
    return {"type": ARRAY, "items": items}


def _num(lo: float = 0.0, hi: float = 1.0) -> dict:
    return {"type": NUMBER, "minimum": lo, "maximum": hi}


TRIAGE_SCHEMA = _obj(
    {
        "trade_narrative": _str(),
        "initial_concerns": _arr(_str()),
        "unknowns": _arr(_str()),
        "dimensions_to_probe": _arr({"type": STRING, "enum": DIMENSIONS}),
    },
    required=["trade_narrative", "initial_concerns", "unknowns", "dimensions_to_probe"],
)

HYPOTHESISE_SCHEMA = _obj(
    {
        "hypotheses": _arr(
            _obj(
                {
                    "kind": {"type": STRING, "enum": HYP_KINDS},
                    "statement": _str(),
                    "explains": _arr({"type": STRING, "enum": DIMENSIONS}),
                    "prior": _num(),
                    "discriminating_evidence_needed": _arr(_str()),
                },
                required=["kind", "statement", "explains", "prior"],
            )
        )
    },
    required=["hypotheses"],
)

PLAN_SCHEMA = _obj(
    {
        "reasoning": _str(),
        "chosen_tool": {"oneOf": [_str(), {"type": NULL}]},
        "chosen_args": {"type": OBJECT, "additionalProperties": True},
        "targets_hypotheses": _arr(_str()),
        "expected_information_gain": _num(),
        "considered": _arr(
            _obj(
                {
                    "tool": _str(),
                    "expected_information_gain": _num(),
                    "why_not": _str(),
                },
                required=["tool", "expected_information_gain", "why_not"],
            )
        ),
        "stop_reason": {"oneOf": [{"type": STRING, "enum": STOP_REASONS}, {"type": NULL}]},
    },
    required=["reasoning", "chosen_tool", "chosen_args", "targets_hypotheses", "expected_information_gain"],
)

INTERPRET_SCHEMA = _obj(
    {
        "evidence": _arr(
            _obj(
                {
                    "dimension": {"type": STRING, "enum": DIMENSIONS},
                    "stance": {"type": STRING, "enum": STANCES},
                    "weight": _num(),
                    "statement": _str(),
                    "interpretation": _str(),
                    "hypotheses_affected": _arr(_str()),
                    "observation_ids": _arr(_str()),
                },
                required=["dimension", "stance", "weight", "statement", "observation_ids"],
            )
        ),
        "hypothesis_updates": _arr(
            _obj(
                {
                    "hypothesis_id": _str(),
                    "posterior": _num(),
                    "status": {"type": STRING, "enum": HYP_STATUSES},
                    "rationale": _str(),
                },
                required=["hypothesis_id", "posterior", "status"],
            )
        ),
    },
    required=["evidence", "hypothesis_updates"],
)

CORROBORATE_SCHEMA = _obj({"narrative": _str()}, required=["narrative"])

REQUESTS_SCHEMA = _obj(
    {
        "requests": _arr(
            _obj(
                {
                    "item": _str(),
                    "why": _str(),
                    "resolves_hypotheses": _arr(_str()),
                    "priority": {"type": "integer", "minimum": 1, "maximum": 3},
                },
                required=["item", "why", "resolves_hypotheses", "priority"],
            )
        )
    },
    required=["requests"],
)

REPORT_SCHEMA = _obj(
    {
        "executive_summary": _str(),
        "key_findings": _arr(_str()),
    },
    required=["executive_summary", "key_findings"],
)
