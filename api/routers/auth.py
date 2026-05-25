"""Faza 4/7: wydawanie JWT dla multi-user UI logowania."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

_limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])


def _jwt_secret() -> str:
    return (os.getenv("ARCHITEKT_JWT_SECRET") or "").strip()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=4, max_length=200)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6, max_length=200)
    display_name: Optional[str] = None


_REFRESH_TOKEN_TTL = 30 * 24 * 3600  # 30 dni
_REFRESH_PREFIX = "rt:"


async def _store_refresh_token(rt: str, sub: str, tenant_id: str) -> None:
    from api.runtime import get_redis
    r = get_redis()
    if r is None:
        return
    try:
        await r.setex(f"{_REFRESH_PREFIX}{rt}", _REFRESH_TOKEN_TTL, f"{sub}:{tenant_id}")
    except Exception as e:
        logger.warning("Nie udało się zapisać refresh tokenu: %s", e)


async def _consume_refresh_token(rt: str) -> Optional[tuple[str, str]]:
    """Zwraca (sub, tenant_id) i natychmiast usuwa token (rotation)."""
    from api.runtime import get_redis
    r = get_redis()
    if r is None:
        return None
    try:
        val = await r.getdel(f"{_REFRESH_PREFIX}{rt}")
        if not val:
            return None
        text = val.decode() if isinstance(val, bytes) else val
        parts = text.split(":", 1)
        if len(parts) != 2:
            return None
        return parts[0], parts[1]
    except Exception as e:
        logger.warning("Błąd odczytu refresh tokenu: %s", e)
        return None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    refresh_token: Optional[str] = None  # obecny gdy Redis dostępny
    tenant_id: str
    display_name: Optional[str] = None


def _argon2_hasher():
    from argon2 import PasswordHasher
    return PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


def _hash_password_argon2(password: str) -> str:
    """Argon2id hash (argon2-cffi). Salt wbudowany w hash string."""
    return _argon2_hasher().hash(password)


def _verify_password_argon2(password: str, stored_hash: str) -> bool:
    try:
        return _argon2_hasher().verify(stored_hash, password)
    except Exception:
        return False


def _hash_password_pbkdf2(password: str, salt: str) -> str:
    """Legacy PBKDF2 — używane tylko do weryfikacji starych hashy przy migracji."""
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def _is_argon2_hash(h: str) -> bool:
    return h.startswith("$argon2")


def _jwt_issuer() -> str:
    return (os.getenv("ARCHITEKT_JWT_ISSUER") or "").strip()


def _jwt_audience() -> str:
    return (os.getenv("ARCHITEKT_JWT_AUDIENCE") or "").strip()


def _make_jwt(payload: dict, secret: str) -> str:
    """HS256 JWT via PyJWT — spójne z auth_identity.decode_user_jwt."""
    import jwt as pyjwt

    return pyjwt.encode(payload, secret, algorithm="HS256")


async def _issue_token_pair(sub: str, tenant_id: str) -> tuple[str, Optional[str]]:
    """Wystawia access JWT + refresh token. Zwraca (access_token, refresh_token|None)."""
    secret = _jwt_secret()
    now = int(time.time())
    claims: dict = {
        "sub": sub,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + 86400,
        "jti": str(uuid.uuid4()),
    }
    iss = _jwt_issuer()
    aud = _jwt_audience()
    if iss:
        claims["iss"] = iss
    if aud:
        claims["aud"] = aud
    access = _make_jwt(claims, secret)
    rt = str(uuid.uuid4())
    await _store_refresh_token(rt, sub, tenant_id)
    from api.runtime import get_redis
    refresh = rt if get_redis() is not None else None
    return access, refresh


@router.post("/register", response_model=TokenResponse)
@_limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest):
    secret = _jwt_secret()
    if not secret:
        raise HTTPException(500, "ARCHITEKT_JWT_SECRET nie ustawiony — auth wyłączony.")

    from db import get_db

    pw_hash = _hash_password_argon2(req.password)
    salt = ""  # Argon2id embeds salt in the hash string
    tenant_id = hashlib.sha256(req.username.lower().encode()).hexdigest()[:16]

    async for db in get_db():
        cur = await db.execute("SELECT 1 FROM users WHERE username = ?", (req.username.lower(),))
        if await cur.fetchone():
            raise HTTPException(409, "Użytkownik już istnieje.")
        await db.execute(
            "INSERT INTO users (username, pw_hash, salt, tenant_id, display_name) VALUES (?, ?, ?, ?, ?)",
            (req.username.lower(), pw_hash, salt, tenant_id, req.display_name or req.username),
        )
        await db.commit()

    access, refresh = await _issue_token_pair(req.username.lower(), tenant_id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        tenant_id=tenant_id,
        display_name=req.display_name or req.username,
    )


@router.post("/login", response_model=TokenResponse)
@_limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest):
    secret = _jwt_secret()
    if not secret:
        raise HTTPException(500, "ARCHITEKT_JWT_SECRET nie ustawiony.")

    from db import get_db

    tenant_id: str = ""
    display_name: Optional[str] = None
    async for db in get_db():
        cur = await db.execute(
            "SELECT pw_hash, salt, tenant_id, display_name FROM users WHERE username = ?",
            (req.username.lower(),),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(401, "Nieprawidłowy login lub hasło.")

        pw_hash, salt, tenant_id, display_name = row[0], row[1], row[2], row[3]

        if _is_argon2_hash(pw_hash):
            if not _verify_password_argon2(req.password, pw_hash):
                raise HTTPException(401, "Nieprawidłowy login lub hasło.")
            # Re-hash if Argon2 params changed (argon2-cffi handles this via check_needs_rehash)
            try:
                if _argon2_hasher().check_needs_rehash(pw_hash):
                    new_hash = _hash_password_argon2(req.password)
                    await db.execute(
                        "UPDATE users SET pw_hash = ?, salt = '' WHERE username = ?",
                        (new_hash, req.username.lower()),
                    )
                    await db.commit()
            except Exception:
                pass
        else:
            # Legacy PBKDF2 — verify then upgrade to Argon2id transparently
            if not hmac.compare_digest(_hash_password_pbkdf2(req.password, salt), pw_hash):
                raise HTTPException(401, "Nieprawidłowy login lub hasło.")
            new_hash = _hash_password_argon2(req.password)
            await db.execute(
                "UPDATE users SET pw_hash = ?, salt = '' WHERE username = ?",
                (new_hash, req.username.lower()),
            )
            await db.commit()
            logger.info("Użytkownik %s zmigrowany z PBKDF2 do Argon2id.", req.username.lower())

    access, refresh = await _issue_token_pair(req.username.lower(), tenant_id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        tenant_id=tenant_id,
        display_name=display_name,
    )


@router.get("/me")
async def current_user():
    """Placeholder — faktyczny user bierze się z JWT w http_guard middleware."""
    return {"hint": "Użyj JWT z /auth/login — sub i tenant_id w tokenie."}


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse)
@_limiter.limit("20/minute")
async def refresh_token_endpoint(request: Request, req: RefreshRequest):
    """
    Wymienia refresh token na nowy access JWT + nowy refresh token (rotation).
    Stary refresh token jest natychmiast unieważniany — użyj nowego z odpowiedzi.
    Wymaga Redis. Bez Redis — 503.
    """
    from api.runtime import get_redis
    if get_redis() is None:
        raise HTTPException(503, "Refresh tokeny wymagają Redis — REDIS_URL nie skonfigurowany.")

    result = await _consume_refresh_token(req.refresh_token)
    if result is None:
        raise HTTPException(401, "Nieprawidłowy lub wygasły refresh token.")

    sub, tenant_id = result
    access, new_refresh = await _issue_token_pair(sub, tenant_id)
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        tenant_id=tenant_id,
    )


@router.post("/revoke")
@_limiter.limit("20/minute")
async def revoke_token(request: Request):
    """
    Unieważnia bieżący token JWT (dodaje JTI do blocklist w Redis).
    Używaj przy wylogowaniu. Bez Redis — odpowiada 200 ale nie blokuje (fail-open).
    """
    auth = (request.headers.get("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        raise HTTPException(400, "Brak nagłówka Authorization: Bearer <token>.")
    token = auth[7:].strip()

    from api.auth_identity import decode_user_jwt, block_jti

    payload = decode_user_jwt(token)
    if payload is None:
        raise HTTPException(401, "Nieprawidłowy lub wygasły token.")

    jti = payload.get("jti")
    exp = payload.get("exp", 0)
    if not jti:
        # Token bez JTI (stary format) — nie możemy go zablokować indywidualnie.
        return {"revoked": False, "detail": "Token nie zawiera JTI — wylogowanie tylko po stronie klienta."}

    ttl = max(1, int(exp) - int(time.time()))
    await block_jti(str(jti), ttl)
    logger.info("Token JTI %s unieważniony (TTL=%ds)", jti, ttl)
    return {"revoked": True}
