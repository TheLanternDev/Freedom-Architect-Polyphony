"""JWT użytkownika i nagłówek serwisowy BFF (obok legacy Bearer API key)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc


def test_service_header_grants_access(monkeypatch, client_no_redis):
    monkeypatch.setenv("ARCHITEKT_API_KEY", "srv-secret")
    monkeypatch.setenv("ARCHITEKT_SERVICE_HEADER", "X-Custom-Service")
    r = client_no_redis.get("/history", headers={"X-Custom-Service": "srv-secret"})
    assert r.status_code == 200


def test_jwt_bearer_without_shared_api_key(monkeypatch, client_no_redis):
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)
    secret = "jwt-unit-secret-key-min-32chars!"
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", secret)

    import jwt

    exp = datetime.now(UTC) + timedelta(hours=2)
    tok = jwt.encode(
        {"sub": "user-42", "exp": int(exp.timestamp()), "jti": "j-mode-1"},
        secret,
        algorithm="HS256",
    )
    r = client_no_redis.get("/history", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200


def test_jwt_tenant_header_mismatch_forbidden(monkeypatch, client_no_redis):
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)
    secret = "jwt-unit-secret-key-min-32chars!"
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", secret)
    monkeypatch.setenv("AW_ENFORCE_TENANT_HEADER", "1")

    import jwt

    exp = datetime.now(UTC) + timedelta(hours=2)
    tok = jwt.encode(
        {
            "sub": "user-42",
            "exp": int(exp.timestamp()),
            "tenant_id": "t-a",
            "jti": "j-mode-2",
        },
        secret,
        algorithm="HS256",
    )
    r = client_no_redis.get(
        "/history",
        headers={
            "Authorization": f"Bearer {tok}",
            "X-Tenant-Id": "t-b",
        },
    )
    assert r.status_code == 403
