"""Dev SQLite fallback gdy Postgres niedostępny; prod fail-fast."""

from __future__ import annotations

from pathlib import Path

import pytest

from db import backend as bk


@pytest.fixture(autouse=True)
def _reset_pg_pool():
    bk._pg_pool = None
    yield
    bk._pg_pool = None


@pytest.mark.asyncio
async def test_init_database_dev_fail_closed_on_pg_failure(monkeypatch):
    """Stage 2: domyślnie (bez furtki) dev NIE wpada po cichu na SQLite.

    DATABASE_URL wskazuje Postgres + połączenie pada → RuntimeError. SQLite nie
    ma RLS, więc cichy fallback maskowałby brak izolacji per-tenant."""
    monkeypatch.setenv("AW_ENV", "development")
    monkeypatch.delenv("AW_ALLOW_SQLITE_FALLBACK", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://architekt:x@localhost:5432/architekt")

    async def _fake_create_pool(*_a, **_k):
        raise OSError('role "architekt" does not exist')

    monkeypatch.setattr("asyncpg.create_pool", _fake_create_pool)

    sqlite_ran: list[bool] = []

    async def _sqlite_cb() -> None:
        sqlite_ran.append(True)

    with pytest.raises(RuntimeError, match="SQLite nie ma RLS|AW_ALLOW_SQLITE_FALLBACK"):
        await bk.init_database(_sqlite_cb)
    assert sqlite_ran == []  # callback SQLite NIE został uruchomiony
    assert bk.runtime_use_postgres() is False


@pytest.mark.asyncio
async def test_init_database_dev_fallback_with_explicit_optin(monkeypatch):
    """Świadoma furtka AW_ALLOW_SQLITE_FALLBACK=1 przywraca fallback na SQLite."""
    monkeypatch.setenv("AW_ENV", "development")
    monkeypatch.setenv("AW_ALLOW_SQLITE_FALLBACK", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://architekt:x@localhost:5432/architekt")

    async def _fake_create_pool(*_a, **_k):
        raise OSError('role "architekt" does not exist')

    monkeypatch.setattr("asyncpg.create_pool", _fake_create_pool)

    sqlite_ran: list[bool] = []

    async def _sqlite_cb() -> None:
        sqlite_ran.append(True)

    await bk.init_database(_sqlite_cb)
    assert sqlite_ran == [True]
    assert bk.runtime_use_postgres() is False


@pytest.mark.asyncio
async def test_init_database_prod_raises_on_pg_failure(monkeypatch):
    monkeypatch.setenv("AW_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")

    async def _fake_create_pool(*_a, **_k):
        raise OSError("connection refused")

    monkeypatch.setattr("asyncpg.create_pool", _fake_create_pool)

    with pytest.raises(RuntimeError, match="produkcji"):
        await bk.init_database(lambda: None)  # type: ignore[arg-type]

    assert bk.runtime_use_postgres() is False


@pytest.mark.asyncio
async def test_probe_db_ready_sqlite(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = tmp_path / "ready.db"
    import aiosqlite

    async with aiosqlite.connect(db_file) as db:
        await db.execute("CREATE TABLE t (id INTEGER)")
        await db.commit()

    ok, reason = await bk.probe_db_ready(db_file)
    assert ok is True
    assert reason == ""


def test_require_pg_pool_raises_clear_message(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert bk._pg_pool is None
    with pytest.raises(RuntimeError, match="PostgreSQL pool is not initialized"):
        bk._require_pg_pool()
