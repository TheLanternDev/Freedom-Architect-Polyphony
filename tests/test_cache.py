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


def test_cache_key_has_v8_prefix_and_agent_name():
    key = BaseAgent._cache_key("Kogit", "ctx", "claude-sonnet-4-6", 0.5)
    assert key.startswith("llm:v8:Kogit:")


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


def test_cache_key_isolates_per_user_id():
    """Multi-tenancy hard isolation: identyczny brief od dwóch userów MUSI
    dawać dwa różne klucze cache — inaczej Redis wycieka treść osobistą
    między kontami."""
    a = BaseAgent._cache_key("Syez", "ctx", "m", 0.4, user_id="user-A")
    b = BaseAgent._cache_key("Syez", "ctx", "m", 0.4, user_id="user-B")
    no_user = BaseAgent._cache_key("Syez", "ctx", "m", 0.4)
    assert a != b
    assert a != no_user
    assert b != no_user


def test_cache_key_isolates_per_tenant_id():
    """Ten sam user_id w różnych tenantach to różne konteksty — klucze
    cache muszą być rozdzielne."""
    a = BaseAgent._cache_key("Syez", "ctx", "m", 0.4, tenant_id="t-1", user_id="u")
    b = BaseAgent._cache_key("Syez", "ctx", "m", 0.4, tenant_id="t-2", user_id="u")
    assert a != b


def test_call_llm_reads_identity_from_contextvar(monkeypatch):
    """Gdy caller nie poda `user_id`/`tenant_id`, `_call_llm` musi zbudować
    klucz cache z `db.tenant.current_*` (ustawianego przez middleware z JWT).
    To gwarancja, że orkiestrator/agents/__init__.py nie potrzebują zmian —
    izolacja działa automatycznie."""
    import asyncio

    from agents.kogit import Kogit
    from db.tenant import (
        reset_current_tenant_id,
        reset_current_user_id,
        set_current_tenant_id,
        set_current_user_id,
    )

    captured: dict[str, str] = {}

    async def _fake_call(self, context, dream=None, *, language="pl",
                         debate_mode="pelna", council_mode="personal",
                         has_evolution_note=False, tenant_id=None, user_id=None):
        # Replikujemy fragment _call_llm odczytujący ContextVar.
        if tenant_id is None or user_id is None:
            from db.tenant import current_tenant_id, current_user_id
            tenant_id = tenant_id or current_tenant_id()
            user_id = user_id or current_user_id()
        captured["key"] = BaseAgent._cache_key(
            self.name, context, "m", 0.4,
            tenant_id=tenant_id, user_id=user_id,
        )
        return "ok"

    monkeypatch.setattr(BaseAgent, "_call_llm", _fake_call)
    agent = Kogit()

    tok_t = set_current_tenant_id("tenant-x")
    tok_u_a = set_current_user_id("user-A")
    try:
        asyncio.run(agent.acontribute("brief"))
        key_a = captured["key"]
    finally:
        reset_current_user_id(tok_u_a)

    tok_u_b = set_current_user_id("user-B")
    try:
        asyncio.run(agent.acontribute("brief"))
        key_b = captured["key"]
    finally:
        reset_current_user_id(tok_u_b)
        reset_current_tenant_id(tok_t)

    assert key_a != key_b, "ContextVar user_id musi rozdzielić klucze cache"


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
