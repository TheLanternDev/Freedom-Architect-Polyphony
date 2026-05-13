"""Publiczna produkcja: klucz API HTTP oraz token administratora."""

from __future__ import annotations


def test_architekt_api_key_blocks_without_bearer(monkeypatch, client_no_redis):
    monkeypatch.setenv("ARCHITEKT_API_KEY", "secret-test-key")
    r = client_no_redis.get("/history")
    assert r.status_code == 401

    r2 = client_no_redis.get(
        "/history",
        headers={"Authorization": "Bearer secret-test-key"},
    )
    assert r2.status_code == 200


def test_architekt_api_key_health_still_public(monkeypatch, client_no_redis):
    monkeypatch.setenv("ARCHITEKT_API_KEY", "x")
    assert client_no_redis.get("/health").status_code == 200


def test_admin_trigger_requires_bearer_when_token_set(monkeypatch, client_no_redis):
    monkeypatch.setenv("ARCHITEKT_ADMIN_TOKEN", "admintok")
    assert client_no_redis.post("/admin/trigger-followups").status_code == 401

    r = client_no_redis.post(
        "/admin/trigger-followups",
        headers={"Authorization": "Bearer admintok"},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True
