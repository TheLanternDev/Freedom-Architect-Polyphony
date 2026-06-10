"""Pure-function testy `api.services.debate_orchestrator`:
selektory, builders kontekstu, chunkers, JSON parsery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from api.services import debate_orchestrator as orch


@dataclass
class _Brief:
    language: str = "pl"
    mode: str = "pelna"
    category: str = "personal"
    description: str = "brief X"
    intention: Optional[str] = None
    extra_context: Optional[str] = None
    scale: Optional[str] = None
    budget: Optional[str] = None


# ── select_council_for_mode ──────────────────────────────────────────────────


def test_select_full_council_for_pelna_mode():
    out = orch.select_council_for_mode("pelna")
    # Pełna Rada = 9 głosów (Kogit, Szow, Kidi, Tai, Obver, Relacjan, Emojy, Smaty, Deega).
    assert len(out) == 9
    names = {a.name for a in out}
    assert "Szow" in names and "Deega" in names


def test_select_codzienny_returns_light_subset():
    out = orch.select_council_for_mode("codzienny")
    names = {a.name for a in out}
    # Jedno źródło prawdy: modes.MODE_AGENTS (nie zduplikowana stała w orchestratorze).
    from modes import MODE_AGENTS

    assert names == set(MODE_AGENTS["codzienny"])


def test_select_unknown_mode_returns_full_council():
    """Tryb spoza listy → fallback pełna Rada (default-safe)."""
    out = orch.select_council_for_mode("unknown-mode")
    assert len(out) == 9


# ── build_council_context ────────────────────────────────────────────────────


def test_build_context_minimal_brief():
    out = orch.build_council_context(_Brief())
    assert "brief X" in out
    assert "personal" in out
    assert "pelna" in out
    assert "Intencja" not in out  # nieobecne


def test_build_context_with_intention_and_extra():
    b = _Brief(intention="I want X", extra_context="bo Y")
    out = orch.build_council_context(b)
    assert "Intencja: I want X" in out
    assert "Dodatkowy kontekst: bo Y" in out


def test_build_context_legacy_scale_and_budget():
    b = _Brief(scale="osobiście", budget="1000 PLN")
    out = orch.build_council_context(b)
    assert "Skala: osobiście" in out
    assert "Budżet: 1000 PLN" in out


def test_build_context_no_legacy_block_when_both_empty():
    out = orch.build_council_context(_Brief())
    assert "(legacy)" not in out


# ── chunk_words ──────────────────────────────────────────────────────────────


def test_chunk_words_empty_input():
    assert orch.chunk_words("") == []
    assert orch.chunk_words("   ") == []


def test_chunk_words_groups_of_5():
    text = "one two three four five six seven"
    out = orch.chunk_words(text, group=5)
    assert len(out) == 2
    assert out[0] == "one two three four five "
    assert out[1] == "six seven"


def test_chunk_words_custom_group_size():
    text = "a b c d e f g h"
    out = orch.chunk_words(text, group=3)
    assert out == ["a b c ", "d e f ", "g h"]


def test_chunk_words_single_word():
    assert orch.chunk_words("hello") == ["hello"]


# ── _agent_evolution_enabled ────────────────────────────────────────────────


def test_agent_evolution_default_enabled(monkeypatch):
    monkeypatch.delenv("AW_AGENT_EVOLUTION", raising=False)
    assert orch._agent_evolution_enabled() is True


def test_agent_evolution_disabled_by_env(monkeypatch):
    for val in ("0", "false", "FALSE", "no", "off"):
        monkeypatch.setenv("AW_AGENT_EVOLUTION", val)
        assert orch._agent_evolution_enabled() is False, f"failed for {val!r}"


def test_agent_evolution_enabled_for_other_values(monkeypatch):
    monkeypatch.setenv("AW_AGENT_EVOLUTION", "1")
    assert orch._agent_evolution_enabled() is True


# ── _extract_json_block + _try_parse_synthesis_json ──────────────────────────


def test_extract_json_block_returns_block():
    text = 'Preamble\n{"foo": "bar"}\nPostamble'
    out = orch._extract_json_block(text)
    assert out == '{"foo": "bar"}'


def test_extract_json_block_returns_none_when_no_json():
    assert orch._extract_json_block("pure prose, no braces") is None


def test_try_parse_synthesis_json_returns_dict():
    out = orch._try_parse_synthesis_json('Synteza...\n{"completion_audit": {}}')
    assert isinstance(out, dict)
    assert "completion_audit" in out


def test_try_parse_synthesis_json_returns_none_for_invalid():
    assert orch._try_parse_synthesis_json("brak JSON-a tutaj") is None


def test_try_parse_synthesis_json_returns_none_for_array():
    """JSON array NIE jest dict — odrzucone."""
    out = orch._try_parse_synthesis_json("ctx\n[1, 2, 3]")
    assert out is None
