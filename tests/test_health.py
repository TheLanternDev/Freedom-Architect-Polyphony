"""
Testy endpointu /health — kontrakt v3.3 (Architekt Wolności).

v3.3 raportuje:
- council_agents (zamiast `agents`)
- synthesizer (Syez)
- version = "3.3"
- redis / rada_status / db_status / core_status
- max_active_projects (AKSJOMAT 2)
- sse_endpoint
"""

from __future__ import annotations

import main as main_module


def test_health_returns_200_and_core_fields(client_no_redis):
    resp = client_no_redis.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "alive"
    assert data["version"] == "3.3"
    assert data["sse_endpoint"] == "POST /debate/stream"


def test_health_redis_disconnected_when_client_is_none(client_no_redis):
    data = client_no_redis.get("/health").json()
    assert data["redis"] == "disconnected"


def test_health_reflects_rada_availability(client_no_redis):
    data = client_no_redis.get("/health").json()
    if main_module.RADA_AVAILABLE:
        assert data["council_agents"] == 9
        assert data["synthesizer"] == "Syez"
        assert data["rada_status"] == "aktywna"
    else:
        assert data["council_agents"] == 0
        assert data["rada_status"] == "niedostępna"


def test_health_reports_aksjomat_fields(client_no_redis):
    """AKSJOMAT 1+2: health musi raportować dostępność core, db i limit projektów."""
    data = client_no_redis.get("/health").json()
    assert "core_status" in data
    assert "db_status" in data
    assert "max_active_projects" in data
    assert data.get("llm_backend") in ("none", "anthropic", "xai", "ollama")


def test_health_when_rada_unavailable(client_no_redis, monkeypatch):
    """Wymuszony RADA_AVAILABLE=False → 0 agentów, rada niedostępna."""
    monkeypatch.setattr(main_module, "RADA_AVAILABLE", False)
    data = client_no_redis.get("/health").json()

    assert data["council_agents"] == 0
    assert data["rada_status"] == "niedostępna"
    assert data["status"] == "alive"
    assert data["version"] == "3.3"


def test_health_ready_ok(client_no_redis):
    r = client_no_redis.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"ready": True}


# ── P1-D1: /health/ready sprawdza Redis gdy wymagany (prod, poza demo) ──────────

def _force_redis_required(monkeypatch):
    """Ustaw warunki, w których redis_required_in_prod() == True."""
    import api.startup as startup

    monkeypatch.setattr(startup, "redis_required_in_prod", lambda: True)


def test_ready_503_when_redis_required_but_client_none(client_no_redis, monkeypatch):
    _force_redis_required(monkeypatch)
    monkeypatch.setattr(main_module, "redis_client", None)
    r = client_no_redis.get("/health/ready")
    assert r.status_code == 503
    assert "redis" in r.json()["detail"].lower()


def test_ready_503_when_redis_ping_fails(client_no_redis, monkeypatch):
    _force_redis_required(monkeypatch)

    class _BadRedis:
        async def ping(self):
            raise ConnectionError("redis down")

        async def close(self):
            return None

    monkeypatch.setattr(main_module, "redis_client", _BadRedis())
    r = client_no_redis.get("/health/ready")
    assert r.status_code == 503
    assert "redis" in r.json()["detail"].lower()


def test_ready_200_when_redis_required_and_ping_ok(client_no_redis, monkeypatch):
    _force_redis_required(monkeypatch)

    class _OkRedis:
        async def ping(self):
            return True

        async def close(self):
            return None

    monkeypatch.setattr(main_module, "redis_client", _OkRedis())
    r = client_no_redis.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"ready": True}
