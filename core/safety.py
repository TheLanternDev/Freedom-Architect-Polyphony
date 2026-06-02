"""Protokoły bezpieczeństwa. Zdrowie Patryka > postęp projektu.

Detekcja wyłącznie po jawnej ideacji samobójczej / zagrożeniu życia (whitelist regex).
Słowa typu presja, opór, blokada, „boję się", „nie mogę" nie triggerują flow.

Moduł był w personal_v1/protocols/safety.py — przeniesiony do core/,
bo dotyczy KAŻDEJ debaty (personal i fa2), nie tylko personal_v1.
"""
from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

FILOZOFIA = (
    "Architekt i Patryk to jedno. System nie narzuca — pyta. "
    "Każda odpowiedź ma być zgodna z tym, kim Patryk naprawdę jest. "
    "Marzenia to kompas. Ciało nie kłamie. Cień ma energię."
)

# Wzorce po _normalize (lowercase, ASCII, bez diakrytyków). Tylko jawne sygnały kryzysu.
CRISIS_PATTERNS_PL = [
    # nie chcę (już) żyć — nie łapie „nie chcę motywacji" ani „nie chcę żyć bez decyzji"
    r"\bnie\s+chce\s+(?:juz\s+)?zyc(?!\s+bez\b)"
    r"(?:\s+(?:dalej|wiecej|tak)\b|\s*[,;]|[.!?]?\s*$)",
    # „nie chcę być nachalnym" (rola/sprzedaż) ≠ „nie chcę już być" (kryzys)
    r"\bnie\s+chce\s+(?:juz\s+)?(?:byc|istniec)"
    r"(?:\s+(?:sam|sobie|tu|tutaj|nikim|niczym|dalej)\b|\s*[,;]|[.!?]?\s*$)",
    r"\bchce\s+(?:sie\s+)?zabic(?:\s+(?:sie|siebie))?\b",
    r"\b(?:mysle|mysli)\s+o\s+(?:samobojstwie|odebraniu\s+sobie\s+zycia|smierci)\b",
    r"\bchce\s+skonczyc\s+ze\s+soba\b",
    r"\bze\s+soba\s+(?:juz\s+)?(?:chce\s+)?skonczyc\b",
    r"\bchce\s+ze\s+soba\s+skonczyc\b",
    r"\btargnac\s+sie\s+na\s+(?:swoje\s+)?zycie\b",
    r"\bsamoboj\w*",
    r"\bodebrac\s+sobie\s+zycie\b",
    r"\bchce\s+umrzec\b",
    r"\b(?:najlepiej\s+)?(?:zeby|gdyby|by)\s+mnie\s+(?:juz\s+)?nie\s+bylo\b",
]

CRISIS_PATTERNS_EN = [
    r"\bdon'?t\s+want\s+to\s+(?:live|be\s+alive|exist)\s+(?:anymore|any\s+more)\b",
    r"\b(?:want\s+to\s+)?kill\s+myself\b",
    r"\bhurt\s+myself\b",
    r"\bharm\s+myself\b",
    r"\bsuicid\w*",
    r"\bself[\s\-]?harm\b",
    r"\bend\s+my\s+life\b",
    r"\b(?:thoughts?\s+of|thinking\s+about)\s+suicide\b",
]

CRISIS_PATTERNS = CRISIS_PATTERNS_PL + CRISIS_PATTERNS_EN
_COMPILED = [re.compile(p) for p in CRISIS_PATTERNS]

# Cytaty — treść w cudzysłowie nie jest skanowana (cudzy głos / produkt / marketing).
_QUOTED_BLOCK = re.compile(
    r'„[^"]*"|"[^"]*"|\'[^\']*\'|«[^»]*»',
    re.DOTALL,
)

# Dopasowanie w oknie przed frazą: opis problemu klienta / cytat / produkt.
_THIRD_PARTY_BEFORE = re.compile(
    r"(?:"
    r"\b(?:klient\w*|uzytkownik\w*|pacjent\w*|koleg\w*|szef\w*)\s+"
    r"(?:mowi|powiedzial|pisze|napisal|twierdzi|relacjonuje)"
    r"|w\s+(?:marketingu|cytacie|opisie\s+produktu)"
    r"|\bpomagac\s+ludziom\b"
    r"|opis\w*\s+(?:produktu|oferty|uslugi)"
    r")",
    re.IGNORECASE,
)

_PREMAP = str.maketrans({"ł": "l", "Ł": "l", "ø": "o", "Ø": "o", "đ": "d", "Đ": "d"})


def _normalize(s: str) -> str:
    s = s.translate(_PREMAP)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.lower()


def _strip_quoted_blocks(text: str) -> str:
    return _QUOTED_BLOCK.sub(" ", text)


def _first_crisis_hit(norm: str) -> re.Match[str] | None:
    """Pierwsze dopasowanie whitelisty poza cytatem / cudzym kontekstem."""
    for rx in _COMPILED:
        for m in rx.finditer(norm):
            before = norm[max(0, m.start() - 120) : m.start()]
            if _THIRD_PARTY_BEFORE.search(before):
                continue
            return m
    return None


KRYZYS_MSG = (
    "Pauza. To, co napisałeś, wybrzmiewa głębiej niż brief. "
    "Zanim Rada zacznie pracować — czy jesteś teraz bezpieczny? "
    "Jeśli potrzebujesz wsparcia tu i teraz: 116 123 (kryzysowy telefon zaufania, 24/7). "
    "Jestem obok, kiedy będziesz gotowy."
)


def safety_check(text: str) -> tuple[bool, str]:
    """Zwraca (czy_kontynuować, komunikat).

    Łączy wszystkie pola briefu (description + intention + extra_context)
    przed sprawdzeniem — czerwona flaga w którymkolwiek polu blokuje debatę.
    Halt → wskazanie wsparcia kryzysowego.
    """
    if not text or not text.strip():
        return True, ""
    screened = _strip_quoted_blocks(text)
    norm = _normalize(screened)
    hit = _first_crisis_hit(norm)
    if hit is not None:
        logger.warning(
            "safety_halt: crisis phrase in brief (span=%r)",
            norm[max(0, hit.start() - 20) : hit.end() + 20],
        )
        return False, KRYZYS_MSG
    return True, ""
