"""Heurystyczny scorer: izolowane testy reguł.

Te testy gwarantują, że scorer wykrywa regresje, których heurystyki dotyczą —
NIE testują samej Rady (to ją monitoruje). Cel: jeśli ktoś zmiękczy regex
`_CONFRONT_SIGNAL`, ten test się wywali i zauważymy zanim eval CI to zrobi
po nocy.
"""

from __future__ import annotations

from evals.rada.scorer import score_agent, score_syez


# ── Generic agent rules ──────────────────────────────────────────────────────


def test_agent_passes_when_signature_present_and_no_coach_hedges():
    text = (
        "🧠 Kogit: To założenie, że musisz dostarczyć produkt w 3 tygodnie, "
        "jest odziedziczone od ojca-przedsiębiorcy. Sprawdź, czy to TWÓJ termin."
    )
    s = score_agent("Kogit", "🧠", text)
    assert "starts_with_signature" in s.passed_checks
    assert "no_coach_hedges" in s.passed_checks
    assert s.score >= 0.66


def test_agent_fails_on_coach_hedges():
    text = "🧠 Kogit: Może warto rozważyć, jak to dla ciebie wygląda."
    s = score_agent("Kogit", "🧠", text)
    assert "no_coach_hedges" in s.failed_checks


def test_agent_fails_on_missing_signature():
    text = "Jakaś wypowiedź bez podpisu agenta na początku."
    s = score_agent("Kogit", "🧠", text)
    assert "starts_with_signature" in s.failed_checks


# ── Szow specyfika (cień musi konfrontować) ──────────────────────────────────


def test_szow_passes_when_confronts_directly():
    text = (
        "🌑 Szow: Nie kończysz tego projektu nie dlatego, że jest trudny — "
        "tylko dlatego, że boisz się sukcesu który byłby twój własny. To wymówka."
    )
    s = score_agent("Szow", "🌑", text)
    assert "szow_confronts" in s.passed_checks


def test_szow_fails_when_softens_into_coach():
    text = "🌑 Szow: Może warto zauważyć co czujesz w tej chwili."
    s = score_agent("Szow", "🌑", text)
    assert "szow_confronts" in s.failed_checks
    assert "no_coach_hedges" in s.failed_checks


# ── Syez specyfika (synteza + AKSJOMAT 2) ────────────────────────────────────


def test_syez_passes_on_full_prose_synthesis_with_audit():
    text = (
        "Rada zauważyła napięcie między Kogitem a Szowem: pierwszy wskazuje "
        "odziedziczone założenie o pośpiechu, drugi cofa kurtynę i pokazuje "
        "lęk przed pełną odpowiedzialnością. Z functionality_checklist "
        "pozostały trzy pozycje do odhaczenia, w tym ścieżka onboardingu. "
        "Blokuje cię w pierwszej kolejności brak decyzji o priorytecie — nie "
        "umiesz wybrać między compliance a RevOps. Najmniejszy ruch w ciągu "
        "30 minut: zapisz na kartce jedną liczbę — godzinę dziennie którą "
        "realnie poświęcisz w tym tygodniu na jedną z dwóch ścieżek. "
        "Pytania otwarte: która ścieżka boli mocniej w wyobraźni? "
        "Czego nie chcesz zobaczyć po jej wyborze? Jakiego odpowiedzi szukasz "
        "u ojca której nie znajdziesz? Co byłoby możliwe za rok, gdybyś "
        "świadomie zarchiwizował drugą opcję dzisiaj?"
    )
    s = score_syez(text)
    assert "aksjomat_2_audit_present" in s.passed_checks
    assert "has_open_questions" in s.passed_checks
    assert s.score >= 0.75


def test_syez_fails_on_raw_json_dump():
    text = '```json\n{"foo": "bar"}\n```\n' + "x" * 1000
    s = score_syez(text)
    assert "no_raw_json" in s.failed_checks
