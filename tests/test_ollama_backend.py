"""Jednostkowe testy backendu Ollama (bez realnego serwera w CI)."""

from __future__ import annotations

import pytest

from config import llm_providers as lp


def test_effective_backend_picks_ollama_when_configured(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert lp.effective_llm_backend() == "ollama"


def test_effective_backend_auto_ollama_when_only_base_url(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "auto")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert lp.effective_llm_backend() == "ollama"


def test_effective_backend_default_unchanged_without_ollama_env(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "auto")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert lp.effective_llm_backend() == "none"


def test_ollama_model_mapping(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.3:70b")
    monkeypatch.setenv("OLLAMA_MODEL_FAST", "llama3.2:3b")
    assert lp.map_claude_model_to_ollama("claude-haiku-4-5") == "llama3.2:3b"
    assert lp.map_claude_model_to_ollama("claude-sonnet-4-6") == "llama3.3:70b"
    assert lp.map_claude_model_to_ollama("claude-opus-4-6") == "llama3.3:70b"


@pytest.mark.asyncio
async def test_ollama_unreachable_raises_clean_error(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11499")
    with pytest.raises(RuntimeError, match=r"Ollama unreachable at http://127\.0\.0\.1:11499"):
        await lp.ollama_chat_completion(
            system="sys",
            user="hi",
            model="llama3.2:3b",
            max_tokens=32,
            temperature=0.2,
        )
