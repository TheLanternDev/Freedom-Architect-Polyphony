"""
RODO: eksport i usunięcie danych konta (tenant_id z JWT).
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from db import repo
from db.backend import acquire_http_db
from db.connection import init_db
from db.tenant import reset_current_tenant_id, set_current_tenant_id

_JWT_SECRET = "jwt-unit-secret-key-min-32chars!"
_CONFIRM = "USUŃ MOJE KONTO"


def _jwt_headers(monkeypatch, *, tenant_id: str, sub: str = "user") -> dict[str, str]:
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", _JWT_SECRET)
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)
    from datetime import datetime, timedelta, timezone

    import jwt

    exp = datetime.now(timezone.utc) + timedelta(hours=2)
    tok = jwt.encode(
        {
            "sub": sub,
            "tenant_id": tenant_id,
            "exp": int(exp.timestamp()),
            "jti": str(uuid.uuid4()),
        },
        _JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {tok}"}


async def _seed_debate(db_path: Path, tenant_id: str, marker: str) -> int:
    tok = set_current_tenant_id(tenant_id)
    try:
        async with acquire_http_db(db_path) as db:
            debate_id = await repo.insert_debate(
                db,
                category="decyzja",
                mode="codzienny",
                brief_description=(
                    f"Debatа RODO {marker} — minimum pięć słów w treści briefu."
                ),
                intention=None,
                extra_context=None,
                dream_id=None,
            )
            await db.execute(
                "UPDATE debates SET synthesis_text = ? WHERE id = ?",
                (f"Synteza {marker}", debate_id),
            )
            await db.commit()
            return debate_id
    finally:
        reset_current_tenant_id(tok)


@pytest.fixture
def jwt_env(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", _JWT_SECRET)
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _no_redis_for_rodo(monkeypatch):
    """Izolacja od lokalnego Redis (JTI blocklist nie przecieka między testami)."""
    import main as main_module

    monkeypatch.setattr(main_module, "redis_client", None)

    def _no_redis():
        return None

    try:
        import api.runtime as rt

        monkeypatch.setattr(rt, "get_redis", _no_redis)
    except Exception:
        pass


def test_export_returns_only_logged_in_tenant(
    client_no_redis, fresh_db_path, jwt_env, monkeypatch
):
    tenant_a = "tenant-rodo-a"
    tenant_b = "tenant-rodo-b"
    asyncio.run(_seed_debate(fresh_db_path, tenant_a, "A"))
    asyncio.run(_seed_debate(fresh_db_path, tenant_b, "B"))

    r_a = client_no_redis.get(
        "/account/export",
        headers=_jwt_headers(monkeypatch, tenant_id=tenant_a, sub="a"),
    )
    assert r_a.status_code == 200
    body_a = r_a.json()
    assert body_a["tenant_id"] == tenant_a
    assert len(body_a["debates"]) == 1
    assert "RODO A" in body_a["debates"][0]["brief_description"]

    r_b = client_no_redis.get(
        "/account/export",
        headers=_jwt_headers(monkeypatch, tenant_id=tenant_b, sub="b"),
    )
    assert r_b.status_code == 200
    assert len(r_b.json()["debates"]) == 1
    assert "RODO B" in r_b.json()["debates"][0]["brief_description"]


def test_delete_without_confirm_returns_400(
    client_no_redis, fresh_db_path, jwt_env, monkeypatch
):
    tenant_a = "tenant-rodo-del-400"
    asyncio.run(_seed_debate(fresh_db_path, tenant_a, "X"))

    r = client_no_redis.request(
        "DELETE",
        "/account",
        headers=_jwt_headers(monkeypatch, tenant_id=tenant_a),
        json={"confirm": "złe potwierdzenie"},
    )
    assert r.status_code == 400


def test_delete_removes_only_target_tenant(
    client_no_redis, fresh_db_path, jwt_env, monkeypatch
):
    tenant_a = "tenant-rodo-purge-a"
    tenant_b = "tenant-rodo-purge-b"
    id_a = asyncio.run(_seed_debate(fresh_db_path, tenant_a, "purgeA"))
    id_b = asyncio.run(_seed_debate(fresh_db_path, tenant_b, "purgeB"))

    r_del = client_no_redis.request(
        "DELETE",
        "/account",
        headers=_jwt_headers(monkeypatch, tenant_id=tenant_a, sub="purge-a"),
        json={"confirm": _CONFIRM},
    )
    assert r_del.status_code == 200
    assert r_del.json()["tenant_id"] == tenant_a
    assert r_del.json()["deleted"]["debates"] >= 1

    async def _row_exists(tid: str, debate_id: int) -> bool:
        tok = set_current_tenant_id(tid)
        try:
            async with acquire_http_db(fresh_db_path) as db:
                row = await repo.get_debate_row(db, debate_id)
                return row is not None
        finally:
            reset_current_tenant_id(tok)

    assert asyncio.run(_row_exists(tenant_a, id_a)) is False
    assert asyncio.run(_row_exists(tenant_b, id_b)) is True


def test_after_delete_export_is_empty(
    client_no_redis, fresh_db_path, jwt_env, monkeypatch
):
    tenant_a = "tenant-rodo-empty"
    asyncio.run(_seed_debate(fresh_db_path, tenant_a, "empty"))

    headers = _jwt_headers(monkeypatch, tenant_id=tenant_a, sub="empty-user")
    r_del = client_no_redis.request(
        "DELETE",
        "/account",
        headers=headers,
        json={"confirm": _CONFIRM},
    )
    assert r_del.status_code == 200

    r_exp = client_no_redis.get("/account/export", headers=headers)
    assert r_exp.status_code == 200
    body = r_exp.json()
    assert body["debates"] == []
    assert body["dreams"] == []
    assert body["users"] == []
