"""Regresja: Opus 4.7 nie przyjmuje `temperature` w Messages API."""

from __future__ import annotations

from config import llm_providers as lp


def test_anthropic_omits_temperature_for_opus_46():
    assert lp.anthropic_omits_temperature("claude-opus-4-6") is True


def test_anthropic_keeps_temperature_for_typical_sonnet(monkeypatch):
    monkeypatch.delenv("AW_ANTHROPIC_OMIT_TEMPERATURE_SUBSTR", raising=False)
    assert lp.anthropic_omits_temperature("claude-sonnet-4-6") is False
    assert lp.anthropic_omits_temperature("claude-haiku-4-5-20251001") is False


def test_extra_substrings_via_env(monkeypatch):
    monkeypatch.setenv("AW_ANTHROPIC_OMIT_TEMPERATURE_SUBSTR", "sonnet-4-6,custom")
    assert lp.anthropic_omits_temperature("claude-sonnet-4-6") is True
    assert lp.anthropic_omits_temperature("x-custom-preview") is True
