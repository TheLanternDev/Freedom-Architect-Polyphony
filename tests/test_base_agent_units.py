"""Pure-function testy `agents.base_agent`: `_build_user_message`,
`_sanitize_syez_output`, `_calculate_cost`, `get_full_instruction`.

Mockujemy LLM client — testy NIE wywołują sieci.
"""

from __future__ import annotations

import pytest

from agents.base_agent import BaseAgent
from agents.kogit import Kogit
from agents.szow import Szow
from agents.syez import Syez


# ── _build_user_message ──────────────────────────────────────────────────────


def test_build_user_message_council_member_pl_starts_with_signature():
    a = Kogit()
    msg = a._build_user_message("brief X", language="pl", council_mode="personal")
    assert "brief X" in msg
    assert f"{a.emoji} {a.name}:" in msg
    # 3 zdania, format konkretu.
    assert "Maks. 3 zdania" in msg


def test_build_user_message_council_member_en_uses_english_rules():
    a = Kogit()
    msg = a._build_user_message("brief X", language="en", council_mode="personal")
    assert "brief X" in msg
    assert "Max 3 sentences" in msg
    assert f"{a.emoji} {a.name}:" in msg


def test_build_user_message_fa2_council_returns_business_template():
    a = Kogit()
    msg = a._build_user_message("brief X", language="pl", council_mode="fa2")
    assert "Zapytanie biznesowe" in msg
    assert "1–2 konkretne nisze" in msg
    assert f"{a.emoji} {a.name}:" in msg


def test_build_user_message_syez_personal_pl_demands_pure_prose():
    s = Syez()
    msg = s._build_user_message("context", language="pl", council_mode="personal")
    assert "CZYSTĄ POLSKĄ PROZĄ" in msg
    assert "ZAKAZ JSON" in msg
    assert "```mermaid" in msg


def test_build_user_message_syez_personal_en():
    s = Syez()
    msg = s._build_user_message("context", language="en", council_mode="personal")
    assert "PURE ENGLISH PROSE" in msg
    assert "monitor of tensions" in msg


def test_build_user_message_syez_fa2_demands_scenarios_and_diagram():
    s = Syez()
    msg = s._build_user_message("context", language="pl", council_mode="fa2")
    assert "SCENARIUSZ BASE" in msg
    assert "SCENARIUSZ BULL" in msg
    assert "SCENARIUSZ BEAR" in msg
    assert "diagram Mermaid" in msg.lower() or "Mermaid" in msg


def test_build_user_message_syez_fa2_en():
    s = Syez()
    msg = s._build_user_message("context", language="en", council_mode="fa2")
    assert "BASE SCENARIO" in msg
    assert "BULL SCENARIO" in msg
    assert "BEAR SCENARIO" in msg


# ── _sanitize_syez_output ────────────────────────────────────────────────────


def test_sanitize_passthrough_for_normal_prose():
    text = "Synteza w pełnej prozie z minimum trzydziestoma znakami treści."
    out = BaseAgent._sanitize_syez_output(text)
    assert text in out


def test_sanitize_preserves_mermaid_block():
    text = (
        "Synteza prozą z minimum trzydziestoma znakami treści żeby przeszło próg.\n\n"
        "```mermaid\nflowchart TD\nA-->B\n```\n\n"
        "Kontynuacja prozy."
    )
    out = BaseAgent._sanitize_syez_output(text)
    assert "```mermaid" in out
    assert "flowchart TD" in out
    assert "Kontynuacja prozy" in out


def test_sanitize_strips_json_fence():
    text = (
        "Synteza prozą z minimum trzydziestoma znakami treści żeby przeszło próg.\n"
        "```json\n{\"foo\": 1}\n```\n"
        "Dalsza proza."
    )
    out = BaseAgent._sanitize_syez_output(text)
    assert "```json" not in out
    assert "foo" not in out
    assert "Synteza prozą" in out
    assert "Dalsza proza" in out


def test_sanitize_strips_other_code_fences():
    text = (
        "Otwarcie syntezy w prozie po polsku z trzydziestoma znakami minimum.\n"
        "```python\nx = 1\n```\n"
        "Zakończenie."
    )
    out = BaseAgent._sanitize_syez_output(text)
    assert "```python" not in out
    assert "Otwarcie syntezy" in out
    assert "Zakończenie" in out


def test_sanitize_strips_naked_json_object():
    text = (
        "Otwarcie syntezy w prozie po polsku z trzydziestoma znakami minimum.\n"
        '{"completion_audit": {"foo": 1}}\n'
        "Zamknięcie syntezy w prozie po polsku."
    )
    out = BaseAgent._sanitize_syez_output(text)
    assert "completion_audit" not in out
    assert "Otwarcie syntezy" in out


def test_sanitize_returns_graceful_message_for_empty_after_strip():
    text = '```json\n{"x": 1}\n```'
    out = BaseAgent._sanitize_syez_output(text)
    assert "Synteza nie została wygenerowana" in out


def test_sanitize_keeps_diagram_only_when_prose_too_short():
    """Sam diagram bez prozy — nadal zachowany (diagram jest wartościową treścią)."""
    text = "```mermaid\nflowchart\nA-->B\n```"
    out = BaseAgent._sanitize_syez_output(text)
    assert "```mermaid" in out
    # Nie graceful degradation.
    assert "Synteza nie została wygenerowana" not in out


def test_sanitize_empty_input_returns_empty():
    assert BaseAgent._sanitize_syez_output("") == ""


# ── _calculate_cost (rozszerzenie istniejących) ──────────────────────────────


def test_cost_unknown_xai_model():
    """Pełny `_calculate_cost` dla xAI z cennikiem."""
    cost = BaseAgent._calculate_cost("grok-3", 1_000_000, 1_000_000)
    assert cost == pytest.approx(18.0)  # 3 + 15


def test_cost_grok_3_mini():
    cost = BaseAgent._calculate_cost("grok-3-mini", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.8)  # 0.3 + 0.5


# ── get_full_instruction (lekkie, bez LLM) ───────────────────────────────────


def test_get_full_instruction_personal_pl_contains_postscript_and_directive():
    a = Kogit()
    out = a.get_full_instruction(language="pl", council_mode="personal")
    assert "DYREKTYWA JĘZYKOWA" in out
    assert "Odpowiadaj WYŁĄCZNIE po polsku" in out
    # Higiena rozumowania — Rada (poza Syez).
    assert "Higiena rozumowania" in out


def test_get_full_instruction_personal_en():
    a = Kogit()
    out = a.get_full_instruction(language="en", council_mode="personal")
    assert "LANGUAGE DIRECTIVE" in out
    assert "Respond ONLY in fluent, natural English" in out
    assert "Reasoning hygiene" in out


def test_get_full_instruction_fa2_council_member_includes_business_anchor():
    a = Kogit()
    out = a.get_full_instruction(language="pl", council_mode="fa2")
    assert "Rady Nadzorczej Architekta Wolności" in out
    assert "TRYB FREEDOM ARCHITECT" in out


def test_get_full_instruction_szow_fa2_includes_steelman_directive():
    """Szow w fa2 dostaje dodatkowo wymóg steelmana przed cięciem."""
    s = Szow()
    out = s.get_full_instruction(language="pl", council_mode="fa2")
    assert "najmocniejszą wersję" in out


def test_get_full_instruction_evolution_note_directive_when_present():
    a = Kogit()
    out = a.get_full_instruction(language="pl", council_mode="personal",
                                 has_evolution_note=True)
    assert "notatka ewolucyjna" in out
