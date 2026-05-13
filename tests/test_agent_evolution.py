"""P5: tabela + merge notatek ewolucyjnych per agent."""

from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from db.connection import repo


def test_agent_evolution_merge_skips_errors(fresh_db_path, monkeypatch):
    monkeypatch.setenv("ARCHITEKT_DB_PATH", str(fresh_db_path))
    import db.connection as dbc

    monkeypatch.setattr(dbc, "DB_PATH", fresh_db_path)

    async def inner():
        await dbc.init_db(fresh_db_path)
        async with aiosqlite.connect(str(fresh_db_path)) as db:
            await repo.merge_agent_evolution_snippet(db, "Kogit", "[błąd: test]")
            await db.commit()
            cur = await db.execute(
                "SELECT COUNT(*) FROM agent_evolution WHERE agent_name='Kogit'"
            )
            n = (await cur.fetchone())[0]
            assert n == 0

    asyncio.run(inner())


def test_agent_evolution_merge_accumulates(fresh_db_path, monkeypatch):
    monkeypatch.setenv("ARCHITEKT_DB_PATH", str(fresh_db_path))
    import db.connection as dbc

    monkeypatch.setattr(dbc, "DB_PATH", fresh_db_path)

    async def inner():
        await dbc.init_db(fresh_db_path)
        async with aiosqlite.connect(str(fresh_db_path)) as db:
            await repo.merge_agent_evolution_snippet(db, "Emojy", "Pierwsza myśl.")
            await repo.merge_agent_evolution_snippet(db, "Emojy", "Druga warstwa.")
            await db.commit()
            d = await repo.list_agent_evolution(db)
            assert "Pierwsza" in d["Emojy"] and "Druga" in d["Emojy"]

    asyncio.run(inner())


def test_agent_evolution_table_after_app_init(client_no_redis, fresh_db_path):
    async def chk():
        async with aiosqlite.connect(str(fresh_db_path)) as db:
            cur = await db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_evolution'"
            )
            assert await cur.fetchone()

    asyncio.run(chk())
