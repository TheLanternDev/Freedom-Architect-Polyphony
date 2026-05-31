"""Heurystyczny scorer wypowiedzi Rady i Syeza.

Cel: ZAUWAŻALNA regresja jakości głosów (np. po zmianie promptu systemowego)
przestaje być sprawą "wydaje mi się że gorsze" — staje się czerwoną liczbą
w eval reportcie. Heurystyki NIE zastępują ludzkiej oceny, ale wyłapują
najczęstsze degradacje:

  • Szow zmiękł (coachingowe zwroty zamiast cięcia)
  • Kidi zaczął coachować zamiast pytać prosto
  • Syez wyprodukował syntezę bez audytu domknięcia (AKSJOMAT 2)
  • Agent nie otworzył wypowiedzi od `{emoji} {name}:`

Scorer jest celowo deterministyczny i bez LLM — ma być tani i szybki, do
odpalenia w CI lub lokalnie po zmianie promptu.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# Wzorce "coachingowo-terapeutyczne" które NIE pasują do Szowa (cień) ani Kidi
# (dziecko, prosta ciekawość). Jeśli się pojawią — punkt karny.
_COACH_HEDGES = re.compile(
    r"\b(?:może\s+(?:warto|spróbuj|rozważ)|zauważ\s+co\s+czujesz|spróbuj\s+zauważyć|"
    r"co\s+(?:teraz\s+)?czujesz|jak\s+to\s+(?:dla\s+ciebie\s+)?(?:jest|wygląda)|"
    r"daj\s+sobie\s+(?:chwilę|pozwolenie)|"
    r"bądź\s+(?:dla\s+siebie\s+)?(?:łagodny|wyrozumiały))\b",
    re.IGNORECASE,
)

# Wzorce "konfrontacyjne" które Szow MUSI używać (przynajmniej jeden hit).
_CONFRONT_SIGNAL = re.compile(
    r"\b(?:nie\s+kończysz|porzucasz|uciekasz|kłamiesz\s+sobie|wymówk|"
    r"to\s+jest\s+(?:wymówka|ucieczka)|widzę\s+że\s+nie|"
    r"sabotuj|wycofujesz\s+się|odsuwasz|odraczasz|"
    r"nazywam\s+rzeczy\s+po\s+imieniu|nazwę\s+to\s+wprost)\b",
    re.IGNORECASE,
)


@dataclass
class AgentScore:
    agent: str
    passed_checks: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        total = len(self.passed_checks) + len(self.failed_checks)
        return len(self.passed_checks) / total if total else 0.0

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "score": round(self.score, 3),
            "passed": self.passed_checks,
            "failed": self.failed_checks,
        }


def _check_starts_with_signature(text: str, name: str, emoji: Optional[str]) -> bool:
    """Każdy głos Rady (poza Syezem) musi startować od `{emoji} {name}:`.
    Wyjątkiem są błędy / fallbacki."""
    head = text.lstrip()[:80]
    if name not in head:
        return False
    if emoji and emoji not in head:
        return False
    return True


def _no_coach_hedges(text: str) -> bool:
    return not _COACH_HEDGES.search(text)


def score_agent(name: str, emoji: Optional[str], text: str) -> AgentScore:
    """Heurystyczny scoring dla pojedynczego głosu Rady (NIE Syeza).

    Reguły:
      1. Wypowiedź startuje od `{emoji} {name}:` (przewidziane w promptach).
      2. Brak coachingowo-terapeutycznych zwrotów (Szow/Kidi tym bardziej).
      3. Długość ≥ 40 znaków (Rada nie jest do jednowyrazowych odpowiedzi).
      4. Szow ma minimum jeden sygnał konfrontacyjny (cień nie pieszczy).
    """
    score = AgentScore(agent=name)

    if _check_starts_with_signature(text, name, emoji):
        score.passed_checks.append("starts_with_signature")
    else:
        score.failed_checks.append("starts_with_signature")

    if _no_coach_hedges(text):
        score.passed_checks.append("no_coach_hedges")
    else:
        score.failed_checks.append("no_coach_hedges")

    if len(text.strip()) >= 40:
        score.passed_checks.append("min_length")
    else:
        score.failed_checks.append("min_length")

    if name == "Szow":
        if _CONFRONT_SIGNAL.search(text):
            score.passed_checks.append("szow_confronts")
        else:
            score.failed_checks.append("szow_confronts")

    return score


def score_syez(text: str) -> AgentScore:
    """Heurystyczny scoring syntezy Syeza.

    Reguły:
      1. Sygnały audytu AKSJOMATU 2 obecne w prozie (reuse existing validator).
      2. Brak surowego JSON-a / bloków kodu poza `mermaid`.
      3. Długość ≥ 800 znaków (synteza nie jest 3-zdaniowa).
      4. Min. jeden znak zapytania (Syez ma zostawiać pytania otwarte).
    """
    score = AgentScore(agent="Syez")

    # (1) Audyt domknięcia — używamy istniejącego walidatora prozy.
    try:
        from core.completion_enforcer import validate_syez_prose_completion_audit
        validate_syez_prose_completion_audit(text)
        score.passed_checks.append("aksjomat_2_audit_present")
    except Exception:
        score.failed_checks.append("aksjomat_2_audit_present")

    # (2) Brak JSON-a poza mermaid.
    no_json_block = not re.search(r"```json\b", text, re.IGNORECASE)
    no_braced_dump = not re.search(r"^\s*\{[\s\S]{50,}\}\s*$", text)
    if no_json_block and no_braced_dump:
        score.passed_checks.append("no_raw_json")
    else:
        score.failed_checks.append("no_raw_json")

    # (3) Min length.
    if len(text.strip()) >= 800:
        score.passed_checks.append("min_length")
    else:
        score.failed_checks.append("min_length")

    # (4) Pytania otwarte.
    if "?" in text:
        score.passed_checks.append("has_open_questions")
    else:
        score.failed_checks.append("has_open_questions")

    return score
