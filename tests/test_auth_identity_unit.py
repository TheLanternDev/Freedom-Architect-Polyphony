"""Unit testy `api.auth_identity` — krytyczne dla bezpieczeństwa.

Pokrywa ścieżki które `test_auth_modes.py` (integracyjny przez TestClient) nie
zaglądają w mocno odizolowane: brak sekretu, brak PyJWT, wymóg tenant_id,
issuer/audience, JTI blocklist (Redis OK / Redis brak / Redis crash).
"""

from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from api import auth_identity as ai


# ── _secret ─────────────────────────────────────────────────────────────────


def test_secret_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("ARCHITEKT_JWT_SECRET", raising=False)
    assert ai._secret() is None


def test_secret_returns_none_when_whitespace(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "   ")
    assert ai._secret() is None


def test_secret_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "topsecret")
    assert ai._secret() == "topsecret"


# ── decode_user_jwt ──────────────────────────────────────────────────────────


def _make_token(secret: str, **claims) -> str:
    now = int(time.time())
    payload = {
        "exp": now + 3600,
        "sub": "user-1",
        "tenant_id": "t-1",
        "jti": "jti-test-1",
        **claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_decode_returns_none_without_secret(monkeypatch):
    monkeypatch.delenv("ARCHITEKT_JWT_SECRET", raising=False)
    assert ai.decode_user_jwt("anything") is None


def test_decode_valid_token(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "k")
    monkeypatch.delenv("ARCHITEKT_JWT_AUDIENCE", raising=False)
    monkeypatch.delenv("ARCHITEKT_JWT_ISSUER", raising=False)
    tok = _make_token("k")
    payload = ai.decode_user_jwt(tok)
    assert payload is not None
    assert payload["sub"] == "user-1"
    assert payload["tenant_id"] == "t-1"


def test_decode_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "right")
    tok = _make_token("wrong")
    assert ai.decode_user_jwt(tok) is None


def test_decode_rejects_expired(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "k")
    tok = jwt.encode(
        {"exp": int(time.time()) - 10, "sub": "u", "tenant_id": "t"},
        "k", algorithm="HS256",
    )
    assert ai.decode_user_jwt(tok) is None


def test_decode_requires_sub_claim(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "k")
    tok = jwt.encode(
        {"exp": int(time.time()) + 100, "tenant_id": "t", "jti": "j-1"},
        "k", algorithm="HS256",
    )
    assert ai.decode_user_jwt(tok) is None


def test_decode_requires_jti_claim(monkeypatch):
    """Fail-closed: token bez `jti` jest nierevokable (logout/blocklist nie
    może go unieważnić) → odrzucamy, mimo poprawnego exp/sub/tenant."""
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "k")
    monkeypatch.delenv("ARCHITEKT_JWT_AUDIENCE", raising=False)
    monkeypatch.delenv("ARCHITEKT_JWT_ISSUER", raising=False)
    tok = jwt.encode(
        {"exp": int(time.time()) + 100, "sub": "u", "tenant_id": "t"},
        "k", algorithm="HS256",
    )
    assert ai.decode_user_jwt(tok) is None


def test_decode_enforces_audience_when_configured(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "k")
    monkeypatch.setenv("ARCHITEKT_JWT_AUDIENCE", "architekt")
    # Token bez aud → reject.
    tok = _make_token("k")
    assert ai.decode_user_jwt(tok) is None
    # Token z poprawnym aud → accept.
    tok_ok = _make_token("k", aud="architekt")
    assert ai.decode_user_jwt(tok_ok) is not None


def test_decode_enforces_issuer_when_configured(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "k")
    monkeypatch.setenv("ARCHITEKT_JWT_ISSUER", "arch-auth")
    tok_bad = _make_token("k", iss="someone-else")
    assert ai.decode_user_jwt(tok_bad) is None
    tok_ok = _make_token("k", iss="arch-auth")
    assert ai.decode_user_jwt(tok_ok) is not None


