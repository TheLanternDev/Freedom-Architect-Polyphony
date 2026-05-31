"""RLS migration 0002: sprawdzenie składni + integracji z PgConnection.

Test nie odpala realnego Postgresa (CI nie ma). Waliduje:
  1. Plik migracji istnieje i jest niepusty.
  2. Zawiera ENABLE/FORCE ROW LEVEL SECURITY + policy `tenant_isolation`.
  3. PgConnection.execute woła `set_config('architekt.tenant_id', ...)` przed
     właściwym SQL (defense-in-depth dla RLS).
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

MIG = Path(__file__).resolve().parent.parent / "db" / "migrations" / "0002_enable_rls.sql"


def test_migration_file_exists_and_nonempty():
    assert MIG.is_file(), f"missing {MIG}"
    assert MIG.stat().st_size > 200


def test_migration_enables_and_forces_rls_for_protected_tables():
    sql = MIG.read_text()
    protected = [
        "dreams", "debates", "agent_voices", "projects",
        "functionality_items", "completion_audits", "commitments",
        "agent_evolution",
    ]
    for t in protected:
        assert t in sql, f"tabela {t} pominięta w migracji RLS"
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "POLICY tenant_isolation" in sql
    assert "current_setting('architekt.tenant_id', true)" in sql
    # users CELOWO poza RLS — login bez kontekstu (patrz komentarz migracji).
    assert not re.search(r"ALTER TABLE\s+users\s+ENABLE ROW LEVEL", sql)


def test_migration_has_idempotent_guards():
    sql = MIG.read_text()
    assert "DROP POLICY IF EXISTS" in sql
    assert "IF NOT EXISTS" in sql  # CHECK constraints


def test_pg_connection_sets_guc_before_query():
    """Każdy execute MUSI poprzedzić query wywołaniem set_config.
    Bez tego RLS w PG zablokuje wszystkie wiersze (policy nie zmatchuje)."""
    from db.pg_wrap import PgConnection

    calls: list[tuple[str, tuple]] = []

    class FakeRaw:
        async def execute(self, sql, *args):
            calls.append((sql, args))
            return "INSERT 0 1"
        async def fetch(self, sql, *args):
            calls.append((sql, args))
            return []
        async def fetchrow(self, sql, *args):
            calls.append((sql, args))
            return None

    conn = PgConnection(FakeRaw())

    # Symulujemy ustawienie ContextVar z `db.tenant` przed query.
    from db.tenant import set_current_tenant_id, reset_current_tenant_id
    tok = set_current_tenant_id("tenant-x")
    try:
        asyncio.run(conn.execute("UPDATE dreams SET core_dream = ? WHERE id = ?", ("x", "1")))
    finally:
        reset_current_tenant_id(tok)

    # Pierwszy call MUSI być set_config z aktywnym tenant_id.
    assert len(calls) >= 2, "execute powinien wywołać set_config + właściwy SQL"
    first_sql, first_args = calls[0]
    assert "set_config" in first_sql
    assert "'architekt.tenant_id'" in first_sql
    assert first_args == ("tenant-x",)
