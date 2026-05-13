"""Walidacja JWT użytkownika (HS256) — klucz nigdy nie trafia do frontendu."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


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
