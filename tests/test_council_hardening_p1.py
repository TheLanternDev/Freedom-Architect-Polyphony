"""
Testy regresyjne dla utwardzenia Rady (P1, ustalenia #1–#4 z code-review).

Każdy test BRONI jednej poprawki — bez nich łatwo o cichą regresję:
  #1  Próg audytu prozy A2 nie da się oszukać samym pytajnikiem + słowami-kluczami.
  #2  Orchestrator i core używają TEJ SAMEJ logiki ekstrakcji JSON (balansowanie).
  #3  Błąd agenta NIE trafia do Syeza jako pełnoprawny głos (degradacja widoczna).
  #4  Cache marzeń jest scope'owany per tenant (brak współdzielenia w pamięci).
"""

import pytest

from core.completion_enforcer import (
    CompletionViolation,
    validate_syez_prose_completion_audit,
)


# ── #1: próg audytu A2 odporny na oszukanie ──────────────────────────────────


def test_prose_audit_rejects_question_mark_only_attack():
    """Atak: >400 zn., słowa z 2–3 klastrów + sam pytajnik, ale BEZ rdzenia
    (remaining + next_move). Stage 2: próg podniesiony do 400 zn. — atak też
    musi być dłuższy, żeby testował walidację sygnałów, nie samą długość."""
    attack = (
        "Czuję pewien opór oraz niepewność w tym module projektu, co napina "
        "wewnętrzny stan decyzyjny i utrudnia pracę. To jest celowo wydłużony, "
        "neutralny akapit dopełniający limit czterystu znaków, pozbawiony "
        "jakiegokolwiek konkretnego ruchu do wykonania w określonym czasie. "
        "Wewnętrzna blokada jest odczuwalna, lecz nie wskazuje żadnej konkretnej akcji. "
        "Napięcie narasta, a pytanie otwarte wisi w powietrzu bez odpowiedzi. "
        "A czy to wszystko brzmi wystarczająco diagnostycznie jak synteza Syeza?"
    )
    with pytest.raises(CompletionViolation) as exc:
        validate_syez_prose_completion_audit(attack)
    assert exc.value.kind == "prose_audit_signals_weak"


def test_prose_audit_requires_core_clusters_remaining_and_next():
    """Brak `next_move` (rdzeń) → odrzucenie, nawet gdy reszta sygnałów jest."""
    # Uwaga: tekst CELOWO unika słów z _CLUSTER_NEXT (najmniejsz / min / dziś /
    # krok / zrób...). Ma remaining + blokadę + pytanie, ale brak next_move.
    no_next = (
        "Na checklistie funkcjonalności została jeszcze jedna pozycja do odhaczenia. "
        "Blokuje ją brak decyzji o architekturze danych oraz wewnętrzny opór. "
        "To rozbudowany akapit przekraczający dwieście znaków, opisujący ogólny stan "
        "sprawy bez wskazania, co dokładnie wykonać. Czy widzisz tutaj jakieś wyjście?"
    )
    with pytest.raises(CompletionViolation):
        validate_syez_prose_completion_audit(no_next)


def test_prose_audit_still_passes_real_synthesis():
    """Realna synteza (remaining + blokada + 45 min + pytania) nadal przechodzi.
    Stage 2: tekst rozszerzony do ≥400 zn. — PROSE_AUDIT_MIN_CHARS podniesiono."""
    ok = (
        "Na checklistie funkcjonalności zostały jeszcze dwie pozycje do odhaczenia: "
        "widok onboardingu i moduł powiadomień. Pierwszą blokuje brak decyzji "
        "o kolorystyce i tonie komunikacji, drugą blokuje nierozstrzygnięta architektura "
        "kolejki zdarzeń. Najmniejszy konkretny ruch na dziś to przygotować jeden "
        "szkic widoku onboardingu w ciągu 45 minut — bez oczekiwania na resztę. "
        "Domykamy audyt z pełną świadomością obu blokad. "
        "Co jest dla Ciebie najcięższe w tym kroku? Jak zmienia się priorytet?"
    )
    validate_syez_prose_completion_audit(ok)  # nie rzuca


# ── #2: jedno źródło prawdy dla ekstrakcji JSON ──────────────────────────────


def test_orchestrator_json_extraction_uses_core_balancing():
    """Orchestrator musi balansować nawiasy tak jak core — JSON z `}` w treści
    pola był obcinany przez naiwne rfind. Tu sprawdzamy zgodność obu."""
    from api.services.debate_orchestrator import _extract_json_block as orch
    from core.dream_architect import _extract_json_block as core

    tricky = 'Odpowiedź: {"a": "tekst z } w środku", "b": 2} a dalej śmieci }'
    assert orch(tricky) == core(tricky)
    # I że wynik to poprawny, kompletny obiekt (nie ucięty na pierwszym `}`).
    import json
    parsed = json.loads(orch(tricky))
    assert parsed == {"a": "tekst z } w środku", "b": 2}


# ── #3: błąd agenta nie udaje pełnoprawnego głosu ────────────────────────────


@pytest.mark.asyncio
async def test_council_excludes_error_voice_from_full_voices():
    """Agent który rzuca wyjątek → event `agent_error`, a jego głos NIE wchodzi
    do full_voices przekazywanego Syezowi (#3)."""
    from api.services import debate_orchestrator as orch
    from api.services._types import PhaseCouncilResult

    class _FakeAgent:
        def __init__(self, name, ok):
            self.name = name
            self._ok = ok

        async def acontribute(self, *a, **k):
            if self._ok:
                return f"Głos agenta {self.name}."
            raise RuntimeError("symulowany błąd LLM")

    class _Brief:
        language = "pl"
        mode = "pełny"

    council = [_FakeAgent("Dobry", True), _FakeAgent("Zepsuty", False)]

    events = []
    full_voices = {}
    async for evt in orch._phase_council(
        council, "brief", None, _Brief(), None, "personal"
    ):
        if isinstance(evt, PhaseCouncilResult):
            full_voices = evt.full_voices
        else:
            events.append(evt)

    assert "Dobry" in full_voices
    assert "Zepsuty" not in full_voices  # uszkodzony głos wykluczony
    assert any("agent_error" in e and "Zepsuty" in e for e in events)


# ── #4: cache marzeń scope'owany per tenant ──────────────────────────────────


def test_dream_cache_key_is_tenant_scoped(monkeypatch):
    """Ten sam brief w dwóch tenantach → różne klucze cache (brak współdzielenia)."""
    import core.dream_architect as da

    monkeypatch.setattr(da, "_tenant_scope", lambda: "tenant_A")
    key_a = da._cache_key("identyczny brief")
    monkeypatch.setattr(da, "_tenant_scope", lambda: "tenant_B")
    key_b = da._cache_key("identyczny brief")
    assert key_a != key_b
