"""LLM client deterministic behaviour (scripted + build_llm factory)."""

import pytest

from interpretex_contracts import ScriptedLLM, build_llm


def test_build_llm_scripted_by_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "scripted")
    llm = build_llm()
    assert isinstance(llm, ScriptedLLM)


def test_scripted_llm_is_deterministic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "scripted")
    llm = build_llm()
    a = llm.complete(system="s", messages=[{"role": "user", "content": "hi"}])
    b = llm.complete(system="s", messages=[{"role": "user", "content": "hi"}])
    assert a == b


def test_build_llm_complete_returns_string(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "scripted")
    llm = build_llm()
    out = llm.complete(system="x", messages=[{"role": "user", "content": "ping"}])
    assert isinstance(out, str)
    assert out
