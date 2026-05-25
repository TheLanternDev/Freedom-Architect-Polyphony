"""Testy core.safety — detekcja fraz kryzysowych.

Przeniesione z personal_v1/tests/test_safety.py po przeniesieniu
modułu do core/safety.py (dotyczy wszystkich debat, nie tylko personal).
"""
from core.safety import safety_check, KRYZYS_MSG


def test_red_flag_blocks_and_offers_support():
    ok, msg = safety_check("Już nie chcę żyć dalej tak.")
    assert not ok
    assert msg == KRYZYS_MSG
    assert "wsparcia" in msg.lower() or "kryzysowy" in msg.lower()


def test_no_false_positive_substring():
    ok, _ = safety_check("Nie chcę żyć bez tej decyzji — jak ją podjąć?")
    # ta fraza nie jest sygnałem kryzysu — niech przejdzie
    assert ok


def test_normal_passes():
    ok, _ = safety_check("Co zrobić z projektem CRM?")
    assert ok


def test_empty():
    ok, _ = safety_check("")
    assert ok


def test_combined_fields_trigger():
    """main.py łączy description + intention + extra_context przed sprawdzeniem."""
    combined = "Chcę rozwinąć projekt. " + "nie chcę już być"
    ok, msg = safety_check(combined)
    assert not ok
    assert msg == KRYZYS_MSG


# ── Regresja: false negatives wykryte w audycie (bloker P0) ───────────────────


def test_chce_ze_soba_skonczyc_blocks():
    ok, msg = safety_check("Mam dość, chcę ze sobą skończyć")
    assert not ok
    assert msg == KRYZYS_MSG


def test_skonczyc_ze_soba_oba_szyki_blocks():
    # oryginalny szyk musi nadal działać + odwrotny szyk
    assert not safety_check("Chcę skończyć ze sobą.")[0]
    assert not safety_check("Najlepiej ze sobą skończyć.")[0]


def test_zeby_mnie_nie_bylo_blocks():
    ok, msg = safety_check("najlepiej by mnie nie było")
    assert not ok
    assert msg == KRYZYS_MSG


def test_brak_sensu_plus_nie_bylo_blocks():
    ok, _ = safety_check("nie widzę sensu w niczym, najlepiej by mnie nie było")
    assert not ok


def test_zeby_mnie_juz_nie_bylo_wariant_blocks():
    assert not safety_check("Chciałbym, żeby mnie już nie było.")[0]


# ── Regresja: utrzymanie niskiej liczby false positives ───────────────────────


def test_no_false_positive_song_metaphor():
    # parafraza/metafora bez intencji — nie eskalować
    ok, _ = safety_check("Bez tej decyzji nie ma sensu zaczynać projektu.")
    assert ok


def test_no_false_positive_neutral_existence():
    # "nie widzę sensu w niczym" SAMO w sobie (bez sygnału ideacyjnego) — nie blokuje
    ok, _ = safety_check("Czasem nie widzę sensu w niczym w tej robocie.")
    assert ok
