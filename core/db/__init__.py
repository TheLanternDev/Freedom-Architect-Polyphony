"""
Warstwa persystencji Architekta Wolności (SQLite via aiosqlite).

Tabele odpowiadają AKSJOMATOM:
- AKSJOMAT 1 (Architektura Marzenia): `dreams`, `dream_debate_link`
- AKSJOMAT 2 (Doprowadzanie Do Końca): `projects`, `functionality_items`, `completion_audits`
- Reszta MVP: `debates`, `agent_voices`, `commitments`

Konfiguracja: env `ARCHITEKT_DB_PATH` (domyślnie `data/architekt.db` w katalogu projektu).
"""

from core.db.connection import (
    DB_PATH,
    get_db,
    init_db,
    repo,
)

__all__ = ["DB_PATH", "get_db", "init_db", "repo"]
