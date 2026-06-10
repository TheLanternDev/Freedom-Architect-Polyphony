"""Warstwa asyncpg z API zbliżonym do aiosqlite (execute → kursor z fetchall / lastrowid)."""

from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional, Sequence

logger = logging.getLogger(__name__)

INSERT_RETURNING_TABLES = frozenset(
    {"debates", "projects", "commitments", "completion_audits"}
)


_DOLLAR_TAG_RE = re.compile(r"\$[A-Za-z0-9_]*\$")


def qmarks_to_pg(sql: str) -> str:
    """Zamienia placeholdery `?` (styl aiosqlite) na `$1, $2, ...` (asyncpg).

    NIE dotyka `?` które nie są placeholderami — wcześniejsze ślepe `re.sub(r"\\?")`
    psuło: literały tekstowe (`'why?'`), identyfikatory w cudzysłowie i bloki
    dollar-quoted (`$$...$$`). Skaner pomija ich zawartość.

    Kontrakt: SQL wchodzący tu pochodzi ze stylu SQLite, gdzie samotny `?` jest
    ZAWSZE placeholderem (SQLite nie ma jsonb `?`). Wieloznakowe operatory jsonb
    `?|` i `?&` są rozpoznawane i zachowywane. Gołego operatora jsonb `?`
    (istnienia klucza) w tej warstwie celowo nie wspieramy — nie występuje w
    zapytaniach SQLite-origin; PG-specyficzne zapytania jsonb używaj na raw
    połączeniu (poza tym translatorem).
    """
    out: list[str] = []
    n = 0
    i = 0
    length = len(sql)
    in_squote = False  # '...'
    in_dquote = False  # "..."
    dollar_tag: Optional[str] = None  # aktywny tag $tag$

    while i < length:
        ch = sql[i]

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                out.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                out.append(ch)
                i += 1
            continue

        if in_squote:
            out.append(ch)
            if ch == "'":
                if i + 1 < length and sql[i + 1] == "'":  # '' = escaped
                    out.append("'")
                    i += 2
                    continue
                in_squote = False
            i += 1
            continue

        if in_dquote:
            out.append(ch)
            if ch == '"':
                if i + 1 < length and sql[i + 1] == '"':  # "" = escaped
                    out.append('"')
                    i += 2
                    continue
                in_dquote = False
            i += 1
            continue

        # poza literałami
        if ch == "'":
            in_squote = True
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_dquote = True
            out.append(ch)
            i += 1
            continue
        if ch == "$":
            m = _DOLLAR_TAG_RE.match(sql, i)
            if m:
                dollar_tag = m.group(0)
                out.append(dollar_tag)
                i += len(dollar_tag)
                continue
        if ch == "?":
            nxt = sql[i + 1] if i + 1 < length else ""
            prv = sql[i - 1] if i > 0 else ""
            # operatory jsonb: ?| ?& ?? — nie placeholder
            if nxt in ("|", "&", "?") or prv == "?":
                out.append(ch)
                i += 1
                continue
            n += 1
            out.append(f"${n}")
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


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
        # True wewnątrz `async with conn.transaction()` — wtedy execute() NIE
        # otwiera własnej transakcji per-statement (atomowość wielu zapisów).
        self._in_tx = False

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

        # RLS (migracja 0002): GUC architekt.tenant_id jest TRANSACTION-LOCAL
        # (`set_config(_, _, true)`) i ustawiany wewnątrz jawnej transakcji razem
        # z właściwym query. Policy `tenant_isolation` porównuje wiersz z tym GUC.
        # Stage 2 hardening: transaction-local oznacza, że GUC NIE przeżywa zwrotu
        # połączenia do puli asyncpg — automatyczny reset na końcu transakcji
        # eliminuje ryzyko, że kolejny request odziedziczy tenant poprzednika
        # (izolacja przez mechanizm, nie przez konwencję „set przed każdym query").
        # Fail-closed: przy błędzie set_config przerywamy query (RuntimeError → 500),
        # bo brak kontekstu tenanta = ryzyko cross-tenant access.
        # Jedyny wyjątek: ImportError db.tenant (testy jednostkowe bez DB) — tam
        # RLS Postgres nie istnieje, więc import-miss jest bezpieczny.
        async def _dispatch() -> Any:
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

        # Wewnątrz jawnej `transaction()` GUC jest już ustawiony i transakcja
        # otwarta — nie otwieramy kolejnej (inaczej każdy statement byłby
        # osobnym savepointem i `commit()` na wyjściu CM nie dawałby atomowości
        # wielu zapisów). Po prostu dispatch w bieżącej transakcji.
        if self._in_tx:
            return await _dispatch()

        try:
            from db.tenant import current_tenant_id
        except ImportError:
            return await _dispatch()  # testy jednostkowe bez db.tenant — RLS nieaktywne

        tid = (current_tenant_id() or "").strip()
        if not tid:
            raise RuntimeError(
                "RLS: pusty tenant_id — query przerwane (fail-closed). "
                "Request musi przejść przez http_guard lub jawnie ustawić ContextVar."
            )

        async with self._c.transaction():
            await self._set_tenant_guc(tid)
            return await _dispatch()

    async def _set_tenant_guc(self, tid: str) -> None:
        """Ustawia transaction-local GUC `architekt.tenant_id` dla RLS.
        Fail-closed: błąd przerywa query (RuntimeError → 500)."""
        try:
            await self._c.execute(
                "SELECT set_config('architekt.tenant_id', $1, true)", tid
            )
        except Exception as e:  # pragma: no cover
            logger.error(
                "RLS: set_config('architekt.tenant_id') failed: %s — przerywam query", e
            )
            raise RuntimeError(
                f"Nie można ustawić kontekstu tenanta RLS — query przerwane: {e}"
            ) from e

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["PgConnection"]:
        """Atomowy zakres wielu zapisów: commit na czystym wyjściu, rollback przy
        wyjątku. GUC tenanta ustawiany RAZ; wewnętrzne execute() reużywają tej
        transakcji (nie otwierają własnych). Interfejs zgodny z SQLite `_Lite`.

        Świadomie NIE zmieniamy domyślnego execute() na odroczony commit —
        chroni to długie strumienie SSE przed jedną wielominutową transakcją
        trzymającą locki. Atomowości używaj jawnie tam, gdzie jest potrzebna.
        """
        set_guc = True
        tid = ""
        try:
            from db.tenant import current_tenant_id
            tid = (current_tenant_id() or "").strip()
        except ImportError:
            set_guc = False  # testy bez db.tenant — RLS nieaktywne
        if set_guc and not tid:
            raise RuntimeError(
                "RLS: pusty tenant_id — transakcja przerwana (fail-closed)."
            )
        async with self._c.transaction():
            if set_guc:
                await self._set_tenant_guc(tid)
            prev = self._in_tx
            self._in_tx = True
            try:
                yield self
            finally:
                self._in_tx = prev

    async def commit(self) -> None:
        """No-op poza `transaction()`: execute() auto-commit'uje per-statement.
        Atomowość wielu zapisów uzyskasz przez `async with conn.transaction():`."""
        return None
