"""Checkpoint 2 — dystylator Obrazu Użytkownika + wstrzykiwanie (bez LLM)."""

from __future__ import annotations

import asyncio

import pytest

from agents.syez import Syez
from core import obraz_uzytkownika as ou
from core.obraz_uzytkownika import (
    ObrazUzytkownika,
    adistill_obraz,
    set_obraz_context,
)


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Wymuś deterministyczny fallback — zero wywołań LLM/kredytów."""
    monkeypatch.setattr(ou, "effective_llm_backend", lambda: "none")
    yield
    set_obraz_context(None)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_fallback_maps_sections_and_preserves_raw_quote():
    answers = [
        {"question_idx": 14, "answer": "Nie zgodzę się na kłamstwo."},   # Wartości
        {"question_idx": 18, "answer": "Rysuję do szuflady."},            # Kreatywność
        {"question_idx": 20, "answer": "Pokora wobec gór."},              # Duchowość
        {"question_idx": 22, "answer": "Spokoju i snu."},                 # Cisza[0]
        {"question_idx": 23, "answer": "Jesteś już wystarczający."},      # Cisza[1]
    ]
    o = _run(adistill_obraz(answers, wersja=3))
    assert "Nie zgodzę się na kłamstwo." in o.wartosci
    assert "Rysuję do szuflady." in o.kreatywnosc
    assert "Pokora wobec gór." in o.duchowosc
    assert o.potrzeba_teraz == "Spokoju i snu."
    # zdanie_dla_siebie — DOSŁOWNY cytat, nie parafraza
    assert o.zdanie_dla_siebie == "Jesteś już wystarczający."
    assert o.wersja == 3


def test_empty_answers_give_empty_obraz():
    o = _run(adistill_obraz([], wersja=1))
    assert o.is_empty()
    assert o.as_agent_context() == ""


def test_as_agent_context_has_limit_and_quote():
    o = ObrazUzytkownika(
        wartosci=["w" * 500],
        zdanie_dla_siebie="Wróć do siebie.",
        cialo="napięcie w barkach",
    )
    ctx = o.as_agent_context()
    assert "OBRAZ UŻYTKOWNIKA" in ctx
    assert "Wróć do siebie." in ctx
    assert len(ctx) <= ou._MAX_CONTEXT_CHARS  # twardy limit sygnału


def test_injection_personal_yes_fa2_no():
    set_obraz_context("=== OBRAZ TESTOWY ===")
    s = Syez()
    personal = s.get_full_instruction(council_mode="personal", dream=None)
    fa2 = s.get_full_instruction(council_mode="fa2", language="pl")
    assert "OBRAZ TESTOWY" in personal       # personal: wstrzyknięty
    assert "OBRAZ TESTOWY" not in fa2          # fa2: poza zakresem onboardingu


def test_injection_absent_when_context_none():
    set_obraz_context(None)
    out = Syez().get_full_instruction(council_mode="personal", dream=None)
    assert "OBRAZ UŻYTKOWNIKA" not in out
