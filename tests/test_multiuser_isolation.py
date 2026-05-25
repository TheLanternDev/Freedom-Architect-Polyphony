"""
Faza 4 — multi-user: test izolacji per tenant_id.

Sprawdza, ze dwie sesje z roznymi tenant_id (ContextVar) widza tylko swoje
dane w listach historii oraz po GET-by-id, a tryb 'default' nie miesza sie
z tenant-owanymi danymi.

Uruchomienie:
    pytest tests/test_multiuser_isolation.py -v
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from db import repo
from db.backend import acquire_http_db
from db.connection import init_db
from db.tenant import (
    DEFAULT_TENANT,
    current_tenant_id,
    reset_current_tenant_id,
    set_current_tenant_id,
)


async def _insert_debate(db_path: Path, brief: str) -> int:
    async with acquire_http_db(db_path) as db:
        debate_id = await repo.insert_debate(
            db,
            category="decyzja",
            mode="codzienny",
            brief_description=brief,
            intention=None,
            extra_context=None,
            dream_id=None,
        )
        await db.commit()
        return debate_id


async def _list_recent_ids(db_path: Path) -> list[int]:
    async with acquire_http_db(db_path) as db:
        rows = await repo.list_debates_recent(db, limit=50)
        return [int(r["id"]) for r in rows]


async def _get_debate(db_path: Path, debate_id: int) -> dict | None:
    async with acquire_http_db(db_path) as db:
        return await repo.get_debate_row(db, debate_id)


def test_default_tenant_when_no_jwt(fresh_db_path):
    """Bez wpinki middleware ContextVar zwraca 'default' — wsteczna kompatybilnosc."""

    async def inner():
        await init_db(fresh_db_path)
        assert current_tenant_id() == DEFAULT_TENANT

    asyncio.run(inner())


def test_history_isolation_between_two_tenants(fresh_db_path):
    """Dwa tenants → kazdy widzi tylko swoje debaty w /history."""

    async def inner():
        await init_db(fresh_db_path)

        # Sesja A: tenant-a
        tok_a = set_current_tenant_id("tenant-a")
        try:
            a_id_1 = await _insert_debate(
                fresh_db_path,
                "Decyzja A: czy zatrudnic Operations Managera tej zimy?",
            )
            a_id_2 = await _insert_debate(
                fresh_db_path,
                "Decyzja A: czy ciac oferte o 30% dla nowych klientow?",
            )
        finally:
            reset_current_tenant_id(tok_a)

        # Sesja B: tenant-b
        tok_b = set_current_tenant_id("tenant-b")
        try:
            b_id_1 = await _insert_debate(
                fresh_db_path,
                "Decyzja B: czy wejsc w segment enterprise jeszcze w tym roku?",
            )
        finally:
            reset_current_tenant_id(tok_b)

        # Sesja A widzi tylko swoje
        tok_a = set_current_tenant_id("tenant-a")
        try:
            ids_a = await _list_recent_ids(fresh_db_path)
        finally:
            reset_current_tenant_id(tok_a)
        assert set(ids_a) == {a_id_1, a_id_2}, (
            f"tenant-a powinien widziec {{a_id_1, a_id_2}}, widzi: {ids_a}"
        )

        # Sesja B widzi tylko swoje
        tok_b = set_current_tenant_id("tenant-b")
        try:
            ids_b = await _list_recent_ids(fresh_db_path)
        finally:
            reset_current_tenant_id(tok_b)
        assert set(ids_b) == {b_id_1}, (
            f"tenant-b powinien widziec {{b_id_1}}, widzi: {ids_b}"
        )

        # Tenant 'default' nie miesza sie z tenantami
        ids_default = await _list_recent_ids(fresh_db_path)
        assert ids_default == [], (
            f"'default' nie powinien widziec cudzych debat: {ids_default}"
        )

    asyncio.run(inner())


def test_get_by_id_blocks_cross_tenant_access(fresh_db_path):
    """GET-by-id z wrogiego tenanta nie zwraca obiektu."""

    async def inner():
        await init_db(fresh_db_path)

        tok_a = set_current_tenant_id("tenant-a")
        try:
            a_id = await _insert_debate(
                fresh_db_path,
                "Decyzja A: czy uruchomic retencje klientow od poniedzialku?",
            )
        finally:
            reset_current_tenant_id(tok_a)

        # tenant-a widzi swoja
        tok_a = set_current_tenant_id("tenant-a")
        try:
            row = await _get_debate(fresh_db_path, a_id)
        finally:
            reset_current_tenant_id(tok_a)
        assert row is not None and int(row["id"]) == a_id

        # tenant-b nie widzi (zwracane None mimo poprawnego id)
        tok_b = set_current_tenant_id("tenant-b")
        try:
            row_b = await _get_debate(fresh_db_path, a_id)
        finally:
            reset_current_tenant_id(tok_b)
        assert row_b is None, "tenant-b nie powinien dostac debaty tenant-a po id"

        # default tez nie widzi
        row_def = await _get_debate(fresh_db_path, a_id)
        assert row_def is None, "'default' nie powinien dostac debaty tenant-a po id"

    asyncio.run(inner())
