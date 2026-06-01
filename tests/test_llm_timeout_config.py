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
