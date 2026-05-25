"""Test zgodności — pytania kontrolne po syntezie Rady."""
from __future__ import annotations

KRYTERIA = [
    ("Czy to brzmi jak Ty?", "tozsamosc"),
    ("Czy ciało rezonuje z tą odpowiedzią?", "soma"),
    ("Czy Kidi (Dziecko) by się ucieszył?", "radosc"),
    ("Czy Szow (Cień) nie milczy z grzeczności?", "szczerosc"),
    ("Czy to nowy ruch, czy stary wzorzec (Tai)?", "ewolucja"),
]

def get_check_questions(synthesis: str | None = None) -> list[dict]:
    """Zwraca pytania kontrolne dla użytkownika. `synthesis` zarezerwowane
    pod przyszłą walidację LLM-as-judge (na razie sygnatura kompatybilna)."""
    return [{"pytanie": p, "tag": t, "do_oceny_uzytkownika": True} for p, t in KRYTERIA]

# wstecz kompatybilność
run_check = get_check_questions
