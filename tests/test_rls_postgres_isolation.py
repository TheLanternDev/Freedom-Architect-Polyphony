"""RLS izolacja egzekwowana PRZEZ BAZĘ (Postgres) — defense-in-depth.

Różnica od test_multiuser_isolation.py:
  • tamten testuje warstwę repo/aplikacji (ContextVar + WHERE tenant_id) na SQLite.
  • TEN testuje, że nawet RAW SELECT bez WHERE tenant_id NIE widzi cudzych
    wierszy, bo blokuje to RLS policy w samym Postgresie. To gwarancja, że
    pojedynczy bug w warstwie repo (zapomniany WHERE) nie wycieka cross-tenant.

Uruchamia się TYLKO gdy realny Postgres jest osiągalny pod TEST_DATABASE_URL
(lub DATABASE_URL). W przeciwnym razie test jest pomijany (CI bez PG).

    TEST_DATABASE_URL=postgresql://architekt:...@localhost:5432/architekt \
        pytest tests/test_rls_postgres_isolation.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

_PG_URL = (os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()


async def _pg_available(url: str) -> bool:
    if not url.lower().startswith(("postgresql://", "postgres://")):
        return False
    try:
        import asyncpg
    except ImportError:
        return False
    try:
        conn = await asyncpg.connect(url, timeout=3)
        await conn.close()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def pg_pool():
    if not await _pg_available(_PG_URL):
        pytest.skip("Postgres niedostępny (ustaw TEST_DATABASE_URL/DATABASE_URL + uruchom bazę).")
    import asyncpg

    pool = await asyncpg.create_pool(_PG_URL, min_size=1, max_size=4)
    # Upewnij się, że schemat + migracje (w tym RLS 0002) są zastosowane.
    from db.backend import _SCHEMA_PG_PATH, _run_pg_migrations, _split_pg_schema

    async with pool.acquire() as conn:
        for stmt in _split_pg_schema(_SCHEMA_PG_PATH.read_text(encoding="utf-8")):
            await conn.execute(stmt)
        await _run_pg_migrations(conn)
    yield pool
    # Sprzątanie testowych wierszy.
    async with pool.acquire() as conn:
        await conn.execute("SELECT set_config('architekt.tenant_id', '', true)")
        await conn.execute("DELETE FROM debates WHERE brief_description LIKE 'RLSTEST::%'")
    await pool.close()


async def _insert_debate(conn, tenant_id: str, brief: str) -> int:
    """INSERT z GUC ustawionym na danego tenanta (jak robi to PgConnection)."""
    async with conn.transaction():
        await conn.execute("SELECT set_config('architekt.tenant_id', $1, true)", tenant_id)
        row = await conn.fetchrow(
            "INSERT INTO debates (tenant_id, category, mode, brief_description) "
            "VALUES ($1, 'decyzja', 'codzienny', $2) RETURNING id",
            tenant_id,
            brief,
        )
        return int(row["id"])


async def test_rls_blocks_cross_tenant_raw_select(pg_pool):
    """RAW SELECT bez WHERE tenant_id widzi TYLKO wiersze aktywnego tenanta."""
    ta = f"tenantA-{uuid.uuid4().hex[:8]}"
    tb = f"tenantB-{uuid.uuid4().hex[:8]}"
    brief_a = f"RLSTEST::{ta}"
    brief_b = f"RLSTEST::{tb}"

    async with pg_pool.acquire() as conn:
        id_a = await _insert_debate(conn, ta, brief_a)
        id_b = await _insert_debate(conn, tb, brief_b)

    # Tenant A: raw SELECT BEZ WHERE tenant_id — RLS musi odfiltrować wiersze B.
    async with pg_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('architekt.tenant_id', $1, true)", ta)
            rows = await conn.fetch("SELECT id, tenant_id FROM debates")
            seen = {int(r["id"]) for r in rows}
            tenants = {r["tenant_id"] for r in rows}

    assert id_a in seen, "Tenant A nie widzi własnego wiersza — RLS za restrykcyjny?"
    assert id_b not in seen, "WYCIEK: Tenant A widzi wiersz Tenanta B mimo RLS!"
    assert tenants == {ta}, f"WYCIEK: w wynikach obce tenanty: {tenants}"


async def test_rls_check_blocks_insert_for_other_tenant(pg_pool):
    """WITH CHECK: nie można wstawić wiersza z cudzym tenant_id przy aktywnym GUC."""
    ta = f"tenantA-{uuid.uuid4().hex[:8]}"
    tb = f"tenantB-{uuid.uuid4().hex[:8]}"

    import asyncpg

    async with pg_pool.acquire() as conn:
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            async with conn.transaction():
                await conn.execute("SELECT set_config('architekt.tenant_id', $1, true)", ta)
                # Próba podszycia: GUC=ta, ale wiersz oznaczony tenantem tb.
                await conn.execute(
                    "INSERT INTO debates (tenant_id, category, mode, brief_description) "
                    "VALUES ($1, 'decyzja', 'codzienny', 'RLSTEST::spoof')",
                    tb,
                )
