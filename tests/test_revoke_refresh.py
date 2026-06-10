"""M-JTI: /auth/revoke unieważnia też refresh token (logout zabija całą sesję).

Bez tego access JTI trafiał na blocklist, ale refresh token przeżywał
i pozwalał wymintować nowy access — sesja nieśmiertelna mimo wylogowania.
"""

from __future__ import annotations

import time
import uuid

import pytest

SECRET = "jwt-unit-secret-key-min-32chars!"


class _FakeRedis:
    """Minimalny async fake — tylko metody używane przez auth/revoke."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def setex(self, key, ttl, val):
        self.store[key] = val

    async def getdel(self, key):
        return self.store.pop(key, None)

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)

    async def exists(self, key):
        return 1 if key in self.store else 0


@pytest.fixture()
def fake_redis(monkeypatch):
    r = _FakeRedis()
    import api.runtime as runtime

    monkeypatch.setattr(runtime, "get_redis", lambda: r)
    return r


def _access_token(sub: str = "user-a") -> str:
    import jwt

    return jwt.encode(
        {
            "sub": sub,
            "tenant_id": "t-a",
            "exp": int(time.time()) + 900,
            "jti": str(uuid.uuid4()),
        },
        SECRET,
        algorithm="HS256",
    )


def test_revoke_consumes_refresh_token(monkeypatch, client_no_redis, fake_redis):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", SECRET)
    rt = "refresh-" + uuid.uuid4().hex
    fake_redis.store["rt:" + rt] = "user-a:t-a"

    r = client_no_redis.post(
        "/auth/revoke",
        headers={"Authorization": f"Bearer {_access_token()}"},
        json={"refresh_token": rt},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["revoked"] is True
    assert body["refresh_revoked"] is True
    # Refresh zniknął z Redis → /auth/refresh musi odrzucić.
    assert "rt:" + rt not in fake_redis.store
    r2 = client_no_redis.post("/auth/refresh", json={"refresh_token": rt})
    assert r2.status_code == 401


def test_revoke_without_refresh_body_backward_compat(monkeypatch, client_no_redis, fake_redis):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", SECRET)
    r = client_no_redis.post(
        "/auth/revoke",
        headers={"Authorization": f"Bearer {_access_token()}"},
    )
    assert r.status_code == 200
    assert r.json()["revoked"] is True
    assert r.json()["refresh_revoked"] is False
