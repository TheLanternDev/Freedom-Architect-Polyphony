"""
Testy warstwy cache + szacowania kosztu w `BaseAgent`.

W v3.2 cache LLM przeszedł z endpointu `/generate` (legacy) do `BaseAgent`,
gdzie każde wywołanie agenta sprawdza Redisa pod kluczem
`llm:v7:<agent>:<sha256>`. Tu testujemy czyste funkcje:
  - `_cache_key` (deterministyczność + uwzględnienie dream_id)
  - `_calculate_cost` (cennik per model)
"""

from __future__ import annotations

import pytest

from agents.base_agent import BaseAgent


# ── _cache_key ──────────────────────────────────────────────────────────────


def test_cache_key_has_v6_prefix_and_agent_name():
    key = BaseAgent._cache_key("Kogit", "ctx", "claude-sonnet-4-6", 0.5)
    assert key.startswith("llm:v7:Kogit:")


def test_cache_key_is_deterministic_for_same_input():
    a = BaseAgent._cache_key("Syez", "ctx", "claude-sonnet-4-6", 0.4)
    b = BaseAgent._cache_key("Syez", "ctx", "claude-sonnet-4-6", 0.4)
    assert a == b


def test_cache_key_changes_with_context():
    a = BaseAgent._cache_key("Syez", "ctxA", "m", 0.4)
    b = BaseAgent._cache_key("Syez", "ctxB", "m", 0.4)
    assert a != b


def test_cache_key_changes_with_model():
    a = BaseAgent._cache_key("Syez", "ctx", "claude-sonnet-4-6", 0.4)
    b = BaseAgent._cache_key("Syez", "ctx", "claude-opus-4-6", 0.4)
    assert a != b


def test_cache_key_changes_with_temperature():
    a = BaseAgent._cache_key("Syez", "ctx", "m", 0.3)
    b = BaseAgent._cache_key("Syez", "ctx", "m", 0.7)
    assert a != b


def test_cache_key_includes_dream_id():
    """AKSJOMAT 1: cache MUSI być izolowany per marzenie, inaczej różne
    marzenia mieszałyby się w cache i agenci zwracaliby kontekstowo zły głos."""
    no_dream = BaseAgent._cache_key("Syez", "ctx", "m", 0.4, dream_id=None)
    with_dream = BaseAgent._cache_key("Syez", "ctx", "m", 0.4, dream_id="abc-123")
    other_dream = BaseAgent._cache_key("Syez", "ctx", "m", 0.4, dream_id="xyz-999")
    assert no_dream != with_dream
    assert with_dream != other_dream


def test_cache_key_changes_with_debate_mode():
    a = BaseAgent._cache_key("Syez", "ctx", "m", 0.4, debate_mode="pelna")
    b = BaseAgent._cache_key("Syez", "ctx", "m", 0.4, debate_mode="codzienny")
    assert a != b


# ── _calculate_cost ─────────────────────────────────────────────────────────


def test_cost_calculation_sonnet():
    """Sonnet 4.6: 3 USD / 1M input, 15 USD / 1M output."""
    cost = BaseAgent._calculate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert cost == pytest.approx(18.0)


def test_cost_calculation_opus():
    """Opus 4.6: 15 USD / 1M input, 75 USD / 1M output."""
    cost = BaseAgent._calculate_cost("claude-opus-4-6", 1_000_000, 1_000_000)
    assert cost == pytest.approx(90.0)


def test_cost_calculation_haiku():
    """Haiku 4.5: 0.25 / 1.25 USD / 1M."""
    cost = BaseAgent._calculate_cost(
        "claude-haiku-4-5-20251001", 1_000_000, 1_000_000
    )
    assert cost == pytest.approx(1.5)


def test_cost_calculation_unknown_model_returns_zero():
    assert BaseAgent._calculate_cost("nonexistent-model", 100, 100) == 0.0


def test_cost_calculation_small_usage():
    """Sanity: małe usage = bardzo niski koszt, nadal poprawnie liczone."""
    cost = BaseAgent._calculate_cost("claude-sonnet-4-6", 1_000, 500)
    expected = (1_000 * 3.0 + 500 * 15.0) / 1_000_000
    assert cost == pytest.approx(expected)
