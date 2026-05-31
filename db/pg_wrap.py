"""Warstwa asyncpg z API zbliżonym do aiosqlite (execute → kursor z fetchall / lastrowid)."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)

INSERT_RETURNING_TABLES = frozenset(
    {"debates", "projects", "commitments", "completion_audits"}
)


def qmarks_to_pg(sql: str) -> str:
    n = 0

    def repl(_m: re.Match[str]) -> str:
        nonlocal n
        n += 1
        return f"${n}"

    return re.sub(r"\?", repl, sql)


def fix_insert_or_ignore(sql: str) -> str:
    s = sql.strip()
    if s.upper().startswith("INSERT OR IGNORE"):
        return s.replace("INSERT OR IGNORE", "INSERT", 1) + " ON CONFLICT DO NOTHING"
    return sql


def fix_datetime_now(sql: str) -> str:
    return sql.replace("datetime('now')", "NOW()")


def fix_on_conflict_spacing(sql: str) -> str:
    """SQLite ON CONFLICT(col) → Postgres ON CONFLICT (col)."""
    return re.sub(
        r"ON CONFLICT\s*\(\s*([^)]+?)\s*\)",
        r"ON CONFLICT (\1)",
        sql,
        flags=re.IGNORECASE,
    )


class _RowsCursor:
    __slots__ = ("_rows", "rowcount", "lastrowid")

    def __init__(self, rows: list[Any]):
        self._rows = rows
        self.rowcount = len(rows)
        self.lastrowid = None

    async def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    async def fetchall(self) -> list[Any]:
        return self._rows


class _ExecCursor:
    __slots__ = ("rowcount", "lastrowid")

    def __init__(self, *, rowcount: int = 0, lastrowid: Optional[int] = None):
        self.rowcount = rowcount
        self.lastrowid = lastrowid

    async def fetchone(self) -> Any:
        return None

    async def fetchall(self) -> list[Any]:
        return []


class PgConnection:
    """Pojedyncze połączenie asyncpg opakowane pod repo (`db.connection`)."""

    dialect = "postgres"

    def __init__(self, raw: Any):
        self._c = raw

    @staticmethod
    def _parse_rowcount(status: str) -> int:
        parts = status.split()
        if len(parts) >= 2:
            try:
                return int(parts[-1])
            except ValueError:
                pass
        return 0

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        sql_work = fix_insert_or_ignore(sql.strip())
        sql_work = fix_datetime_now(sql_work)
        sql_work = fix_on_conflict_spacing(sql_work)
        sql_pg = qmarks_to_pg(sql_work)
        params_t = tuple(params)

        # RLS (migracja 0002): przed KAŻDYM query ustaw GUC architekt.tenant_id
        # z aktywnego ContextVar. Policy `tenant_isolation` na tabelach z
        # tenant_id porównuje wiersz z tym GUC. `set_config(_, _, false)` =
        # session-level (asyncpg pool ma 1 connection per query w tej klasie,
        # więc race między requestami zamykamy nadpisywaniem PRZED query).
        # Try/except, bo `db.tenant` to opcjonalny import w testach jednostkowych.
        try:
            from db.tenant import current_tenant_id
            await self._c.execute(
                "SELECT set_config('architekt.tenant_id', $1, false)",
                current_tenant_id(),
            )
        except Exception as e:  # pragma: no cover
            logger.warning("RLS GUC set failed: %s — fallback to repo-layer isolation", e)

        up = sql_work.upper().strip()
        if up.startswith("SELECT") or up.startswith("WITH"):
            rows = await self._c.fetch(sql_pg, *params_t)
            return _RowsCursor(list(rows))

        ins = re.match(r"INSERT\s+INTO\s+(\w+)", sql_work, re.I)
        if (
            ins
            and ins.group(1).lower() in INSERT_RETURNING_TABLES
            and "RETURNING" not in sql_pg.upper()
        ):
            sql_ret = sql_pg.rstrip().rstrip(";") + " RETURNING id"
            row = await self._c.fetchrow(sql_ret, *params_t)
            rid = int(row["id"]) if row else None
            return _ExecCursor(rowcount=1, lastrowid=rid)

        status = await self._c.execute(sql_pg, *params_t)
        rc = self._parse_rowcount(status)
        return _ExecCursor(rowcount=rc)

    async def commit(self) -> None:
        """asyncpg w puli — komendy DDL/DML są zatwierdzane automatycznie."""
        return None
