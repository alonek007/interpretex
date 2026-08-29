"""Shared LLM adapter: OpenRouter over raw httpx + cassette cache + ScriptedLLM.

Why raw HTTP over an SDK: OpenRouter is a plain OpenAI-compatible REST endpoint
and support for native function calling / response_format varies across its
alpha and stealth models. Raw HTTP means a model swap is one env var and never
a dependency change.

The cassette cache is the single highest-value component in the repo: with
``LLM_CACHE_MODE=read`` a demo runs with zero network, zero rate limits, zero
latency and byte-identical output.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from .helpers import stable_hash


class LLMError(RuntimeError):
    """Raised after retries are exhausted, on config errors, or on a cache
    miss in ``read`` mode."""


class LLMJsonError(LLMError):
    """Raised when complete_json cannot obtain schema-valid JSON."""


_RETRYABLE_STATUS = {429, 500, 502, 503, 504, 520, 529}


def _cache_mode() -> str:
    return os.environ.get("LLM_CACHE_MODE", "readwrite").strip().lower()


def _cache_dir() -> Path:
    return Path(os.environ.get("LLM_CACHE_DIR", "./.llm_cache"))


def _cache_key(model: str, system: str, messages: list[dict], temperature: float,
               max_tokens: int) -> str:
    return stable_hash(model, system, messages, temperature, max_tokens)[:32]


# --------------------------------------------------------------- extraction --


def extract_json_object(text: str) -> dict[str, Any]:
    """Tolerant JSON-object extractor.

    Handles bare JSON, fenced ```json blocks, a prose preamble and trailing
    commentary (brace-matching fallback). Raises ValueError when no object
    can be recovered.
    """
    if text is None:
        raise ValueError("empty response")
    candidates: list[str] = []

    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    candidates.extend(fenced)
    candidates.append(text)

    # brace-matching scan: first balanced {...} that parses wins
    starts = [m.start() for m in re.finditer(r"\{", text)]
    for start in starts:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start:i + 1])
                    break

    for cand in candidates:
        cand = cand.strip()
        if not cand:
            continue
        try:
            obj = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("no JSON object found in response")


def validate_against_schema(obj: dict[str, Any], schema: dict[str, Any]) -> str | None:
    """Validate ``obj`` against a JSON Schema; return an error message or None.

    Uses ``jsonschema`` when importable, else checks required keys only.
    """
    try:
        import jsonschema  # noqa: PLC0415
    except ImportError:
        required = schema.get("required", [])
        missing = [k for k in required if k not in obj]
        if missing:
            return f"missing required keys: {missing}"
        return None
    try:
        jsonschema.validate(obj, schema)
        return None
    except jsonschema.ValidationError as exc:
        return f"{exc.message} (path: {'/'.join(str(p) for p in exc.absolute_path) or '<root>'})"


# ---------------------------------------------------------------- the client --


class OpenRouterClient:
    """OpenAI-compatible chat client with an on-disk cassette cache.

    Env vars: OPENROUTER_API_KEY, LLM_MODEL, LLM_BASE_URL, LLM_CACHE_MODE,
    LLM_CACHE_DIR, LLM_TIMEOUT_S, LLM_MAX_RETRIES.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None,
                 base_url: str | None = None, timeout_s: float | None = None,
                 max_retries: int | None = None, cache_mode: str | None = None,
                 cache_dir: str | Path | None = None) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL",
                        "https://openrouter.ai/api/v1")).rstrip("/")
        self.timeout_s = float(timeout_s if timeout_s is not None
                               else os.environ.get("LLM_TIMEOUT_S", 60))
        self.max_retries = int(max_retries if max_retries is not None
                               else os.environ.get("LLM_MAX_RETRIES", 2))
        self.cache_mode = (cache_mode or _cache_mode())
        self.cache_dir = Path(cache_dir) if cache_dir else _cache_dir()

        # usage accounting (Part 2 feeds RunMeta from this)
        self.usage: dict[str, Any] = {
            "calls": 0, "cache_hits": 0, "retries": 0,
            "prompt_tokens": 0, "completion_tokens": 0,
            "by_tag": {},
        }

    # -- accounting -----------------------------------------------------

    def _account(self, tag: str, prompt_tokens: int, completion_tokens: int,
                 cache_hit: bool, retries: int) -> None:
        u = self.usage
        u["calls"] += 1
        u["prompt_tokens"] += prompt_tokens
        u["completion_tokens"] += completion_tokens
        u["retries"] += retries
        if cache_hit:
            u["cache_hits"] += 1
        slot = u["by_tag"].setdefault(tag or "untagged", {
            "calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cache_hits": 0})
        slot["calls"] += 1
        slot["prompt_tokens"] += prompt_tokens
        slot["completion_tokens"] += completion_tokens
        if cache_hit:
            slot["cache_hits"] += 1

    # -- cache ------------------------------------------------------------

    def _cassette_path(self, tag: str, key: str) -> Path:
        safe_tag = re.sub(r"[^A-Za-z0-9_.-]", "_", tag or "untagged")
        return self.cache_dir / f"{safe_tag}.{key}.json"

    def _cache_get(self, tag: str, key: str) -> str | None:
        if self.cache_mode in {"off", "write"}:
            return None
        path = self._cassette_path(tag, key)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))["response"]
            except (json.JSONDecodeError, KeyError, OSError):
                return None
        if self.cache_mode == "read":
            raise LLMError(
                f"cache miss for tag={tag!r} in LLM_CACHE_MODE=read: {path}. "
                "Record the cassette first (run once with LLM_CACHE_MODE=readwrite) "
                "or switch mode."
            )
        return None

    def _cache_put(self, tag: str, key: str, request: dict[str, Any], response: str) -> None:
        if self.cache_mode in {"off", "read"}:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cassette_path(tag, key)
        path.write_text(
            json.dumps({"request": request, "response": response}, ensure_ascii=False,
                       indent=1),
            encoding="utf-8",
        )

    # -- core -------------------------------------------------------------

    def complete(self, *, system: str, messages: list[dict[str, str]],
                 temperature: float = 0.2, max_tokens: int = 2048,
                 tag: str = "") -> str:
        """One chat completion; cached, retried, accounted. Returns text."""
        key = _cache_key(self.model, system, messages, temperature, max_tokens)
        cached = self._cache_get(tag, key)
        if cached is not None:
            self._account(tag, 0, 0, cache_hit=True, retries=0)
            return cached

        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/alonek007/interpretex",
            "X-Title": "Interpretex",
        }
        retries = 0
        backoff = 0.5
        last_err: str = ""
        while True:
            try:
                resp = httpx.post(f"{self.base_url}/chat/completions", json=payload,
                                  headers=headers, timeout=self.timeout_s)
            except httpx.HTTPError as exc:
                last_err = f"transport error: {exc}"
            else:
                if resp.status_code == 200:
                    try:
                        body = resp.json()
                        content = body["choices"][0]["message"]["content"] or ""
                        usage = body.get("usage", {}) or {}
                    except (KeyError, IndexError, ValueError) as exc:
                        last_err = f"malformed response body: {exc}"
                    else:
                        if content.strip():
                            self._cache_put(tag, key, payload, content)
                            self._account(tag, int(usage.get("prompt_tokens", 0)),
                                          int(usage.get("completion_tokens", 0)),
                                          cache_hit=False, retries=retries)
                            return content
                        last_err = "empty completion"
                elif resp.status_code in _RETRYABLE_STATUS:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                else:
                    raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
            if retries >= self.max_retries:
                raise LLMError(f"LLM failed after {retries + 1} attempt(s): {last_err}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 8.0)
            retries += 1

    def complete_json(self, *, system: str, messages: list[dict[str, str]],
                      schema: dict[str, Any], temperature: float = 0.1,
                      max_tokens: int = 2048, tag: str = "", retries: int = 2) -> dict:
        """Strict-JSON completion with a local repair loop.

        Appends the JSON Schema to the system prompt with a hard instruction to
        emit one JSON object and nothing else; parses with a tolerant extractor;
        validates; on failure re-prompts with the validator error and the model's
        previous output. Never uses provider-side structured output.
        """
        schema_block = json.dumps(schema, ensure_ascii=False)
        hard_system = (
            f"{system}\n\nRespond with ONE JSON object and nothing else — no prose, "
            f"no code fences. It must validate against this JSON Schema:\n{schema_block}"
        )
        convo = list(messages)
        seen: list[str] = []
        last_error = "no attempt made"
        for attempt in range(retries + 1):
            text = self.complete(system=hard_system, messages=convo,
                                 temperature=temperature, max_tokens=max_tokens,
                                 tag=tag)
            try:
                obj = extract_json_object(text)
            except ValueError as exc:
                last_error = f"unparseable response: {exc}"
            else:
                err = validate_against_schema(obj, schema)
                if err is None:
                    return obj
                last_error = f"schema violation: {err}"
            seen.append(text)
            convo = [
                *messages,
                {"role": "assistant", "content": text},
                {"role": "user", "content":
                    "Your previous response was not valid: " + last_error
                    + "\nPrevious response:\n" + (text or "<empty>")
                    + "\nTry again. Respond with ONE JSON object that validates "
                      "against the schema in the system prompt, and nothing else."},
            ]
        raise LLMJsonError(
            f"complete_json failed after {retries + 1} attempt(s): {last_error}"
        )


class ScriptedLLM:
    """Deterministic offline LLM: hands out canned responses in order.

    Loops on the last response; records every request it was asked. This is
    what makes CI and offline unit tests possible (``LLM_PROVIDER=scripted``).
    """

    def __init__(self, responses: list[str], model: str = "scripted") -> None:
        if not responses:
            raise ValueError("ScriptedLLM needs at least one canned response")
        self.responses = list(responses)
        self.model = model
        self.asked: list[dict[str, Any]] = []
        self.usage: dict[str, Any] = {
            "calls": 0, "cache_hits": 0, "retries": 0,
            "prompt_tokens": 0, "completion_tokens": 0,
            "by_tag": {},
        }

    def complete(self, *, system: str, messages: list[dict[str, str]],
                 temperature: float = 0.2, max_tokens: int = 2048,
                 tag: str = "") -> str:
        self.asked.append({"system": system, "messages": messages,
                           "temperature": temperature, "max_tokens": max_tokens, "tag": tag})
        self.usage["calls"] += 1
        slot = self.usage["by_tag"].setdefault(tag or "untagged", {"calls": 0})
        slot["calls"] += 1
        idx = min(len(self.asked) - 1, len(self.responses) - 1)
        return self.responses[idx]

    def complete_json(self, *, system: str, messages: list[dict[str, str]],
                      schema: dict[str, Any], temperature: float = 0.1,
                      max_tokens: int = 2048, tag: str = "", retries: int = 2) -> dict:
        """Same repair loop semantics as OpenRouterClient, offline."""
        schema_block = json.dumps(schema, ensure_ascii=False)
        hard_system = (f"{system}\n\nRespond with ONE JSON object and nothing else — "
                       f"no prose, no code fences. It must validate against this JSON "
                       f"Schema:\n{schema_block}")
        convo = list(messages)
        last_error = "no attempt made"
        for _ in range(retries + 1):
            text = self.complete(system=hard_system, messages=convo,
                                 temperature=temperature, max_tokens=max_tokens, tag=tag)
            try:
                obj = extract_json_object(text)
            except ValueError as exc:
                last_error = f"unparseable response: {exc}"
            else:
                err = validate_against_schema(obj, schema)
                if err is None:
                    return obj
                last_error = f"schema violation: {err}"
            convo = [
                *messages,
                {"role": "assistant", "content": text},
                {"role": "user", "content":
                    "Your previous response was not valid: " + last_error
                    + "\nPrevious response:\n" + (text or "<empty>")
                    + "\nTry again. Respond with ONE JSON object and nothing else."},
            ]
        raise LLMJsonError(
            f"complete_json failed after {retries + 1} attempt(s): {last_error}"
        )


def build_llm() -> OpenRouterClient | ScriptedLLM:
    """Factory used by all three parts.

    ``LLM_PROVIDER=scripted`` selects ScriptedLLM (offline, deterministic);
    anything else selects OpenRouterClient.
    """
    provider = os.environ.get("LLM_PROVIDER", "openrouter").strip().lower()
    if provider == "scripted":
        raw = os.environ.get("SCRIPTED_RESPONSES", "")
        responses = json.loads(raw) if raw.strip() else [
            '{"ok": true}'
        ]
        return ScriptedLLM(responses)
    return OpenRouterClient()
