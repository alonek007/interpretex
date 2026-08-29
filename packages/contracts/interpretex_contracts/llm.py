"""OpenRouter LLM adapter + on-disk cassette cache (contract section 8.7).

- `complete_json` validates against a local JSON Schema and re-prompts on failure
  (repair loop), raising LLMJsonError after `retries`.
- Cassette cache keyed by hash(model, system, messages, temperature, max_tokens);
  LLM_CACHE_MODE=read replays from disk with zero network.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx
import jsonschema

from .helpers import canonical_json
from .protocols import LLMError, LLMJsonError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _cache_dir() -> Path:
    return Path(os.environ.get("LLM_CACHE_DIR", ".llm_cache"))


def _cache_mode() -> str:
    return os.environ.get("LLM_CACHE_MODE", "off").strip().lower()


def cache_key(model: str, system: str, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
    raw = canonical_json(
        {"model": model, "system": system, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class OpenRouterLLM:
    """Minimal OpenAI-compatible client over raw httpx with a cassette cache."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("LLM_MODEL", "openrouter/auto")
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
        self.replayed = False

    # ------------------------------------------------------------------ raw

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2048,
        tag: str = "",
    ) -> str:
        key = cache_key(self.model, system, messages, temperature, max_tokens)
        cached = self._read_cassette(key)
        if cached is not None:
            self.replayed = True
            return cached

        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY is not set")

        body = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        try:
            resp = httpx.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {}) or {}
            self.usage["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
            self.usage["completion_tokens"] += int(usage.get("completion_tokens", 0) or 0)
            self.usage["calls"] += 1
        except LLMError:
            raise
        except Exception as exc:  # transport / parsing failure
            raise LLMError(f"LLM transport failure: {exc}") from exc

        self._write_cassette(key, content)
        return content

    # --------------------------------------------------------------- json

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
        convo = list(messages)
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            content = self.complete(
                system=system, messages=convo, temperature=temperature, max_tokens=max_tokens, tag=tag
            )
            parsed = extract_json(content)
            if parsed is None:
                last_error = LLMJsonError(f"[{tag}] response was not parseable JSON")
                convo = [*convo, {"role": "assistant", "content": content}]
                convo.append(
                    {
                        "role": "user",
                        "content": "That was not valid JSON matching the schema. "
                        "Return ONLY a single JSON object, no prose, no code fences.",
                    }
                )
                continue
            try:
                jsonschema.validate(parsed, schema)
                return parsed
            except jsonschema.ValidationError as exc:
                last_error = exc
                convo = [*convo, {"role": "assistant", "content": content}]
                convo.append(
                    {
                        "role": "user",
                        "content": f"Your JSON failed schema validation: {exc.message[:300]}. "
                        "Return ONLY a corrected single JSON object.",
                    }
                )
        raise LLMJsonError(f"[{tag}] JSON repair loop exhausted: {last_error}")

    # ------------------------------------------------------------- cassettes

    def _cassette_path(self, key: str) -> Path:
        return _cache_dir() / f"{key}.txt"

    def _read_cassette(self, key: str) -> str | None:
        mode = _cache_mode()
        path = self._cassette_path(key)
        if mode in {"read", "write"} and path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    def _write_cassette(self, key: str, content: str) -> None:
        if _cache_mode() != "write":
            return
        try:
            path = self._cassette_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception:
            pass


def extract_json(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of a possibly chatty response."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
        cleaned = cleaned.strip()
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(cleaned[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None
