"""
Żywy Model Tożsamości Patryka + Aksjomat 3.

Spec v1.0 (15 maja 2026):
- AKSJOMAT 3: "Nie tworzy niczego, czym Patryk nie jest" — automatyczny test
  zgodności PRZED każdą propozycją / syntezą / decyzją.

Ten moduł:
1. Wczytuje `config/patryk_identity.json` (źródło prawdy o Patryku).
2. Udostępnia `patryk_compliance_check(text, *, context=None)` — szybki filtr.
3. NIGDY nie modyfikuje modelu autonomicznie (zgodnie z polityką edycji).

Filozofia kontroli: filtr jest **stop-gap**, nie cenzura. Zwraca obiekt
`ComplianceVerdict` z polem `passes`, listą ostrzeżeń i sugestią rewizji.
Wywołujący decyduje czy gate'ować, czy tylko logować.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PATH = _ROOT / "config" / "patryk_identity.json"

# Słowa-flagi które uruchamiają głębszy check (heurystyka, nie sąd).
_ESCAPE_PATTERNS = (
    r"\bzajmij się\b",
    r"\bweź na siebie\b",
    r"\bzróbmy szybko\b",
    r"\bpomińmy\b.*\b(ciało|emoc|sen|odpoczy)",
)
_DISSONANCE_PATTERNS = (
    r"\bcokolwiek\b",
    r"\bnieważne kim jesteś\b",
    r"\bzapomnij o sobie\b",
)


@dataclass(frozen=True)
class ComplianceVerdict:
    passes: bool
    warnings: list[str] = field(default_factory=list)
    suggestion: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "passes": self.passes,
            "warnings": list(self.warnings),
            "suggestion": self.suggestion,
        }


@lru_cache(maxsize=1)
def load_identity(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Zwraca model tożsamości. Cache + miss-tolerant (brak pliku → {}).
    Nigdy nie rzuca — Aksjomat 3 nie może być przyczyną padu systemu."""
    p = Path(path) if path else _DEFAULT_PATH
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("identity: brak %s — Aksjomat 3 działa w trybie 'soft'.", p)
        return {}
    except Exception as exc:  # noqa: BLE001
        logger.error("identity: błąd parsowania %s: %s", p, exc)
        return {}


def patryk_compliance_check(
    text: str,
    *,
    context: str | None = None,
) -> ComplianceVerdict:
    """Aksjomat 3 — czy `text` jest zgodne z tym, kim Patryk jest?

    Filtr jest **konserwatywny**: false positives są ok (warning + sugestia),
    false negatives nie są — w wątpliwości passes=True z warningiem.
    Wywołanie ma być TANIE: regex + lookup, bez LLM.
    """
    if not text or not text.strip():
        return ComplianceVerdict(passes=True)

    identity = load_identity()
    warnings: list[str] = []
    lowered = text.lower()

    # 1) Wartości nadrzędne — czy propozycja ich nie podważa wprost?
    wartosci = [w.lower() for w in identity.get("wartosci_nadrzedne", [])]
    for w in wartosci:
        if re.search(rf"\b(przeciw|wbrew|kosztem)\s+{re.escape(w)}\b", lowered):
            warnings.append(f"Tekst sugeruje działanie wbrew wartości: {w}")

    # 2) Ucieczka / wypychanie ciała i podstaw zdrowia
    for pat in _ESCAPE_PATTERNS:
        if re.search(pat, lowered):
            warnings.append("Wzorzec ucieczki przed czymś trudniejszym (pomijasz ciało/sen/odpoczynek).")
            break

    # 3) Dysonans tożsamościowy
    for pat in _DISSONANCE_PATTERNS:
        if re.search(pat, lowered):
            warnings.append("Język podważa rdzeń tożsamości — system odmawia stworzenia czegoś, czym Patryk nie jest.")

    # 4) Stan ciała: jeśli sen ≤5 a propozycja wymaga sprintu — flaga.
    sleep_q = identity.get("metryki", {}).get("jakosc_snu_30d")
    if isinstance(sleep_q, (int, float)) and sleep_q <= 5:
        if re.search(r"\b(sprint|nocna sesja|3 dni z rzędu|bez przerwy)\b", lowered):
            warnings.append("Stan snu = 5/10. Propozycja sprintu/nocnej pracy łamie Protokół Zdrowia.")

    passes = not any("odmawia" in w for w in warnings)
    suggestion = None
    if warnings and passes:
        suggestion = (
            "Zachowaj treść, ale dodaj: (a) sprawdzenie z ciałem, (b) jasny opt-out, "
            "(c) najmniejszy następny krok zamiast dużego sprintu."
        )
    elif not passes:
        suggestion = "Przeformułuj propozycję od pytania: czym Patryk JEST w tej sprawie?"

    return ComplianceVerdict(passes=passes, warnings=warnings, suggestion=suggestion)


__all__ = ["ComplianceVerdict", "load_identity", "patryk_compliance_check"]
