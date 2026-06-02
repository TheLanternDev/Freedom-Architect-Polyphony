"""
Testy pokrycia zmian bezpieczeństwa Stage 1.

Weryfikują:
1. Guard fail-closed — bez sekretów → 401 (bez AW_INSECURE_NO_AUTH)
2. Legacy bearer odrzucony gdy JWT skonfigurowany
3. Admin endpoints fail-closed (403 gdy brak ARCHITEKT_ADMIN_TOKEN)
4. /metrics fail-closed (403 gdy brak ARCHITEKT_ADMIN_TOKEN)
5. RLS pg_wrap raises RuntimeError gdy set_config rzuci wyjątek

UWAGA: conftest.py ustawia AW_INSECURE_NO_AUTH=1 na poziomie modułu.
Testy guard muszą jawnie usunąć tę zmienną przez monkeypatch.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


# ── 1. Guard fail-closed ──────────────────────────────────────────────────


def test_guard_failclosed_without_secrets(client_no_auth_bypass):
    """Brak sekretów + brak AW_INSECURE_NO_AUTH → 401.
    Tech-debt fix: używa fixture client_no_auth_bypass zamiast ręcznego TestClient."""
    r = client_no_auth_bypass.get("/history")
    assert r.status_code == 401
    assert "Brak konfiguracji" in r.json()["detail"] or "sekret" in r.json()["detail"].lower()


def test_guard_insecure_no_auth_bypass_works_in_dev(monkeypatch, client_no_redis):
    """AW_INSECURE_NO_AUTH=1 bez sekretów → pass-through (dev bypass)."""
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)
    monkeypatch.delenv("ARCHITEKT_JWT_SECRET", raising=False)
    monkeypatch.setenv("AW_INSECURE_NO_AUTH", "1")
    r = client_no_redis.get("/history")
    assert r.status_code == 200


# ── 2. Legacy bearer odrzucony gdy JWT aktywny ─────────────────────────────


def test_guard_legacy_bearer_rejected_when_jwt_configured(monkeypatch, client_no_redis):
    """Gdy ARCHITEKT_JWT_SECRET ustawiony, shared API key odrzucony → 401."""
    key = "shared-api-key-value"
    secret = "jwt-unit-secret-key-min-32chars!"
    monkeypatch.setenv("ARCHITEKT_API_KEY", key)
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", secret)

    r = client_no_redis.get("/history", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 401
    detail = r.json()["detail"]
    assert "legacy" in detail.lower() or "JWT" in detail


def test_guard_legacy_bearer_works_without_jwt(monkeypatch, client_no_redis):
    """Gdy brak ARCHITEKT_JWT_SECRET, legacy bearer nadal działa."""
    key = "shared-api-key-value"
    monkeypatch.setenv("ARCHITEKT_API_KEY", key)
    monkeypatch.delenv("ARCHITEKT_JWT_SECRET", raising=False)

    r = client_no_redis.get("/history", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200
    assert r.headers.get("Deprecation") == "true"


# ── 3. Admin endpoints fail-closed ────────────────────────────────────────


def test_admin_trigger_followups_failclosed_no_token(monkeypatch, client_no_redis):
    """Brak ARCHITEKT_ADMIN_TOKEN → /admin/trigger-followups zwraca 403."""
    monkeypatch.delenv("ARCHITEKT_ADMIN_TOKEN", raising=False)
    r = client_no_redis.post("/admin/trigger-followups")
    assert r.status_code == 403
    assert "wyłączony" in r.json()["detail"] or "ARCHITEKT_ADMIN_TOKEN" in r.json()["detail"]


def test_admin_trigger_followups_wrong_token(monkeypatch, client_no_redis):
    """Zły token → 401."""
    monkeypatch.setenv("ARCHITEKT_ADMIN_TOKEN", "correct-token")
    r = client_no_redis.post(
        "/admin/trigger-followups",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 401


def test_admin_rebuild_evolution_failclosed_no_token(monkeypatch, client_no_redis):
    """Brak ARCHITEKT_ADMIN_TOKEN → /admin/rebuild-evolution zwraca 403."""
    monkeypatch.delenv("ARCHITEKT_ADMIN_TOKEN", raising=False)
    r = client_no_redis.post("/admin/rebuild-evolution")
    assert r.status_code == 403


# ── 4. /metrics fail-closed ──────────────────────────────────────────────


def test_metrics_failclosed_no_token(monkeypatch, client_no_redis):
    """Brak ARCHITEKT_ADMIN_TOKEN → /metrics zwraca 403."""
    monkeypatch.delenv("ARCHITEKT_ADMIN_TOKEN", raising=False)
    r = client_no_redis.get("/metrics")
    assert r.status_code == 403


def test_metrics_wrong_token_returns_401(monkeypatch, client_no_redis):
    """Zły token → 401."""
    monkeypatch.setenv("ARCHITEKT_ADMIN_TOKEN", "right-token")
    r = client_no_redis.get(
        "/metrics", headers={"Authorization": "Bearer wrong-token"}
    )
    assert r.status_code == 401


def test_metrics_correct_token_allowed(monkeypatch, client_no_redis):
    """Poprawny token → nie 401/403 (może być 503 jeśli prometheus_client niezainstalowany)."""
    tok = "metrics-admin-tok"
    monkeypatch.setenv("ARCHITEKT_ADMIN_TOKEN", tok)
    r = client_no_redis.get(
        "/metrics", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code in (200, 503)  # 503 = prometheus_client brak


# ── 5. RLS pg_wrap fail-closed przy błędzie set_config ───────────────────


def test_pg_wrap_rls_raises_on_set_config_failure():
    """Stage 1: gdy set_config rzuci wyjątek → RuntimeError (nie cicha kontynuacja)."""
    from db.pg_wrap import PgConnection
    from db.tenant import reset_current_tenant_id, set_current_tenant_id

    class FakeRawBroken:
        _call_count = 0

        async def execute(self, sql, *args):
            self._call_count += 1
            if "set_config" in sql:
                raise RuntimeError("symulowany błąd GUC set_config")
            return "SELECT 1"

        async def fetch(self, sql, *args):
            return []

        async def fetchrow(self, sql, *args):
            return None

    conn = PgConnection(FakeRawBroken())
    tok = set_current_tenant_id("tenant-fail")
    try:
        with pytest.raises(RuntimeError, match="tenant"):
            asyncio.run(
                conn.execute("SELECT * FROM debates WHERE tenant_id = ?", ("tenant-fail",))
            )
    finally:
        reset_current_tenant_id(tok)


def test_pg_wrap_rls_no_query_executed_on_set_config_failure():
    """Po błędzie set_config właściwy query NIE jest wykonywany."""
    from db.pg_wrap import PgConnection
    from db.tenant import reset_current_tenant_id, set_current_tenant_id

    executed_sqls: list[str] = []

    class FakeRawBrokenTracking:
        async def execute(self, sql, *args):
            executed_sqls.append(sql)
            if "set_config" in sql:
                raise RuntimeError("GUC fail")
            return "SELECT 1"

        async def fetch(self, sql, *args):
            executed_sqls.append(sql)
            return []

        async def fetchrow(self, sql, *args):
            executed_sqls.append(sql)
            return None

    conn = PgConnection(FakeRawBrokenTracking())
    tok = set_current_tenant_id("tenant-x")
    try:
        with pytest.raises(RuntimeError):
            asyncio.run(conn.execute("SELECT * FROM dreams", ()))
    finally:
        reset_current_tenant_id(tok)

    # Jedyny wykonany SQL to set_config — właściwy query nie dotknął bazy
    assert len(executed_sqls) == 1
    assert "set_config" in executed_sqls[0]
