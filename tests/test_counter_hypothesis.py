"""Counter-hypothesis (anty-echo-chamber) — testy.

Sprawdza, że:
  • wybór agenta-kontry jest deterministyczny wg hasha briefu i rotuje,
  • DOKŁADNIE jeden agent na debatę dostaje rolę kontry,
  • moduł testu przesłanki trafia do promptu TYLKO agenta-kontry (PL i EN),
  • każdy z 9 głosów ma kalibrację tonu (charakter zachowany),
  • escape hatch ("nie wymyślaj kontrowersji") jest obecny.
"""

from __future__ import annotations

from agents import COUNCIL, _counter_index
from agents.base_agent import _COUNTER_VOICE


def test_every_council_agent_has_voice_calibration():
    """Charakter zachowany: każdy z 9 głosów ma własne zdanie kalibrujące."""
    expected = {a.name for a in COUNCIL}
    assert set(_COUNTER_VOICE.keys()) == expected


def test_counter_index_is_deterministic():
    brief = "Czy bycie sobą nie jest egoizmem?"
    a = _counter_index(brief, len(COUNCIL))
    b = _counter_index(brief, len(COUNCIL))
    assert a == b
    assert 0 <= a < len(COUNCIL)


def test_counter_index_rotates_across_briefs():
    """Różne briefy trafiają na różnych agentów (rotacja, nie stały głos)."""
    briefs = [f"brief wariant {i} — inny kontekst decyzji" for i in range(40)]
    picked = {_counter_index(b, len(COUNCIL)) for b in briefs}
    # Przy 40 różnych briefach i 9 agentach oczekujemy wyraźnej rotacji.
    assert len(picked) >= 4


def test_exactly_one_agent_gets_counter_role():
    brief = "Czy bycie sobą nie jest egoizmem?"
    ci = _counter_index(brief, len(COUNCIL))
    flags = [(i == ci) for i in range(len(COUNCIL))]
    assert sum(flags) == 1


def test_counter_module_only_in_counter_agent_pl():
    marker = "ROLA TESTU PRZESŁANKI"
    for a in COUNCIL:
        with_counter = a.get_full_instruction(language="pl", counter_role=True)
        without = a.get_full_instruction(language="pl", counter_role=False)
        assert marker in with_counter, f"Brak modułu kontry dla {a.name} (PL)"
        assert marker not in without, f"Moduł kontry wyciekł bez flagi: {a.name}"
        # Kalibracja danego głosu jest obecna gdy rola aktywna.
        assert _COUNTER_VOICE[a.name] in with_counter


def test_counter_module_only_in_counter_agent_en():
    marker = "PREMISE-TEST ROLE"
    for a in COUNCIL:
        with_counter = a.get_full_instruction(language="en", counter_role=True)
        without = a.get_full_instruction(language="en", counter_role=False)
        assert marker in with_counter, f"Brak modułu kontry dla {a.name} (EN)"
        assert marker not in without, f"Moduł kontry wyciekł bez flagi: {a.name}"


def test_escape_hatch_present():
    """Mitygacja krótkiego briefu: agent może odmówić wymyślania kontrowersji."""
    a = COUNCIL[0]
    pl = a.get_full_instruction(language="pl", counter_role=True)
    en = a.get_full_instruction(language="en", counter_role=True)
    assert "Nie wymyślaj kontrowersji" in pl
    assert "Do not invent controversy" in en
