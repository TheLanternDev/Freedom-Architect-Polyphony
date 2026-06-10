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


def runtime_use_postgres() -> bool:
    """Aktywny backend runtime — True tylko gdy pula PG została zainicjalizowana."""
    return _pg_pool is not None


def _require_pg_pool() -> Any:
    if _pg_pool is None:
        raise RuntimeError(
            "PostgreSQL pool is not initialized — sprawdź DATABASE_URL, "
            "dostępność serwera i logi startu (w produkcji startup powinien się zatrzymać wcześniej)."
        )
    return _pg_pool

_SCHEMA_PG_PATH = Path(__file__).resolve().parent / "schema_postgres.sql"
_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


async def _run_pg_migrations(conn: Any) -> None:
    """Uruchamia niewykonane migracje z db/migrations/*.sql (tylko Postgres).

    Wersjonowanie przez tabelę `schema_migrations`. Każdy plik wykonywany jako
    całość jednym `execute` (asyncpg simple-query) — poprawnie obsługuje bloki
    `DO $$ ... $$;`, których nie wolno dzielić po średnikach.
    Pliki są idempotentne (IF [NOT] EXISTS), ale tracking i tak zapobiega
    ponownemu uruchamianiu.
    """
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version TEXT PRIMARY KEY,"
        " applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
    )
    if not _MIGRATIONS_DIR.is_dir():
        return
    applied = {r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")}
    for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem  # np. "0001_add_tenant_isolation"
        if version in applied:
            continue
        sql_text = path.read_text(encoding="utf-8")
        async with conn.transaction():
            await conn.execute(sql_text)
            await conn.execute(
                "INSERT INTO schema_migrations(version) VALUES($1)", version
            )
        logger.info("Applied Postgres migration: %s", version)


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
    from api.settings import is_production

    global _pg_pool
    if use_postgres():
        pool: Any = None
        try:
            import asyncpg
        except ImportError as e:
            raise RuntimeError(
                "DATABASE_URL wskazuje na Postgres — zainstaluj asyncpg (requirements.txt)."
            ) from e
        url = database_url()
        max_sz = int(os.getenv("PG_POOL_MAX_SIZE", "16") or "16")
        max_sz = max(2, min(max_sz, 64))
        try:
            pool = await asyncpg.create_pool(url, min_size=1, max_size=max_sz)
            _pg_pool = pool
            schema_sql = _SCHEMA_PG_PATH.read_text(encoding="utf-8")
            # ⚠️  JEDYNE dozwolone użycie rawowego `_pg_pool.acquire()` bez PgConnection wrappera.
            # PgConnection.execute() ustawia GUC `architekt.tenant_id` przed każdym query —
            # co jest wymagane przez RLS policy tenant_isolation. Tutaj celowo pomijamy ten
            # mechanizm, bo migracje DDL/seed muszą widzieć WSZYSTKIE wiersze (brak tenant_id
            # w kontekście — backfille w 0005 itd.). Bypass jest JAWNY: ustawiamy GUC
            # `architekt.migration_bypass='on'` (od migracji 0009 to JEDYNY sposób ominięcia
            # policy — pusty `architekt.tenant_id` już NIE otwiera RLS, fail-closed).
            # Poza init_database NIE używaj _pg_pool.acquire() bezpośrednio ani nie ustawiaj
            # migration_bypass — każdy request-time query musi przechodzić przez PgConnection
            # (acquire_http_db / debate_stream_db), które ustawia wyłącznie tenant_id.
            async with _pg_pool.acquire() as conn:
                # Session-scoped (is_local=false) — ważny dla całego acquire, zwolniony przy
                # zwrocie połączenia do puli. Kolejne (runtime) acquire dostaje czysty GUC.
                await conn.execute(
                    "SELECT set_config('architekt.migration_bypass', 'on', false)"
                )
                for stmt in _split_pg_schema(schema_sql):
                    await conn.execute(stmt)
                await _run_pg_migrations(conn)
            logger.info(
                "PostgreSQL pool initialized (%s)",
                re.sub(r":([^@/]*)@", r":****@", url),
            )
            return
        except Exception as exc:
            if pool is not None:
                await pool.close()
            _pg_pool = None
            if is_production():
                raise RuntimeError(
                    f"Inicjalizacja PostgreSQL nieudana w produkcji ({exc}). "
                    "RLS i izolacja tenantów wymagają działającego Postgresa — brak fallbacku SQLite."
                ) from exc
            # Stage 2 hardening (poza produkcją): DATABASE_URL wskazuje Postgres,
            # ale połączenie padło. Domyślnie NIE wpadamy po cichu na SQLite —
            # SQLite nie ma RLS, więc fallback maskowałby brak izolacji per-tenant
            # i dawał fałszywe poczucie bezpieczeństwa podczas testów. Fail-closed.
            #
            # Świadoma furtka dev: AW_ALLOW_SQLITE_FALLBACK=1 przywraca stare
            # zachowanie (np. szybka praca offline bez Dockera) — z głośnym ostrzeżeniem.
            allow_fallback = os.getenv("AW_ALLOW_SQLITE_FALLBACK", "").strip().lower() in (
                "1", "true", "yes",
            )
            if not allow_fallback:
                raise RuntimeError(
                    f"PostgreSQL niedostępny ({exc}), a DATABASE_URL wskazuje Postgres. "
                    "Start przerwany: SQLite nie ma RLS, więc fallback złamałby izolację "
                    "per-tenant. Uruchom bazę (`docker compose up postgres`) albo — jeśli "
                    "naprawdę chcesz dev bez RLS — ustaw AW_ALLOW_SQLITE_FALLBACK=1 "
                    "(lub usuń DATABASE_URL z .env)."
                ) from exc
            logger.warning(
                "⚠️ AW_ALLOW_SQLITE_FALLBACK=1 — PostgreSQL niedostępny (%s), fallback na "
                "SQLite (%s). RLS NIE DZIAŁA — izolacja per-tenant wyłączona. Tylko dev/offline.",
                exc,
                os.getenv("ARCHITEKT_DB_PATH", "data/architekt.db"),
            )
            await sqlite_init_cb()
            return

    await sqlite_init_cb()


async def shutdown_database() -> None:
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None


async def probe_db_ready(sqlite_db_path: Path) -> tuple[bool, str]:
    """Ping aktywnego backendu — (ok, reason) dla /health/ready."""
    if runtime_use_postgres():
        try:
            async with _require_pg_pool().acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True, ""
        except Exception as exc:
            return False, f"postgresql: {exc}"
    try:
        import aiosqlite

        async with aiosqlite.connect(sqlite_db_path) as raw:
            await raw.execute("SELECT 1")
        return True, ""
    except Exception as exc:
        return False, f"sqlite: {exc}"


@asynccontextmanager
async def acquire_http_db(sqlite_db_path: Path) -> AsyncIterator[Any]:
    """Pojedyncze połączenie na żądanie FastAPI."""
    if runtime_use_postgres():
        from db.pg_wrap import PgConnection

        async with _require_pg_pool().acquire() as raw:
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

            @asynccontextmanager
            async def transaction(self) -> AsyncIterator[Any]:
                """Atomowy zakres: commit na czystym wyjściu, rollback przy wyjątku.
                Interfejs zgodny z PgConnection.transaction()."""
                try:
                    yield self
                    await self._c.commit()
                except Exception:
                    await self._c.rollback()
                    raise

        yield _Lite(raw)


@asynccontextmanager
async def debate_stream_db(sqlite_db_path: Path) -> AsyncIterator[Any]:
    """Jedno połączenie na cały cykl SSE debaty."""
    if runtime_use_postgres():
        from db.pg_wrap import PgConnection

        async with _require_pg_pool().acquire() as raw:
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

        @asynccontextmanager
        async def transaction(self) -> AsyncIterator[Any]:
            """Atomowy zakres: commit na czystym wyjściu, rollback przy wyjątku.
            Interfejs zgodny z PgConnection.transaction()."""
            try:
                yield self
                await self._c.commit()
            except Exception:
                await self._c.rollback()
                raise

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
