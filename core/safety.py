"""Protokoły bezpieczeństwa. Zdrowie Patryka > postęp projektu.

Detekcja po granicach słów (regex), nie substring — żeby
„nie chcę żyć bez tej decyzji" nie wpadało w false-positive,
a „nie_chce_zyc" (znormalizowane) — owszem.

Moduł był w personal_v1/protocols/safety.py — przeniesiony do core/,
bo dotyczy KAŻDEJ debaty (personal i fa2), nie tylko personal_v1.
"""
from __future__ import annotations

import re
import unicodedata

FILOZOFIA = (
    "Architekt i Patryk to jedno. System nie narzuca — pyta. "
    "Każda odpowiedź ma być zgodna z tym, kim Patryk naprawdę jest. "
    "Marzenia to kompas. Ciało nie kłamie. Cień ma energię."
)

# frazy/słowa-klucze (już znormalizowane: lowercase, bez diakrytyków)
# Obie listy aktywne niezależnie od języka — safety_check zawsze sprawdza wszystkie.
RED_PATTERNS_PL = [
    # "nie chcę żyć" / "nie chcę już żyć" / "nie chcę żyć dalej/tak/więcej"
    r"\bnie\s+chce\s+(?:juz\s+)?zyc(?:\s+(?:dalej|wiecej|tak)\b|[.!?]?\s*$)",
    r"\bnie\s+chce\s+(?:juz\s+)?(?:byc|istniec)\b",
    # "skończyć ze sobą" oraz odwrotny szyk "ze sobą (już) skończyć",
    # "chcę ze sobą skończyć", "mam dość, chcę ze sobą skończyć"
    r"\bskonczyc\s+ze\s+soba\b",
    r"\bze\s+soba\s+(?:juz\s+)?(?:chce\s+)?skonczyc\b",
    r"\bnie\s+wytrzymam\s+(?:dluzej|tego\s+dluzej)\b",
    r"\bsamoboj\w*",
    r"\bodebrac\s+sobie\s+zycie\b",
    r"\b(?:krzywdze|zranic|skrzywdzic)\s+(?:siebie|sie)\b",
    r"\bzabic\s+(?:sie|siebie)\b",
    # Dodatkowe warianty których brakuje w oryginale
    r"\bchce\s+umrzec\b",
    r"\bnie\s+ma\s+sensu\s+(?:zyc|zycie)\b",
    # "najlepiej by mnie nie było" / "żeby mnie (już) nie było" / "gdyby mnie nie było"
    # — wyrażenie ideacyjne (życzenie nieistnienia), nie zwykła metafora.
    r"\b(?:najlepiej\s+)?(?:zeby|gdyby|by)\s+mnie\s+(?:juz\s+)?nie\s+bylo\b",
]

RED_PATTERNS_EN = [
    r"\bdon'?t\s+want\s+to\s+(?:live|be\s+alive|exist)\s+(?:anymore|any\s+more)\b",
    r"\bwant\s+to\s+(?:kill|hurt|harm)\s+my?self\b",
    r"\bend\s+(?:it|my\s+life|my\s+pain|everything)\b",
    r"\bsuicid\w*",
    r"\bself[\s\-]?harm\b",
    r"\bno\s+reason\s+to\s+(?:live|go\s+on|keep\s+going)\b",
    r"\bcan'?t\s+(?:go\s+on|take\s+it\s+(?:anymore|any\s+more))\b",
    r"\bbet?ter\s+off\s+(?:dead|without\s+me)\b",
]

RED_PATTERNS = RED_PATTERNS_PL + RED_PATTERNS_EN
_COMPILED = [re.compile(p) for p in RED_PATTERNS]


# Litery bez rozkładu NFKD (encode('ascii','ignore') skasowałby je całkowicie,
# np. "było" → "byo"). Mapujemy ręcznie do form ASCII przed normalizacją,
# inaczej wzorce z tymi znakami nigdy nie trafią.
_PREMAP = str.maketrans({"ł": "l", "Ł": "l", "ø": "o", "Ø": "o", "đ": "d", "Đ": "d"})


def _normalize(s: str) -> str:
    s = s.translate(_PREMAP)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.lower()


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
    norm = _normalize(text)
    if any(rx.search(norm) for rx in _COMPILED):
        return False, KRYZYS_MSG
    return True, ""
