"""Test doubles for the Part 2 agent.

- ScriptedLLM: returns canned JSON for the `plan` tag, and deliberately raises
  on every other tag so the loop exercises its per-stage fallback path (proving
  the agent degrades gracefully instead of crashing).
- FakeToolRegistry: a MiniToolRegistry that can be told to *raise* on specific
  tools, so we can test that a failing tool never breaks the investigation.
These are test scaffolding only and live under tests/agent.
"""
from __future__ import annotations

import json
from typing import Any

from interpretex_contracts import LLMError, ToolResult

from agent.miniregistry import MiniToolRegistry


class ScriptedLLM:
    """An LLMClient stand-in. Scripts only the planner; everything else fails
    on purpose so the deterministic fallback runs for those stages."""

    def __init__(self, plan_choices: dict[int, str | None] | None = None, model: str = "scripted") -> None:
        self.plan_choices = plan_choices or {}
        self.model = model
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
        self.replayed = False
        self.tags_seen: list[str] = []

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2048,
        tag: str = "",
    ) -> str:
        self.usage["calls"] += 1
        self.tags_seen.append(tag)
        if tag.startswith("plan"):
            step = int(tag.split(".")[1]) if "." in tag else 1
            choice = self.plan_choices.get(step)
            if choice is None:
                return json.dumps({
                    "reasoning": "scripted stop", "chosen_tool": None,
                    "chosen_args": {}, "targets_hypotheses": [],
                    "expected_information_gain": 0.0, "considered": [],
                    "stop_reason": "sufficient_evidence",
                })
            return json.dumps({
                "reasoning": "scripted choice", "chosen_tool": choice,
                "chosen_args": {}, "targets_hypotheses": [],
                "expected_information_gain": 1.0, "considered": [],
            })
        raise LLMError(f"scripted: no handler for tag {tag}")

    def complete_json(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        tag: str = "",
        retries: int = 2,
    ) -> dict[str, Any]:
        import jsonschema

        text = self.complete(
            system=system, messages=messages, temperature=temperature,
            max_tokens=max_tokens, tag=tag,
        )
        obj = json.loads(text)
        jsonschema.validate(obj, schema)
        return obj


class FakeToolRegistry(MiniToolRegistry):
    """MiniToolRegistry that raises on demand, to simulate tools that blow up.
    The agent must never crash: the loop catches and converts this into a
    failed ToolResult, then continues."""

    def __init__(self, case: Any, world: Any, fail: set[str] | None = None) -> None:
        super().__init__(case, world)
        self.fail = set(fail or [])

    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        if name in self.fail:
            raise RuntimeError(f"simulated failure of {name}")
        return super().call(name, args)
