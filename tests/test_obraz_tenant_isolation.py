"""Checkpoint 2 — izolacja Obrazu Użytkownika per tenant+user.

Obraz zdestylowany dla usera A jest niewidoczny dla usera B
(`GET /personal/onboarding/obraz`). Zero LLM (fallback deterministyczny).
"""

from __future__ import annotations

import hashlib

import pytest

from core import obraz_uzytkownika as ou

_JWT_SECRET = "jwt-unit-secret-key-min-32chars!"
_PASSWORD = "securepass123"


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setattr(ou, "effective_llm_backend", lambda: "none")


@pytest.fixture
def jwt_auth_env(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", _JWT_SECRET)
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)
    monkeypatch.delenv("AW_INSECURE_NO_AUTH", raising=False)
    from api.routers import auth as auth_mod

    salt = "obraz_iso_salt"

    def _hash(p: str) -> str:
        return hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), 100_000).hex()

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


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_obraz_isolated_per_user(client_no_redis, jwt_auth_env):
    tok_a = _register(client_no_redis, "obraz_iso_a")
    tok_b = _register(client_no_redis, "obraz_iso_b")

    # A zapisuje odpowiedzi i syntetyzuje Obraz
    save = client_no_redis.post(
        "/personal/onboarding/save",
        json={"answers": [
            {"question_idx": 14, "answer": "Nie zgodzę się na zdradę wartości."},
            {"question_idx": 23, "answer": "Jesteś na właściwej drodze."},
        ]},
        headers=_h(tok_a),
    )
    assert save.status_code == 200, save.text

    syn = client_no_redis.post("/personal/onboarding/synthesize", headers=_h(tok_a))
    assert syn.status_code == 200, syn.text
    assert syn.json()["obraz"]["zdanie_dla_siebie"] == "Jesteś na właściwej drodze."

    # A widzi swój Obraz
    own = client_no_redis.get("/personal/onboarding/obraz", headers=_h(tok_a))
    assert own.status_code == 200
    assert own.json()["obraz"] is not None
    assert own.json()["obraz"]["zdanie_dla_siebie"] == "Jesteś na właściwej drodze."

    # B NIE widzi Obrazu A (izolacja per user_subject)
    other = client_no_redis.get("/personal/onboarding/obraz", headers=_h(tok_b))
    assert other.status_code == 200
    assert other.json()["obraz"] is None
