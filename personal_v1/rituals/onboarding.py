"""20 pytań pierwszego uruchomienia — tworzą profil Patryka."""

PYTANIA = [
    # Tożsamość
    "Kim jesteś, kiedy nikt nie patrzy?",
    "Z czego jesteś najbardziej dumny — i czego nikt o tym nie wie?",
    "Co byś robił, gdyby pieniądze nie miały znaczenia?",
    # Ciało
    "Gdzie w ciele najczęściej trzymasz napięcie?",
    "Kiedy ostatnio czułeś radość fizycznie?",
    # Cień
    "Co najczęściej ukrywasz przed innymi?",
    "Czego się boisz, ale nie chcesz o tym mówić?",
    "Jaki impuls najczęściej tłumisz?",
    # Marzenia
    "Co byś zrobił, gdybyś wiedział, że nie możesz przegrać?",
    "Jakie marzenie odpaliło Cię ostatnio?",
    # Relacje
    "Kto Cię zna naprawdę?",
    "Komu nie powiedziałeś czegoś ważnego?",
    # Historia (Tai)
    "Jaki wzorzec z dzieciństwa wraca w dorosłym życiu?",
    "Co byś chciał przerwać raz na zawsze?",
    # Wartości
    "Trzy rzeczy, na które nigdy się nie zgodzisz.",
    "Trzy rzeczy, których pragniesz najmocniej.",
    # Domknięcie
    "Jakiego projektu nie ukończyłeś — i dlaczego?",
    "Co zaczynasz, kiedy się boisz skończyć?",
    # Cisza
    "Czego najbardziej potrzebujesz w tym tygodniu?",
    "Jakie jedno zdanie chciałbyś usłyszeć od siebie sprzed roku?",
]

# Grupowanie pytań w sekcje (batche) — inteligentne sekwencjonowanie w UI
# oraz złożenie „Mojego obrazu". Indeksy spójne z PYTANIA (nie zmieniać kolejności).
_GRUPY = [
    ("Tożsamość", 3),
    ("Ciało", 2),
    ("Cień", 3),
    ("Marzenia", 2),
    ("Relacje", 2),
    ("Historia", 2),
    ("Wartości", 2),
    ("Domknięcie", 2),
    ("Cisza", 2),
]
SEKCJE: list[str] = []
for _nazwa, _ile in _GRUPY:
    SEKCJE.extend([_nazwa] * _ile)
assert len(SEKCJE) == len(PYTANIA), "SEKCJE muszą pokrywać każde pytanie"


def start_onboarding():
    return {"pytania": PYTANIA, "sekcje": SEKCJE, "ton": "lagodny", "tempo": "ile_chcesz"}
