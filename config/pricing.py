"""Cennik modeli LLM (USD za 1M tokenów) — JEDYNE źródło prawdy.

Konsumenci:
  • `agents/base_agent._calculate_cost` (koszty debat + advisor),
  • `shared/utils/llm._log_cost` (dashboard).

Wcześniej dwa ręcznie synchronizowane cenniki (base_agent + shared/utils/llm)
z komentarzem „podmień ręcznie po 2026-08-31" — gwarantowany cichy dryf
kosztów po końcu promo Sonneta 5. Teraz promo jest liczone datą wywołania.

Estymata do logów/dashboardu — nie do faktury (realny billing: konsola
dostawcy). BYOK: koszt ponosi klucz użytkownika.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)

# Sonnet 5 — promo do 2026-08-31 włącznie ($2/$10), od 2026-09-01 $3/$15.
# (platform.claude.com/docs/en/about-claude/pricing, sprawdzone 2026-07-07)
_SONNET5_PROMO_UNTIL = date(2026, 8, 31)
_SONNET5_PROMO = (2.0, 10.0)
_SONNET5_STANDARD = (3.0, 15.0)

_STATIC_PER_M: dict[str, tuple[float, float]] = {
    # (input, output) USD / 1M tokenów
    "claude-opus-4-6":             (15.0, 75.0),
    # Standard rate — domyślny model Advisor toola (config/agent_models.py).
    "claude-opus-4-8":              (5.0, 25.0),
    "claude-sonnet-4-6":            (3.0, 15.0),
    "claude-haiku-4-5-20251001":    (0.25, 1.25),
    # legacy aliasy — bez kosztu „rozbicia”, gdy ktoś nadpisze przez env
    "claude-4-opus":               (15.0, 75.0),
    "claude-3-5-sonnet-20241022":   (3.0, 15.0),
    "claude-3-haiku":               (0.25, 1.25),
    # xAI (szacunki USD / 1M — do logów kosztu; API zwraca tokeny)
    "grok-3":                       (3.0, 15.0),
    "grok-3-mini":                  (0.3, 0.5),
}


# Modele już zgłoszone jako nieznane — warning RAZ na model na proces,
# nie przy każdym wywołaniu (koszt liczony po każdej odpowiedzi LLM).
_WARNED_UNKNOWN: set[str] = set()


def price_per_m(model: str, at: date | None = None) -> tuple[float, float] | None:
    """(input, output) USD/1M dla modelu; None gdy model nieznany (koszt 0 u callera).

    `at`: data rozliczenia (default: dziś UTC) — promo liczone w momencie
    wywołania, nie w momencie importu modułu (proces może żyć przez próg cen).

    Dopasowanie: exact → prefiks (datowane snapshoty typu
    `claude-sonnet-5-20260601` dziedziczą cenę `claude-sonnet-5`; dłuższy
    prefiks wygrywa). Model bez dopasowania NIE znika po cichu — jeden
    warning na proces, żeby dashboard kosztów pokazujący 0.0 miał ślad
    w logach zamiast wyglądać na poprawny.
    """
    m = (model or "").strip()
    if not m:
        return None
    if m == "claude-sonnet-5" or m.startswith("claude-sonnet-5-"):
        d = at or datetime.now(timezone.utc).date()
        return _SONNET5_PROMO if d <= _SONNET5_PROMO_UNTIL else _SONNET5_STANDARD
    exact = _STATIC_PER_M.get(m)
    if exact:
        return exact
    # Prefiks: `claude-opus-4-8-20260315` → stawka `claude-opus-4-8` itd.
    best_key = ""
    for key in _STATIC_PER_M:
        if m.startswith(key + "-") and len(key) > len(best_key):
            best_key = key
    if best_key:
        return _STATIC_PER_M[best_key]
    if m not in _WARNED_UNKNOWN:
        _WARNED_UNKNOWN.add(m)
        logger.warning(
            "pricing: model %r nieznany — koszt logowany jako $0.00. "
            "Dodaj stawkę w config/pricing.py, inaczej dashboard kosztów kłamie.",
            m,
        )
    return None
