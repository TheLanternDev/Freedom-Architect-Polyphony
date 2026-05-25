"""
Backend bazy: SQLite (domyślnie) lub PostgreSQL (`DATABASE_URL`).

• Krótkie żądania HTTP: `acquire_http_db`.
• Długi strumień SSE debaty: `debate_stream_db` — jedno połączenie na całą debatę.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

_pg_pool: Any = None

_SCHEMA_PG_PATH = Path(__file__).resolve().parent / "schema_postgres.sql"


def database_url() -> str:
    return (os.getenv("DATABASE_URL") or "").strip()


def use_postgres() -> bool:
    u = database_url().lower()
    return u.startswith(("postgresql://", "postgres://"))


def _split_pg_schema(sql_text: str) -> list[str]:
    stmts: list[str] = []
    cur: list[str] = []
    for line in sql_text.splitlines():
        ls = line.strip()
        if not cur and ls.startswith("--"):
            continue
        cur.append(line)
        if ls.endswith(";"):
            block = "\n".join(cur).strip()
            if block:
                stmts.append(block)
            cur = []
    return stmts


async def init_database(sqlite_init_cb: Any) -> None:
    """sqlite_init_cb: async callable () -> None uruchamiane tylko dla SQLite."""
    global _pg_pool
    if use_postgres():
        try:
            import asyncpg
        except ImportError as e:
            raise RuntimeError(
                "DATABASE_URL wskazuje na Postgres — zainstaluj asyncpg (requirements.txt)."
            ) from e
        url = database_url()
        max_sz = int(os.getenv("PG_POOL_MAX_SIZE", "16") or "16")
        max_sz = max(2, min(max_sz, 64))
        _pg_pool = await asyncpg.create_pool(url, min_size=1, max_size=max_sz)
        schema_sql = _SCHEMA_PG_PATH.read_text(encoding="utf-8")
        async with _pg_pool.acquire() as conn:
            for stmt in _split_pg_schema(schema_sql):
                await conn.execute(stmt)
        logger.info(
            "PostgreSQL pool initialized (%s)",
            re.sub(r":([^@/]*)@", r":****@", url),
        )
        return

    await sqlite_init_cb()


async def shutdown_database() -> None:
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None


@asynccontextmanager
async def acquire_http_db(sqlite_db_path: Path) -> AsyncIterator[Any]:
    """Pojedyncze połączenie na żądanie FastAPI."""
    if use_postgres():
        assert _pg_pool is not None
        from core.db.pg_wrap import PgConnection

        async with _pg_pool.acquire() as raw:
            yield PgConnection(raw)
        return

    import aiosqlite

    async with aiosqlite.connect(sqlite_db_path) as raw:
        await raw.execute("PRAGMA foreign_keys = ON")
        raw.row_factory = aiosqlite.Row

        class _Lite:
            dialect = "sqlite"

            def __init__(self, c: Any) -> None:
                self._c = c

            async def execute(self, sql: str, params: Any = ()) -> Any:
                return await self._c.execute(sql, params)

            async def commit(self) -> None:
                await self._c.commit()

        yield _Lite(raw)


@asynccontextmanager
async def debate_stream_db(sqlite_db_path: Path) -> AsyncIterator[Any]:
    """Jedno połączenie na cały cykl SSE debaty."""
    if use_postgres():
        assert _pg_pool is not None
        from core.db.pg_wrap import PgConnection

        async with _pg_pool.acquire() as raw:
            yield PgConnection(raw)
        return

    import aiosqlite

    conn = await aiosqlite.connect(sqlite_db_path)
    await conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = aiosqlite.Row

    class _Lite:
        dialect = "sqlite"

        def __init__(self, c: Any) -> None:
            self._c = c

        async def execute(self, sql: str, params: Any = ()) -> Any:
            return await self._c.execute(sql, params)

        async def commit(self) -> None:
            await self._c.commit()

    try:
        yield _Lite(conn)
    finally:
        await conn.close()


@asynccontextmanager
async def optional_debate_db(sqlite_db_path: Path, enabled: bool) -> AsyncIterator[Any]:
    """Jedno połączenie przez cały SSE lub brak DB (`yield None`)."""
    if enabled:
        async with debate_stream_db(sqlite_db_path) as db:
            yield db
    else:
        yield None  # type: ignore[misc]
