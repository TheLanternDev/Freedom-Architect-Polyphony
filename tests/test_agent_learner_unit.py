"""Testy `core.agent_learner` — Faza 3 (rolling notatka ewolucyjna)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core import agent_learner as al


# ── extract_evolution_snippet ────────────────────────────────────────────────


def test_snippet_returns_empty_for_short_text():
    assert al.extract_evolution_snippet("Kogit", "short") == ""
    assert al.extract_evolution_snippet("Kogit", "") == ""


def test_snippet_single_sentence_returned_as_is():
    text = "To jest jedno zdanie ale wystarczająco długie żeby przejść próg."
    out = al.extract_evolution_snippet("Kogit", text)
    assert out == text.strip()


def test_snippet_first_and_last_when_multiple_sentences():
    text = (
        "Pierwsze zdanie z konkretną obserwacją początkową. "
        "Drugie zdanie środkowe które powinno zostać pominięte całkowicie. "
        "Ostatnie zdanie z wnioskiem końcowym tego głosu agenta."
    )
    out = al.extract_evolution_snippet("Kogit", text)
    assert "Pierwsze zdanie" in out
    assert "Ostatnie zdanie" in out
    assert "(...)" in out
    # Środkowe zdanie pominięte.
    assert "Drugie zdanie" not in out


def test_snippet_truncated_if_too_long(monkeypatch):
    monkeypatch.setattr(al, "SNIPPET_TARGET_LEN", 50)
    text = "x" * 200 + ". " + "y" * 200 + "."
    out = al.extract_evolution_snippet("Kogit", text)
    assert len(out) <= 50
    assert out.endswith("...")


def test_snippet_filters_too_short_sentence_fragments():
    """Po `re.split` odrzucone są fragmenty <=10 znaków."""
    text = "OK. Nie. To jest pełne zdanie obserwacyjne z dłuższą treścią."
    out = al.extract_evolution_snippet("Kogit", text)
    # "OK" i "Nie" odpadną — wybierane jest tylko pełne zdanie.
    assert "OK" not in out
    assert "pełne zdanie obserwacyjne" in out


# ── merge_evolution_notes ────────────────────────────────────────────────────


def test_merge_returns_existing_when_new_empty():
    existing = "[2026-05-01] stary wpis"
    assert al.merge_evolution_notes(existing, "") == existing
    assert al.merge_evolution_notes(existing, "   ") == existing


def test_merge_appends_with_date_prefix():
    out = al.merge_evolution_notes("", "nowa obserwacja")
    assert "nowa obserwacja" in out
    # Format: [YYYY-MM-DD] snippet
    assert out.startswith("[20")


def test_merge_caps_at_max_snippets(monkeypatch):
    monkeypatch.setattr(al, "MAX_SNIPPETS_PER_AGENT", 3)
    note = ""
    for i in range(5):
        note = al.merge_evolution_notes(note, f"snippet-{i}")
    lines = [l for l in note.split("\n") if l.strip()]
    assert len(lines) == 3
    # FIFO: pierwsze odpadły, najnowsze zostają.
    assert "snippet-0" not in note
    assert "snippet-4" in note


def test_merge_caps_at_max_length(monkeypatch):
    monkeypatch.setattr(al, "MAX_EVOLUTION_NOTE_LEN", 80)
    monkeypatch.setattr(al, "MAX_SNIPPETS_PER_AGENT", 100)
    note = ""
    for i in range(20):
        note = al.merge_evolution_notes(note, f"snippet-numer-{i:02d}-z-dłuższą-treścią")
    assert len(note) <= 200  # luźny upper bound — algorytm zostawia ≥3 linie
    # Najnowsze zostają.
    assert "snippet-numer-19" in note


# ── rebuild_evolution_for_agent ──────────────────────────────────────────────


def test_rebuild_returns_empty_when_repo_method_missing():
    """Brak `list_recent_voices_for_agent` w repo → graceful degradation."""
    repo = MagicMock(spec=[])  # nie ma żadnej metody
    db = MagicMock()
    out = asyncio.run(al.rebuild_evolution_for_agent(db, "Kogit", repo))
    assert out == ""


def test_rebuild_builds_note_from_voices():
    voices = [
        {"voice_text": "Pierwszy głos Kogita z konkretną obserwacją początkową. Też z ostatnim zdaniem."},
        {"voice_text": "Drugi głos Kogita z innym wnioskiem dłuższym. Drugie zakończenie."},
        {"voice_text": "krótki"},  # poniżej progu — odrzucony
    ]
    repo = MagicMock()
    repo.list_recent_voices_for_agent = AsyncMock(return_value=voices)
    db = MagicMock()
    out = asyncio.run(al.rebuild_evolution_for_agent(db, "Kogit", repo, max_debates=10))
    assert "Pierwszy głos" in out
    assert "Drugi głos" in out


# ── run_full_evolution_cycle ────────────────────────────────────────────────


def test_full_cycle_merges_per_agent_and_persists():
    voices = [
        {"voice_text": "Głos pełny z konkretną treścią i finalnym podsumowaniem na końcu."},
    ]
    repo = MagicMock()
    repo.list_recent_voices_for_agent = AsyncMock(return_value=voices)
    repo.merge_agent_evolution_snippet = AsyncMock()
    db = MagicMock()

    out = asyncio.run(al.run_full_evolution_cycle(db, repo, ["Kogit", "Szow"]))

    assert set(out.keys()) == {"Kogit", "Szow"}
    # Każdy agent dostał wywołanie persist.
    assert repo.merge_agent_evolution_snippet.await_count == 2


def test_full_cycle_skips_agents_without_voices():
    """Gdy `rebuild` zwraca '' → nie woła `merge_agent_evolution_snippet`."""
    repo = MagicMock()
    repo.list_recent_voices_for_agent = AsyncMock(return_value=[])
    repo.merge_agent_evolution_snippet = AsyncMock()
    db = MagicMock()

    out = asyncio.run(al.run_full_evolution_cycle(db, repo, ["Kogit"]))
    assert out == {}
    repo.merge_agent_evolution_snippet.assert_not_awaited()
