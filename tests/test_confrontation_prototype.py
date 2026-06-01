"""
Prototyp + test porównawczy drugiej tury konfrontacji (decyzja Rady 2026-05-25).

Cel: udowodnić RÓŻNICĘ jakości bez palenia kredytów — fake-agenci deterministyczni.
Sprawdzamy logikę selekcji przeciwników, budowy kontekstu, wsteczną zgodność
oraz mierzalny koszt (liczba dodatkowych wywołań LLM).

Test porównawczy (1 runda vs 2 rundy) na tym samym briefie: patrz
`test_confrontation_changes_voices_fed_to_syez` — pokazuje, że do Syeza trafiają
ZREWIDOWANE głosy, nie pierwsze monologi.
"""

import os

import pytest

from api.services.confrontation import (
    build_confrontation_context,
    confrontation_enabled,
    debate_rounds,
    should_confront,
    tensions_exceed_threshold,
    top_opponents_for,
)


# ── Wsteczna zgodność (kluczowy wymóg Rady) ──────────────────────────────────


def test_default_is_single_round(monkeypatch):
    monkeypatch.delenv("AW_COUNCIL_DEBATE_ROUNDS", raising=False)
    assert debate_rounds() == 1
    assert confrontation_enabled("pełny") is False  # brak flagi → zero zmian


def test_invalid_env_falls_back_to_one(monkeypatch):
    monkeypatch.setenv("AW_COUNCIL_DEBATE_ROUNDS", "garbage")
    assert debate_rounds() == 1


def test_enabled_only_for_full_modes(monkeypatch):
    monkeypatch.setenv("AW_COUNCIL_DEBATE_ROUNDS", "2")
    assert confrontation_enabled("pelna") is True   # kanoniczna nazwa (db CHECK)
    assert confrontation_enabled("schematy") is True
    assert confrontation_enabled("codzienny") is False  # decyzja Rady: nie codzienny


def test_tensions_exceed_threshold_empty_pairs():
    assert tensions_exceed_threshold([]) is False


def test_tensions_exceed_threshold_uses_max_intensity():
    pairs = [{"a": "Szow", "b": "Tai", "intensity": 0.5}]
    assert tensions_exceed_threshold(pairs, threshold=0.66) is False
    assert tensions_exceed_threshold(pairs, threshold=0.4) is True


def test_should_confront_requires_mode_flag_and_tension(monkeypatch):
    monkeypatch.setenv("AW_COUNCIL_DEBATE_ROUNDS", "2")
    pairs = [{"a": "Szow", "b": "Relacjan", "intensity": 0.9}]
    assert should_confront("pelna", pairs) is True
    assert should_confront("codzienny", pairs) is False
    assert should_confront("pelna", []) is False


# ── Selekcja przeciwników z istniejących par napięć ──────────────────────────


def test_top_opponents_picks_highest_tension():
    pairs = [
        {"a": "Szow", "b": "Relacjan", "intensity": 0.9},
        {"a": "Szow", "b": "Smaty", "intensity": 0.7},
        {"a": "Kogit", "b": "Emojy", "intensity": 0.6},
        {"a": "Szow", "b": "Tai", "intensity": 0.3},
    ]
    opp = top_opponents_for("Szow", pairs, limit=2)
    assert opp == ["Relacjan", "Smaty"]  # po intensity, bez Tai (limit 2)


def test_top_opponents_empty_when_no_conflict():
    assert top_opponents_for("Obver", [{"a": "Szow", "b": "Tai", "intensity": 0.5}]) == []


# ── Kontekst konfrontacji zmusza do rewizji, nie powtórki ────────────────────


def test_confrontation_context_contains_opponents_and_directive():
    voices = {"Relacjan": "Liczy się więź, nie deadline.", "Smaty": "Liczby nie kłamią."}
    ctx = build_confrontation_context(
        "Szow", "Co tu chowasz?", ["Relacjan", "Smaty"], voices, language="pl"
    )
    assert "Liczy się więź" in ctx and "Liczby nie kłamią" in ctx
    assert "Twój pierwszy głos" in ctx
    assert "zrewiduj" in ctx.lower()  # dyrektywa rewizji obecna


# ── Test porównawczy 1 vs 2 rundy (rdzeń prototypu) ──────────────────────────


@pytest.mark.asyncio
async def test_confrontation_changes_voices_fed_to_syez():
    """Symulacja: agent w turze 2 REWIDUJE stanowisko po zobaczeniu przeciwnika.
    Dowodzimy, że Syez dostaje inny (zrewidowany) bundle niż w 1 rundzie."""
    llm_calls = {"n": 0}

    class _Agent:
        def __init__(self, name, take1, take2):
            self.name = name
            self._t1, self._t2 = take1, take2

        async def acontribute(self, context, **k):
            llm_calls["n"] += 1
            # Druga tura rozpoznawana po obecności nagłówka konfrontacji.
            return self._t2 if "TURA KONFRONTACJI" in context else self._t1

    council = [
        _Agent("Szow", "Chowasz strach przed oceną.", "Po Relacjanie widzę: to nie strach, to brak więzi. Rewiduję."),
        _Agent("Relacjan", "Liczy się więź, nie deadline.", "Trzymam: bez więzi projekt umrze."),
    ]
    pairs = [{"a": "Szow", "b": "Relacjan", "intensity": 0.9}]

    # Runda 1: monologi
    voices_r1 = {}
    for a in council:
        voices_r1[a.name] = await a.acontribute("brief")
    calls_after_r1 = llm_calls["n"]

    # Runda 2: konfrontacja (tylko ci z przeciwnikami)
    voices_r2 = dict(voices_r1)
    for a in council:
        opp = top_opponents_for(a.name, pairs)
        if opp:
            ctx = build_confrontation_context(a.name, voices_r1[a.name], opp, voices_r1)
            voices_r2[a.name] = await a.acontribute(ctx)
    extra_calls = llm_calls["n"] - calls_after_r1

    # DOWÓD różnicy: Szow zrewidował; bundle do Syeza inny niż w 1 rundzie.
    assert voices_r1["Szow"] != voices_r2["Szow"]
    assert "Rewiduję" in voices_r2["Szow"]
    # Koszt jawny i mierzalny: dokładnie +1 wywołanie na agenta z przeciwnikiem.
    assert extra_calls == 2  # obaj mieli przeciwnika
