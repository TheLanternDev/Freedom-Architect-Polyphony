"""Faza 1 — jedno źródło prawdy dla protokołu Syeza FA2 (#A/#B).

Snapshot bez LLM: protokół FA2 żyje WYŁĄCZNIE w instrukcji systemowej
(`FA2_SYEZ_INSTRUCTION_PL` / `_EN`), a user-message jedynie go wywołuje.
Pilnuje obecności kotwic „Jeden krok teraz:" / „One step now:" oraz
jawnego wskazania najsłabszego ogniwa w obu językach.
"""

from __future__ import annotations

from agents.syez import Syez


def _sys(language: str) -> str:
    return Syez().get_full_instruction(council_mode="fa2", language=language)


def test_fa2_system_pl_has_protocol_anchors():
    s = _sys("pl")
    assert "PROTOKÓŁ FA2" in s
    assert "Jeden krok teraz:" in s
    assert "Najsłabsze ogniwo" in s
    assert "800–1400" in s  # ujednolicona długość (jedno źródło)


def test_fa2_system_en_has_protocol_anchors():
    s = _sys("en")
    assert "FA2 PROTOCOL" in s
    assert "One step now:" in s
    assert "Weakest link" in s
    assert "800–1400" in s


def test_fa2_user_message_only_invokes_protocol_pl():
    msg = Syez()._build_user_message("BRIEF", language="pl", council_mode="fa2")
    assert "BRIEF" in msg
    assert "protokołu FA2" in msg
    assert "Jeden krok teraz:" in msg
    # drugi, rozjeżdżający się zestaw kroków usunięty
    assert "ZASADY SYNTEZY FA2" not in msg
    assert "800–1600" not in msg


def test_fa2_user_message_only_invokes_protocol_en():
    msg = Syez()._build_user_message("BRIEF", language="en", council_mode="fa2")
    assert "BRIEF" in msg
    assert "FA2 protocol" in msg
    assert "One step now:" in msg
    assert "SYNTHESIS RULES" not in msg
    assert "800–1600" not in msg
