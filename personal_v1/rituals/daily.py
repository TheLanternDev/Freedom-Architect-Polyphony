"""Codzienny rytuał — 5 min, 3 pytania, łagodnie."""

PYTANIA_PORANNE = [
    "Co dziś w ciele? (1 słowo)",
    "Co dziś jest najważniejsze — a co tylko pilne?",
    "Co Kidi (Dziecko) chciałoby dziś zrobić?",
]

PYTANIA_WIECZORNE = [
    "Gdzie dziś byłem sobą, a gdzie kimś innym?",
    "Co domknąłem? Co zostawiłem otwarte?",
    "Jeden krok wdzięczności.",
]

def poranek(): return {"typ": "poranek", "pytania": PYTANIA_PORANNE}
def wieczor(): return {"typ": "wieczor", "pytania": PYTANIA_WIECZORNE}