def test_decode_rejects_empty_tenant_when_required(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "k")
    monkeypatch.setenv("AW_REQUIRE_TENANT_JWT_CLAIM", "1")
    tok = jwt.encode(
        {"exp": int(time.time()) + 100, "sub": "u", "tenant_id": "  "},
        "k", algorithm="HS256",
    )
    assert ai.decode_user_jwt(tok) is None


# ── JTI blocklist ────────────────────────────────────────────────────────────


def test_is_jti_blocked_returns_false_without_redis():
    with patch("api.runtime.get_redis", return_value=None):
        assert asyncio.run(ai.is_jti_blocked("any")) is False


def test_is_jti_blocked_true_when_redis_has_key():
    r = MagicMock()
    r.exists = AsyncMock(return_value=1)
    with patch("api.runtime.get_redis", return_value=r):
        assert asyncio.run(ai.is_jti_blocked("blocked-jti")) is True
        r.exists.assert_awaited_once_with("jti:blocked:blocked-jti")


def test_is_jti_blocked_false_on_redis_error():
    r = MagicMock()
    r.exists = AsyncMock(side_effect=ConnectionError("redis down"))
    with patch("api.runtime.get_redis", return_value=r):
        # Bezpiecznie: gdy Redis pada, NIE blokujemy (fail-open dla read).
        assert asyncio.run(ai.is_jti_blocked("any")) is False


def test_block_jti_noop_when_no_redis():
    with patch("api.runtime.get_redis", return_value=None):
        # Nie rzuca; M-4: zwraca False (revoke no-op bez Redis).
        assert asyncio.run(ai.block_jti("x", 60)) is False


def test_block_jti_writes_with_ttl():
    r = MagicMock()
    r.setex = AsyncMock(return_value=True)
    with patch("api.runtime.get_redis", return_value=r):
        # M-4: realny zapis → True.
        assert asyncio.run(ai.block_jti("the-jti", 1800)) is True
        r.setex.assert_awaited_once_with("jti:blocked:the-jti", 1800, "1")


def test_block_jti_swallows_error():
    r = MagicMock()
    r.setex = AsyncMock(side_effect=RuntimeError("oops"))
    with patch("api.runtime.get_redis", return_value=r):
        # NIE rzuca — niedostępność Redisa nie może wywalić logout/refresh.
        # M-4: ale zwraca False — zapis się nie udał, revoke nie jest uczciwy.
        assert asyncio.run(ai.block_jti("x", 60)) is False


# ── decode_user_jwt_checked ─────────────────────────────────────────────────


def test_checked_returns_none_for_invalid_token(monkeypatch):
    monkeypatch.delenv("ARCHITEKT_JWT_SECRET", raising=False)
    assert asyncio.run(ai.decode_user_jwt_checked("garbage")) is None


def test_checked_rejects_blocked_jti(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "k")
    tok = _make_token("k", jti="J1")
    with patch("api.auth_identity.is_jti_blocked",
               AsyncMock(return_value=True)):
        assert asyncio.run(ai.decode_user_jwt_checked(tok)) is None


def test_checked_accepts_when_jti_not_blocked(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "k")
    tok = _make_token("k", jti="J2")
    with patch("api.auth_identity.is_jti_blocked",
               AsyncMock(return_value=False)):
        payload = asyncio.run(ai.decode_user_jwt_checked(tok))
        assert payload is not None
        assert payload["jti"] == "J2"


def test_checked_rejects_token_without_jti(monkeypatch):
    """Fail-closed: brak `jti` → token jest nierevokable, więc `decode_user_jwt`
    odrzuca go już na poziomie `require`, a `decode_user_jwt_checked` zwraca None
    (zmiana semantyki: wcześniej token bez jti przechodził)."""
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", "k")
    tok = jwt.encode(
        {"exp": int(time.time()) + 100, "sub": "u", "tenant_id": "t"},
        "k", algorithm="HS256",
    )  # bez jti
    payload = asyncio.run(ai.decode_user_jwt_checked(tok))
    assert payload is None
