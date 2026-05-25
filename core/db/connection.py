"""
Cienki re-eksport kanonicznej warstwy DB.

Stan przed Fazą 0: ten plik miał 701 linii równolegle do `db/connection.py`
(różnica była tylko w prefiksach importu). Każda zmiana w jednym wymagała
lustrzanej w drugim — klasyczny code debt.

Decyzja Fazy 0 audytu (2026-05-15): kanoniczna implementacja zostaje w
`db/connection.py` (używana przez `main.py`, `tests/`, `scripts/`).
Tutaj zachowujemy alias dla wstecznej kompatybilności importów
`from core.db.connection import ...`.

Nie dodawaj nowej logiki w tym module — edytuj `db/connection.py`.
"""

from db.connection import *  # noqa: F401,F403
from db.connection import (  # noqa: F401  jawne re-eksporty
    DB_PATH,
    get_db,
    init_db,
    repo,
)

__all__ = ["DB_PATH", "get_db", "init_db", "repo"]
