"""Walidacja JWT użytkownika (HS256) — klucz nigdy nie trafia do frontendu."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_JTI_BLOCKLIST_PREFIX = "jti:blocked:"


async def is_jti_blocked(jti: str) -> bool:
    """Sprawdza czy JTI jest na blocklist w Redis. Jeśli Redis niedostępny — przepuszcza."""
    from api.runtime import get_redis
    r = get_redis()
    if r is None:
        return False
    try:
        return bool(await r.exists(f"{_JTI_BLOCKLIST_PREFIX}{jti}"))
    except Exception:
        return False


async def block_jti(jti: str, ttl_seconds: int) -> None:
    """Dodaje JTI do blocklist z TTL równym pozostałemu czasowi życia tokenu."""
    from api.runtime import get_redis
    r = get_redis()
    if r is None:
        return
    try:
        await r.setex(f"{_JTI_BLOCKLIST_PREFIX}{jti}", ttl_seconds, "1")
    except Exception as e:
        logger.warning("Nie udało się zablokować JTI %s: %s", jti, e)


def _secret() -> Optional[str]:
    s = (os.getenv("ARCHITEKT_JWT_SECRET") or "").strip()
    return s or None


def decode_user_jwt(token: str) -> Optional[dict[str, Any]]:
    """
    Dekoduje i weryfikuje Bearer JWT (HS256).

    Opcjonalnie: ARCHITEKT_JWT_ISSUER, ARCHITEKT_JWT_AUDIENCE.
    Claim `tenant_id`: rozdzielenie tenantów (logicznie — persistence per-tenant osobna migracja).
    """
    secret = _secret()
    if not secret:
        return None
    try:
        import jwt
    except ImportError as e:
        logger.warning("PyJWT nie zainstalowany — ustaw pip install PyJWT: %s", e)
        return None

    aud = (os.getenv("ARCHITEKT_JWT_AUDIENCE") or "").strip()
    iss = (os.getenv("ARCHITEKT_JWT_ISSUER") or "").strip()
    decode_kw: dict[str, Any] = {
        "algorithms": ["HS256"],
        "options": {"require": ["exp", "sub"]},
    }
    if aud:
        decode_kw["audience"] = aud
    if iss:
        decode_kw["issuer"] = iss
    try:
        payload = jwt.decode(token, secret, **decode_kw)
    except jwt.PyJWTError:
        return None

    from api.settings import require_tenant_claim

    if require_tenant_claim():
        tid = payload.get("tenant_id")
        if not tid or not str(tid).strip():
            return None

    return dict(payload)


async def decode_user_jwt_checked(token: str) -> Optional[dict[str, Any]]:
    """
    Jak decode_user_jwt, ale dodatkowo sprawdza JTI blocklist w Redis.
    Używaj tej funkcji w http_guard (zamiast sync decode_user_jwt).
    """
    payload = decode_user_jwt(token)
    if payload is None:
        return None
    jti = payload.get("jti")
    if jti and await is_jti_blocked(str(jti)):
        logger.info("JWT z zablokowanym JTI %s odrzucony", jti)
        return None
    return payload
