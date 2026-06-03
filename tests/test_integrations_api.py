"""P1-C1: HTTP smoke dla /integrations/*."""

from __future__ import annotations


def test_integrations_status_unconfigured(client_no_redis):
    r = client_no_redis.get("/integrations/status")
    assert r.status_code == 200
    data = r.json()
    assert data["notion"]["configured"] is False
    assert data["todoist"]["configured"] is False
    assert data["google_calendar"]["configured"] is False


def test_notion_export_400_without_env(client_no_redis):
    r = client_no_redis.post("/integrations/notion/export", json={"commitment_ids": [1]})
    assert r.status_code == 400
    assert "NOTION" in r.json()["detail"]


def test_todoist_export_400_without_env(client_no_redis):
    r = client_no_redis.post("/integrations/todoist/export", json={"commitment_ids": [1]})
    assert r.status_code == 400
    assert "TODOIST" in r.json()["detail"]


def test_gcal_export_400_without_env(client_no_redis):
    r = client_no_redis.post("/integrations/gcal/export", json={"commitment_ids": [1]})
    assert r.status_code == 400
    assert "GCAL" in r.json()["detail"]


def test_integrations_require_auth(client_no_auth_bypass):
    r = client_no_auth_bypass.get("/integrations/status")
    assert r.status_code == 401
