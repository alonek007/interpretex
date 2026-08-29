"""Shared protocols and LLM errors (frozen, section 8.7)."""
from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

from .investigation import InvestigationEvent


class LLMError(Exception):
    """Raised when the LLM transport fails (network, auth, quota)."""


class LLMJsonError(LLMError):
    """Raised when complete_json exhausts its repair retries on invalid JSON."""


@runtime_checkable
class LLMClient(Protocol):
    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2048,
        tag: str = "",
    ) -> str: ...

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
    ) -> dict[str, Any]: ...


EmitFn = Callable[[InvestigationEvent], None]
