"""
Druga tura konfrontacji Rady (prototyp, za flagą AW_COUNCIL_DEBATE_ROUNDS).

Decyzja Rady 2026-05-25: tylko tryby `pełny`/`schematy`, opt-in przez ENV,
pełna wsteczna zgodność (brak flagi lub =1 → zachowanie obecne, zero zmian).

Zasada: po turze monologów każdy agent dostaje 2–3 NAJBARDZIEJ skonfliktowane
z nim głosy (z istniejącego compute_live_pair_frictions) i ma prawo docisnąć,
zrewidować albo przyznać rację. Dopiero te głosy idą do Syeza. Napięcia, które
dziś tylko się wizualizuje, zaczynają pracować.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Tryby, w których konfrontacja jest dozwolona (decyzja Rady).
# Kanoniczna nazwa trybu pełnego to `pelna` (db/schema.sql CHECK +
# business_fa2/config/modes.VALID_MODES + Literal w main.py).
_CONFRONTATION_MODES: frozenset[str] = frozenset({"pelna", "schematy"})


def debate_rounds() -> int:
    """Liczba tur debaty z ENV. Default 1 (= obecne zachowanie)."""
    try:
        n = int((os.getenv("AW_COUNCIL_DEBATE_ROUNDS") or "1").strip())
    except ValueError:
        return 1
    return 2 if n >= 2 else 1


def confrontation_enabled(mode: str) -> bool:
    """Czy tryb i flaga ENV w ogóle dopuszczają drugą turę (warunek konieczny)."""
    return debate_rounds() >= 2 and mode in _CONFRONTATION_MODES


def tension_threshold() -> float:
    """Próg „high-stakes" z ENV `AW_CONFRONTATION_TENSION_MIN` (domyślnie 0.66).

    Intensywność par z compute_live_pair_frictions mieści się w 0.22–1.0;
    ~0.66 oznacza wyraźne rozjechanie głosów. Clamp do [0, 1]."""
    try:
        v = float((os.getenv("AW_CONFRONTATION_TENSION_MIN") or "0.66").strip())
    except ValueError:
        return 0.66
    return min(1.0, max(0.0, v))


def tensions_exceed_threshold(
    pairs: list[dict[str, Any]], threshold: float | None = None
) -> bool:
    """True, gdy najsilniejsza para napięć osiąga próg. Pusta lista → False
    (rutynowa debata zostaje jednorundowa)."""
    if not pairs:
        return False
    thr = tension_threshold() if threshold is None else threshold
    top = max(float(p.get("intensity", 0.0)) for p in pairs)
    return top >= thr


def should_confront(
    mode: str, pairs: list[dict[str, Any]], threshold: float | None = None
) -> bool:
    """Bramka „high-stakes": druga tura tylko gdy tryb+flaga ją dopuszczają
    ORAZ napięcia rundy 1 przekraczają próg. W przeciwnym razie debata
    pozostaje jednorundowa."""
    return confrontation_enabled(mode) and tensions_exceed_threshold(pairs, threshold)


def top_opponents_for(
    agent_name: str,
    pairs: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> list[str]:
    """Z posortowanych par napięć zwraca nazwy najsilniej skonfliktowanych
    z `agent_name` (pairs są już sortowane malejąco po intensity)."""
    out: list[str] = []
    for p in pairs:
        a, b = p.get("a"), p.get("b")
        other = b if a == agent_name else (a if b == agent_name else None)
        if other and other not in out:
            out.append(other)
        if len(out) >= limit:
            break
    return out


def build_confrontation_context(
    agent_name: str,
    own_voice: str,
    opponents: list[str],
    full_voices: dict[str, str],
    *,
    language: str = "pl",
) -> str:
    """Składa kontekst drugiej tury: własny głos + głosy przeciwników + dyrektywa."""
    opp_block = "\n\n".join(
        f"[{name}]\n{full_voices.get(name, '').strip()}"
        for name in opponents
        if full_voices.get(name, "").strip()
    )
    if language == "en":
        return (
            "[CONFRONTATION ROUND — your first take]\n"
            f"{own_voice.strip()}\n\n"
            "[VOICES MOST IN TENSION WITH YOURS]\n"
            f"{opp_block}\n\n"
            "═══════════════════\n"
            "Respond to the friction directly: press harder where you hold your "
            "ground, OR consciously revise your stance, OR concede a point. Do NOT "
            "merely repeat your first take. Stay in character. Max 3 sentences."
        )
    return (
        "[TURA KONFRONTACJI — Twój pierwszy głos]\n"
        f"{own_voice.strip()}\n\n"
        "[GŁOSY NAJBARDZIEJ SKONFLIKTOWANE Z TWOIM]\n"
        f"{opp_block}\n\n"
        "═══════════════════\n"
        "Odnieś się WPROST do tarcia: dociśnij tam, gdzie trzymasz stanowisko, "
        "ALBO świadomie je zrewiduj, ALBO przyznaj rację. NIE powtarzaj tylko "
        "pierwszego głosu. Pozostań w roli. Maksymalnie 3 zdania."
    )
