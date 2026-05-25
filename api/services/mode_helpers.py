"""Helpery trybów debaty: pytanie dnia, dekoratory briefu."""

from __future__ import annotations

from datetime import date


# ── Pytania dnia (tryb codzienny) ────────────────────────────────────────────

_DAILY_QUESTIONS_PL: tuple[str, ...] = (
    "Co jest dziś najmniejszym krokiem, który przybliża Cię do tego, czego naprawdę chcesz?",
    "Czego unikasz nazwanie na głos — i jak jednym zdaniem byś to nazwał?",
    "Kim jesteś, gdy nikt nie patrzy — i czego ten moment Cię uczy?",
    "Co byś zrobił jutro, gdybyś nie bał się rozczarować nikogo?",
    "Jaki sygnał z ciała najbardziej Ci teraz ufa?",
    "Czego potrzebujesz od siebie dziś bardziej niż od innych?",
    "Co jest jedyną rzeczą do odhaczenia w najbliższej godzinie?",
)
_DAILY_QUESTIONS_EN: tuple[str, ...] = (
    "What is the smallest step today that moves you toward what you actually want?",
    "What are you avoiding naming out loud — and how would you name it in one sentence?",
    "Who are you when no one is watching — and what does that teach you?",
    "What would you do tomorrow if you weren't afraid to disappoint anyone?",
    "Which signal from your body do you trust most right now?",
    "What do you need from yourself today more than from anyone else?",
    "What is the one thing to tick off within the next hour?",
)


def daily_checkin_question(language: str) -> str:
    """Pytanie dnia — rotacja po ordinalnym dniu roku."""
    i = date.today().toordinal() % len(_DAILY_QUESTIONS_PL)
    return _DAILY_QUESTIONS_EN[i] if language == "en" else _DAILY_QUESTIONS_PL[i]


def mode_decorator_for_dream(mode: str, language: str = "pl") -> str:
    """Prefix wstrzykiwany do briefu przed destylacją, zależnie od trybu."""
    if mode == "codzienny":
        q = daily_checkin_question(language)
        if language == "en":
            return (
                "\n\n[DAILY MODE — ~5 minute check-in, NOT a full Council debate]\n"
                "Each agent: max 2 sentences; concrete, warm, no preamble.\n"
                "Focus on today's anchor question:\n"
                f"→ {q}\n"
            )
        return (
            "\n\n[Tryb codzienny — check-in ~5 min, to nie pełna debata Rady]\n"
            "Każdy agent: maks. 2 zdania; konkret, życzliwość, bez wstępów.\n"
            "Oś dzisiejszego pytania:\n"
            f"→ {q}\n"
        )
    if mode == "marzen":
        return (
            "\n\n[Tryb Marzeń] Najpierw pełna ekspansja wizji — NIE redukuj do realizmu, "
            "póki nie nazwiesz pełnej wersji."
        )
    if mode == "schematy":
        if language == "en":
            return (
                "\n\n[Pattern-Breaking Mode] Under the brief, find the abandonment or escape "
                "pattern — name the dream it hides.\n"
                "MANDATORY OUTPUT: end your voice with exactly one sentence starting with "
                "\"Today I will...\" that the user can say aloud or write down right now. "
                "No abstractions — one concrete action ≤60 minutes."
            )
        return (
            "\n\n[Tryb Przełamywania Schematów] Pod briefem szukaj wzorca porzucania "
            "lub ucieczki — nazwij marzenie, które ten schemat zasłania.\n"
            "OBOWIĄZKOWY OUTPUT: zakończ swój głos dokładnie jednym zdaniem zaczynającym się "
            "od \"Dziś zrobię...\" które użytkownik może powiedzieć głośno lub zapisać teraz. "
            "Żadnych abstrakcji — jedna konkretna akcja ≤60 minut."
        )
    return ""


# ── Re-prompt audytu domknięcia ───────────────────────────────────────────────


def build_audit_fix_prompt(language: str, synthesis_final: str) -> str:
    """Zwraca prompt do re-promptu Syeza po naruszeniu completion_audit."""
    if language == "en":
        return (
            "The previous synthesis does not satisfy AXIOM 2 (completion audit).\n"
            "Rewrite IT ALL as PURE ENGLISH PROSE — no JSON; the only "
            "permitted code block is ```mermaid … ``` (agent relation diagram).\n"
            "Weave clearly three things: what remains in the functionality "
            "checklist, what blocks the first outstanding item, and the "
            "smallest concrete move (≈60 minutes).\n\n"
            f"Previous version:\n---\n{synthesis_final}\n---"
        )
    return (
        "Poprzednia synteza nie spełnia AKSJOMATU 2 (audyt domknięcia).\n"
        "Przepisz CAŁOŚĆ jako CZYSTĄ POLSKĄ PROZĘ — bez JSON-a; jedyny "
        "dozwolony blok kodu to ```mermaid … ``` (diagram relacji agentów).\n"
        "Wpleć wyraźnie trzy rzeczy: co zostało z checklisty funkcjonalności, "
        "co blokuje pierwszą zaległą pozycję, oraz najmniejszy konkretny ruch "
        "(około 60 minut).\n\n"
        f"Poprzednia wersja:\n---\n{synthesis_final}\n---"
    )
