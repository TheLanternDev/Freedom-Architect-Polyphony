"""Walidacja JWT użytkownika (HS256) — klucz nigdy nie trafia do frontendu."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_JTI_BLOCKLIST_PREFIX = "jti:blocked:"


async def is_jti_blocked(jti: str) -> bool:
    """Sprawdza czy JTI jest na blocklist w Redis.

    Zachowanie przy braku Redis:
    - DEV (AW_ENV != production): fail-open — Redis opcjonalny, logout nie blokuje tokenu.
    - PRODUKCJA: fail-closed — Redis wymagany (preflight check); brak Redis = incydent,
      token z JTI jest odrzucany żeby logout działał deterministycznie.
      Tokeny bez claimu `jti` nie są dotknięte (revocation niemożliwe bez JTI).
    """
    from api.runtime import get_redis
    from api.settings import is_production
    r = get_redis()
    if r is None:
        if is_production():
            # Produkcja: Redis niedostępny = incydent. Fail-closed: blokuj token.
            logger.warning(
                "JTI check: Redis niedostępny w produkcji — token z JTI=%s odrzucony (fail-closed)", jti
            )
            return True
        # Dev/staging: fail-open (Redis opcjonalny).
        return False
    try:
        return bool(await r.exists(f"{_JTI_BLOCKLIST_PREFIX}{jti}"))
    except Exception as e:
        if is_production():
            logger.error("JTI Redis error w produkcji (fail-closed): %s", e)
            return True
        logger.warning("JTI Redis error (fail-open dev): %s", e)
        return False


async def block_jti(jti: str, ttl_seconds: int) -> bool:
    """Dodaje JTI do blocklist z TTL równym pozostałemu czasowi życia tokenu.

    Zwraca True tylko gdy JTI realnie trafił do blocklist. False gdy Redis jest
    niedostępny lub zapis padł — wtedy revoke jest no-op i caller (`/auth/revoke`)
    NIE może uczciwie zwrócić `revoked: true` (M-4).
    """
    from api.runtime import get_redis
    r = get_redis()
    if r is None:
        return False
    try:
        await r.setex(f"{_JTI_BLOCKLIST_PREFIX}{jti}", ttl_seconds, "1")
        return True
    except Exception as e:
        logger.warning("Nie udało się zablokować JTI %s: %s", jti, e)
        return False


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
        # `jti` wymagany (fail-closed): bez niego token jest nierevokable —
        # logout/blocklist (`decode_user_jwt_checked` → `is_jti_blocked`) nie
        # może go unieważnić. Wszyscy wystawcy (`api/routers/auth.py`:
        # login/refresh/demo-guest) już dodają `jti`. Odrzucamy więc wyłącznie
        # tokeny, których i tak nie dałoby się odwołać.
        "options": {"require": ["exp", "sub", "jti"]},
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
