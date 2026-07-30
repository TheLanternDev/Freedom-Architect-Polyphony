"""Konfiguracja timeoutów LLM z ENV."""

from __future__ import annotations

import pytest

from config import llm_providers as lp


def test_llm_timeout_defaults():
    assert lp.LLM_TIMEOUT_SDK_SEC == 45
    assert lp.LLM_TIMEOUT_WAIT_SEC == 55
    assert lp.DREAM_TIMEOUT_WAIT_SEC == 60
    assert lp.LLM_TIMEOUT_WAIT_SEC > lp.LLM_TIMEOUT_SDK_SEC


def test_llm_timeout_env_override(monkeypatch):
    monkeypatch.setenv("AW_LLM_TIMEOUT_SDK", "30")
    monkeypatch.setenv("AW_LLM_TIMEOUT_WAIT", "40")
    monkeypatch.setenv("AW_DREAM_TIMEOUT_WAIT", "50")
    assert lp._int_env("AW_LLM_TIMEOUT_SDK", "45") == 30
    assert lp._int_env("AW_LLM_TIMEOUT_WAIT", "55") == 40
    assert lp._int_env("AW_DREAM_TIMEOUT_WAIT", "60") == 50


def test_syez_per_agent_timeout():
    """Syez fa2 (5000 tok) i personal (5000 tok) muszą mieć timeout_s > globalne 55s.

    Regresja: „[błąd syntezy: TimeoutError]" przy każdej dłuższej syntezie fa2."""
    from config.agent_models import get_model_config

    fa2 = get_model_config("Syez", council_mode="fa2")
    assert fa2["max_tokens"] == 5000
    assert fa2["timeout_s"] == 150
    assert fa2["timeout_s"] > lp.LLM_TIMEOUT_WAIT_SEC

    personal = get_model_config("Syez", council_mode="personal")
    assert personal["max_tokens"] == 5000
    assert personal["timeout_s"] == 120
    assert personal["timeout_s"] > lp.LLM_TIMEOUT_WAIT_SEC


def test_other_agents_no_timeout_override():
    """Głosy Rady zostają na globalnym timeoucie (degradują się łagodnie
    placeholderem [timeout: agent…], nie wywracają debaty)."""
    from config.agent_models import get_model_config

    for name in ("Kogit", "Obver", "Szow"):
        assert "timeout_s" not in get_model_config(name, council_mode="fa2")
