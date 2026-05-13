#!/usr/bin/env python3
"""
Usuwa z SQLite wszystkie: marzenia, debaty (historia briefów), projekty,
funkcjonalności, audyty, zobowiązania, głosy agentów, linki dream↔debate,
rolling `agent_evolution`.

Nie usuwa samego pliku DB ani schematu — tylko dane użytkownika.
Ścieżka: ARCHITEKT_DB_PATH lub domyślnie data/architekt.db (repo root).
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("aw_env_bootstrap", ROOT / "env_bootstrap.py")
if _spec and _spec.loader:
    _m = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_m)
    _m.load_repo_env()

from db.connection import DB_PATH  # noqa: E402

CLEAR_SQL = """
PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;
DELETE FROM agent_voices;
DELETE FROM dream_debate_link;
DELETE FROM commitments;
DELETE FROM projects;
DELETE FROM debates;
DELETE FROM dreams;
DELETE FROM agent_evolution;
COMMIT;
"""


async def main() -> None:
    import aiosqlite

    path = Path(os.getenv("ARCHITEKT_DB_PATH", str(DB_PATH))).resolve()
    if not path.is_file():
        print(f"Brak pliku bazy: {path} — nic do czyszczenia.", file=sys.stderr)
        return
    async with aiosqlite.connect(path) as db:
        await db.executescript(CLEAR_SQL)
        await db.commit()
    print(f"Wyczyszczono dane w: {path}")


if __name__ == "__main__":
    asyncio.run(main())
