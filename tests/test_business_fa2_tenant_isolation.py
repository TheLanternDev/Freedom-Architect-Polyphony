"""Faza 0 — izolacja montowanej sub-appki FA2 (`/business/debate/stream`).

Dowodzi empirycznie, że sub-app `business_fa2` montowana pod `/business`
DZIEDZICZY guard z aplikacji głównej (`architekt_http_guard`) oraz że
ContextVar `tenant_id` ustawiony w guardzie propaguje się do handlera
sub-appki i do generatora SSE wewnątrz `_stream_debate`.

To jest test REGRESJI: poprawność izolacji opiera się na zachowaniu
propagacji ContextVar przez `BaseHTTPMiddleware` do montowanej sub-appki,
które jest wrażliwe na wersję Starlette i historycznie bywało zepsute.
Jeśli upgrade Starlette zerwie propagację — ten test ma paść PIERWSZY,
zanim FA2 zacznie zapisywać debaty pod cudzym tenantem.
"""

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

    salt = "business_iso_salt"

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
    assert debates, "brak debaty w historii tenant A — sub-app nie zapisał pod tenantem A"
    return int(debates[0]["id"])


def test_business_stream_requires_auth(client_no_redis, jwt_auth_env):
    """Guard aplikacji głównej obejmuje montowaną sub-appkę: brak JWT → 401."""
    r = client_no_redis.post(
        "/business/debate/stream",
        json={
            "description": "Brief bez autoryzacji — guard ma odrzucić zanim dojdzie do FA2",
            "category": "decyzja",
            "mode": "codzienny",
        },
    )
    assert r.status_code == 401, r.text


def test_business_stream_invalid_brief_returns_422(client_no_redis, jwt_auth_env):
    """#G: niepoprawny brief (za guardem) → 422, nie 500."""
    tok = _register(client_no_redis, "business_iso_422")
    r = client_no_redis.post(
        "/business/debate/stream",
        json={"category": "decyzja"},  # brak wymaganego description
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 422, r.text


def test_business_debate_isolated_per_tenant(client_no_redis, jwt_auth_env):
    """Debata uruchomiona przez `/business/...` jako tenant A jest niewidoczna dla B."""
    tok_a = _register(client_no_redis, "business_iso_a")
    tok_b = _register(client_no_redis, "business_iso_b")

    payload = {
        "description": "Debata tenant A przez sub-appkę FA2 — test izolacji /business",
        "category": "decyzja",
        "mode": "codzienny",
    }
    with client_no_redis.stream(
        "POST",
        "/business/debate/stream",
        json=payload,
        headers={"Authorization": f"Bearer {tok_a}"},
    ) as resp:
        assert resp.status_code == 200, resp.read()
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
