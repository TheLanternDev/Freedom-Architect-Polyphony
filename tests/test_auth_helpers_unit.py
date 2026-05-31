"""Unit testy `api.routers.auth` helpers — argon2/pbkdf2, JWT issuer/audience."""

from __future__ import annotations

import hashlib
import jwt
import pytest

from api.routers import auth as auth_mod


def test_argon2_hash_and_verify_roundtrip():
    h = auth_mod._hash_password_argon2("haslo-test-123")
    assert h.startswith("$argon2")
    assert auth_mod._verify_password_argon2("haslo-test-123", h) is True
    assert auth_mod._verify_password_argon2("inne-haslo", h) is False


def test_argon2_verify_on_garbage_returns_false():
    """Walidacja: garbage hash → False, nie wyjątek."""
    assert auth_mod._verify_password_argon2("any", "not-a-valid-hash") is False
    assert auth_mod._verify_password_argon2("any", "") is False


def test_is_argon2_hash_detection():
    assert auth_mod._is_argon2_hash("$argon2id$v=19$m=65536,t=2,p=2$...") is True
    assert auth_mod._is_argon2_hash("plain-pbkdf2-hex") is False
    assert auth_mod._is_argon2_hash("") is False


def test_pbkdf2_legacy_hash_is_deterministic():
    """Stary algorytm — używamy tylko do weryfikacji legacy userów."""
    h1 = auth_mod._hash_password_pbkdf2("pass", "salt-x")
    h2 = auth_mod._hash_password_pbkdf2("pass", "salt-x")
    assert h1 == h2
    # Inny salt → inny hash.
    h3 = auth_mod._hash_password_pbkdf2("pass", "salt-y")
    assert h1 != h3
    # Format: hex string.
    bytes.fromhex(h1)


def test_jwt_issuer_audience_from_env(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_ISSUER", "arch-auth")
    monkeypatch.setenv("ARCHITEKT_JWT_AUDIENCE", "architekt-clients")
    assert auth_mod._jwt_issuer() == "arch-auth"
    assert auth_mod._jwt_audience() == "architekt-clients"


def test_jwt_issuer_audience_empty_when_unset(monkeypatch):
    monkeypatch.delenv("ARCHITEKT_JWT_ISSUER", raising=False)
    monkeypatch.delenv("ARCHITEKT_JWT_AUDIENCE", raising=False)
    assert auth_mod._jwt_issuer() == ""
    assert auth_mod._jwt_audience() == ""


def test_make_jwt_produces_decodable_token():
    payload = {"sub": "user-1", "tenant_id": "t-1", "exp": 9999999999}
    token = auth_mod._make_jwt(payload, "secret-key")
    decoded = jwt.decode(token, "secret-key", algorithms=["HS256"])
    assert decoded["sub"] == "user-1"
    assert decoded["tenant_id"] == "t-1"


def test_jwt_secret_from_env(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "topsecret")
    assert auth_mod._jwt_secret() == "topsecret"


def test_jwt_secret_strips_whitespace(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "  spaced  ")
    assert auth_mod._jwt_secret() == "spaced"
