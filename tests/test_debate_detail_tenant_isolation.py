"""P1-A3: debata z tenant A niewidoczna dla tenant B (GET /debate/{id})."""

from __future__ import annotations

import hashlib

import pytest

_JWT_SECRET = "jwt-unit-secret-key-min-32chars!"
_PASSWORD = "securepass123"


@pytest.fixture
def jwt_auth_env(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", _JWT_SECRET)
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)
    monkeypatch.delenv("AW_INSECURE_NO_AUTH", raising=False)
    from api.routers import auth as auth_mod

    salt = "debate_iso_salt"

    def _hash(p: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", p.encode(), salt.encode(), 100_000
        ).hex()

    monkeypatch.setattr(auth_mod, "_hash_password_argon2", _hash)
    monkeypatch.setattr(auth_mod, "_is_argon2_hash", lambda _h: False)
    monkeypatch.setattr(auth_mod, "_hash_password_pbkdf2", lambda p, _s: _hash(p))


def _register(client, username: str) -> str:
    r = client.post(
        "/auth/register",
        json={"username": username, "password": _PASSWORD, "display_name": username},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _last_debate_id(client, token: str) -> int:
    hist = client.get("/history", headers={"Authorization": f"Bearer {token}"})
    assert hist.status_code == 200
    debates = hist.json().get("debates") or []
    assert debates, "brak debaty w historii tenant A"
    return int(debates[0]["id"])


def test_debate_detail_isolated_per_tenant(client_no_redis, jwt_auth_env):
    tok_a = _register(client_no_redis, "debate_iso_a")
    tok_b = _register(client_no_redis, "debate_iso_b")

    payload = {
        "description": "Debaty tenant A — test izolacji GET debate detail endpoint",
        "category": "decyzja",
        "mode": "codzienny",
    }
    with client_no_redis.stream(
        "POST",
        "/debate/stream",
        json=payload,
        headers={"Authorization": f"Bearer {tok_a}"},
    ) as resp:
        assert resp.status_code == 200
        for _ in resp.iter_text():
            pass

    debate_id = _last_debate_id(client_no_redis, tok_a)
    own = client_no_redis.get(
        f"/debate/{debate_id}",
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert own.status_code == 200

    other = client_no_redis.get(
        f"/debate/{debate_id}",
        headers={"Authorization": f"Bearer {tok_b}"},
    )
    assert other.status_code == 404
