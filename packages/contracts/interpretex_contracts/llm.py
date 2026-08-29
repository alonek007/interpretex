"""OpenRouter LLM adapter with an on-disk cassette cache.

complete()/complete_json() are the only LLM surface in the system. The cache is
keyed by a hash of (model, system, messages, temperature, max_tokens); with
LLM_CACHE_MODE=read a run is byte-identical with zero network.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

try:
    import jsonschema
except Exception:  # pragma: no cover - jsonschema optional at runtime
    jsonschema = None

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openrouter/auto"


class LLMError(RuntimeError):
    pass


class _CacheKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    h: str


def _cache_key(model: str, system: str, messages: list[dict], temperature: float,
               max_tokens: int) -> str:
    blob = json.dumps(
        {"model": model, "system": system, "messages": messages,
         "temperature": temperature, "max_tokens": max_tokens},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _cache_dir() -> Path:
    return Path(os.environ.get("LLM_CACHE_DIR", ".llm_cache"))


def _cache_mode() -> str:
    return os.environ.get("LLM_CACHE_MODE", "off")


class OpenRouterClient:
    """OpenAI-compatible REST over raw httpx. No SDK, no native tool calling."""

    def __init__(self, api_key: str | None = None, model: str | None = None,
                 base_url: str | None = None, timeout: float = 120.0) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get(
            "OPENROUTER_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    # -- low level ---------------------------------------------------------

    def _post(self, payload: dict) -> dict:
        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY is not set")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions",
                               headers=headers, json=payload)
        if resp.status_code != 200:
            raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    @staticmethod
    def _extract(data: dict) -> tuple[str, int, int]:
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected LLM response shape: {data}") from exc
        usage = data.get("usage") or {}
        return text, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))

    # -- cache -------------------------------------------------------------

    def _cached(self, key: str) -> str | None:
        if _cache_mode() not in ("read", "write"):
            return None
        path = _cache_dir() / f"{key}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def _store(self, key: str, text: str) -> None:
        if _cache_mode() == "write":
            d = _cache_dir()
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{key}.txt").write_text(text, encoding="utf-8")

    # -- public API --------------------------------------------------------

    def complete(self, *, system: str, messages: list[dict], temperature: float = 0.2,
                 max_tokens: int = 2048, tag: str = "") -> str:
        key = _cache_key(self.model, system, messages, temperature, max_tokens)
        hit = self._cached(key)
        if hit is not None:
            return hit
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = self._post(payload)
        text, pt, ct = self._extract(data)
        self.llm_calls += 1
        self.prompt_tokens += pt
        self.completion_tokens += ct
        self._store(key, text)
        return text

    def complete_json(self, *, system: str, messages: list[dict], schema: dict,
                      temperature: float = 0.1, max_tokens: int = 2048,
                      tag: str = "", retries: int = 2) -> dict:
        prompt = list(messages)
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            text = self.complete(system=system, messages=prompt,
                                 temperature=temperature, max_tokens=max_tokens,
                                 tag=f"{tag}:{attempt}")
            parsed = self._parse_json(text)
            if parsed is not None:
                ok, err = self._validate(parsed, schema)
                if ok:
                    return parsed
                last_error = LLMError(f"schema violation: {err}")
            else:
                last_error = LLMError("response was not valid JSON")
            prompt = [*prompt,
                      {"role": "assistant", "content": text},
                      {"role": "user", "content":
                       "Your previous reply was not valid per the schema. "
                       f"Error: {last_error}. Reply again with JSON only."}]
        raise LLMError(f"complete_json failed after retries: {last_error}")

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        s = text.strip()
        if s.startswith("```"):
            s = s.strip("`")
            if s.startswith("json"):
                s = s[4:]
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            return json.loads(s[start:end + 1])
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _validate(data: dict, schema: dict) -> tuple[bool, str]:
        if jsonschema is None:
            return True, ""
        try:
            jsonschema.validate(data, schema)
            return True, ""
        except jsonschema.ValidationError as exc:
            return False, exc.message


class ScriptedLLMClient:
    """Deterministic offline stand-in for tests. Replays canned replies per tag."""

    def __init__(self, replies: dict[str, str] | None = None) -> None:
        self.replies = replies or {}
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def complete(self, *, system: str, messages: list[dict], temperature: float = 0.2,
                 max_tokens: int = 2048, tag: str = "") -> str:
        self.llm_calls += 1
        return self.replies.get(tag, self.replies.get("*", "{}"))

    def complete_json(self, *, system: str, messages: list[dict], schema: dict,
                      temperature: float = 0.1, max_tokens: int = 2048,
                      tag: str = "", retries: int = 2) -> dict:
        text = self.complete(system=system, messages=messages, tag=tag)
        data = json.loads(text)
        ok, err = OpenRouterClient._validate(data, schema)
        if not ok:
            raise LLMError(err)
        return data


def client_from_env() -> OpenRouterClient | None:
    """Build the real client when a key is configured; None otherwise."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        return None
    return OpenRouterClient()
