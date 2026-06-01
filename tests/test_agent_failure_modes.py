"""Per-agent failure mode injection — testy.

Sprawdza, że KAŻDY z 9 agentów Rady + Syez dostaje w system prompt
linijkę o swoim charakterystycznym błędzie. Bez tego cross-cutting
higiena rozumowania jest za generyczna.
"""

from __future__ import annotations

import pytest

from agents import COUNCIL, SYNTHESIZER
from agents.base_agent import _AGENT_FAILURE_MODES_PL, _AGENT_FAILURE_MODES_EN


def test_every_council_agent_and_syez_has_failure_mode_defined():
    expected = {a.name for a in COUNCIL} | {"Syez"}
    assert set(_AGENT_FAILURE_MODES_PL.keys()) == expected
    assert set(_AGENT_FAILURE_MODES_EN.keys()) == expected


def test_failure_mode_is_injected_into_system_prompt_pl():
    """Każdy agent w trybie personal/PL dostaje swoją linijkę failure mode."""
    for a in COUNCIL:
        prompt = a.get_full_instruction(language="pl", council_mode="personal")
        expected = _AGENT_FAILURE_MODES_PL[a.name]
        assert expected in prompt, f"Brak failure mode dla {a.name} w PL prompt"


def test_failure_mode_is_injected_into_system_prompt_en():
    for a in COUNCIL:
        prompt = a.get_full_instruction(language="en", council_mode="personal")
        expected = _AGENT_FAILURE_MODES_EN[a.name]
        assert expected in prompt, f"Brak failure mode dla {a.name} w EN prompt"


def test_failure_mode_works_in_fa2_mode():
    """W fa2 też injectujemy — analitycy biznesowi mają tę samą charakterystykę."""
    for a in COUNCIL:
        prompt = a.get_full_instruction(language="pl", council_mode="fa2")
        expected = _AGENT_FAILURE_MODES_PL[a.name]
        assert expected in prompt, f"Brak failure mode dla {a.name} w fa2 prompt"


def test_failure_mode_distinct_per_agent():
    """Failure mode jednego agenta nie pojawia się w prompt drugiego."""
    kogit = next(a for a in COUNCIL if a.name == "Kogit")
    szow = next(a for a in COUNCIL if a.name == "Szow")
    kogit_prompt = kogit.get_full_instruction(language="pl", council_mode="personal")
    szow_prompt = szow.get_full_instruction(language="pl", council_mode="personal")
    assert _AGENT_FAILURE_MODES_PL["Szow"] not in kogit_prompt
    assert _AGENT_FAILURE_MODES_PL["Kogit"] not in szow_prompt


def test_calibration_extension_present_in_hygiene_pl():
    """Higiena rozumowania zawiera teraz prośbę o calibration of confidence."""
    kogit = next(a for a in COUNCIL if a.name == "Kogit")
    prompt = kogit.get_full_instruction(language="pl", council_mode="personal")
    assert "podniosłaby ALBO obniżyła" in prompt
    assert "motivated reasoning" in prompt


def test_calibration_extension_present_in_hygiene_en():
    kogit = next(a for a in COUNCIL if a.name == "Kogit")
    prompt = kogit.get_full_instruction(language="en", council_mode="personal")
    assert "raise OR lower your confidence" in prompt


def test_syez_failure_mode_addresses_non_merging():
    """Kluczowa zmiana — Syez NIE uśrednia konfliktów."""
    syez_pl = _AGENT_FAILURE_MODES_PL["Syez"]
    syez_en = _AGENT_FAILURE_MODES_EN["Syez"]
    assert "uśredniasz" in syez_pl.lower() or "konflikt" in syez_pl.lower()
    assert "NAZWIJ" in syez_pl
    assert "NAME the conflict" in syez_en
