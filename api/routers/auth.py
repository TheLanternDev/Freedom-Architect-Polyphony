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

from api._rate_limit import jwt_or_ip_key

logger = logging.getLogger(__name__)

# Rate limit per JWT `sub` z fallbackiem na IP (patrz `api._rate_limit`).
# Dla `/auth/*` JWT najczęściej JESZCZE nie istnieje (to ścieżki login/refresh),
# więc realnie limit pójdzie po IP — co dla tych endpointów jest poprawne.
_limiter = Limiter(key_func=jwt_or_ip_key)

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


async def invalidate_refresh_tokens_for_tenant(tenant_id: str) -> int:
    """Usuwa refresh tokeny Redis przypisane do tenant_id (RODO — usunięcie konta)."""
    from api.runtime import get_redis

    r = get_redis()
    if r is None:
        return 0
    removed = 0
    try:
        async for key in r.scan_iter(match=f"{_REFRESH_PREFIX}*"):
            val = await r.get(key)
            if val is None:
                continue
            text = val.decode() if isinstance(val, bytes) else str(val)
            parts = text.split(":", 1)
            if len(parts) == 2 and parts[1] == tenant_id:
                await r.delete(key)
                removed += 1
    except Exception as e:
        logger.warning("invalidate_refresh_tokens_for_tenant: %s", e)
    return removed


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


async def _issue_token_pair(
    sub: str,
    tenant_id: str,
    *,
    ttl_seconds: int = 86400,
    extra_claims: dict | None = None,
) -> tuple[str, Optional[str]]:
    """Wystawia access JWT + refresh token. Zwraca (access_token, refresh_token|None)."""
    secret = _jwt_secret()
    now = int(time.time())
    claims: dict = {
        "sub": sub,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + max(60, ttl_seconds),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        claims.update(extra_claims)
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
    from api.settings import demo_mode_enabled

    if demo_mode_enabled():
        raise HTTPException(
            403,
            detail="Rejestracja wyłączona w trybie demo — użyj POST /auth/demo.",
        )

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


@router.post("/demo", response_model=TokenResponse)
@_limiter.limit("15/minute")
async def demo_session(request: Request):
    """Sesja gościa demo — JWT z tenant_id demo_* i limitem debat."""
    from api.settings import demo_jwt_ttl_seconds, demo_mode_enabled

    if not demo_mode_enabled():
        raise HTTPException(404, detail="Tryb demo wyłączony.")

    secret = _jwt_secret()
    if not secret:
        raise HTTPException(500, "ARCHITEKT_JWT_SECRET nie ustawiony — demo wymaga JWT.")

    guest = uuid.uuid4().hex[:16]
    sub = f"demo:{guest}"
    tenant_id = f"demo_{guest}"
    access, refresh = await _issue_token_pair(
        sub,
        tenant_id,
        ttl_seconds=demo_jwt_ttl_seconds(),
        extra_claims={"demo": True},
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        tenant_id=tenant_id,
        display_name="Gość demo",
    )


@router.get("/me")
async def current_user(request: Request):
    """Tożsamość bieżącego usera z aktywnego JWT (ustawiona przez http_guard).

    L-1: zamiast placeholdera zwraca realne dane. `sub`/`tenant_id` pochodzą z
    `request.state` (middleware zweryfikował JWT). `display_name` dociągamy z
    tabeli `users` best-effort (poza JWT). Brak ważnej tożsamości → 401, spójnie
    z resztą API (nie udajemy zalogowania).
    """
    sub = getattr(request.state, "architekt_subject", None)
    tenant_id = getattr(request.state, "architekt_tenant_id", None)
    auth_kind = getattr(request.state, "architekt_auth", None)

    # Tożsamość per-user istnieje tylko przy JWT. Legacy bearer / service-header
    # nie niosą `sub` z tokenu → /me nie ma czego zwrócić.
    if auth_kind != "jwt" or not sub:
        raise HTTPException(
            401,
            detail="Brak tożsamości użytkownika — zaloguj się przez POST /auth/login (JWT).",
        )

    display_name: Optional[str] = None
    try:
        from db import get_db

        async for db in get_db():
            cur = await db.execute(
                "SELECT display_name FROM users WHERE username = ?", (str(sub),)
            )
            row = await cur.fetchone()
            if row:
                display_name = row[0]
    except Exception as e:  # DB opcjonalna dla tej odpowiedzi — nie blokuj /me
        logger.debug("/me: nie udało się pobrać display_name: %s", e)

    return {
        "sub": sub,
        "tenant_id": tenant_id,
        "display_name": display_name,
        "auth": auth_kind,
    }


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
    # M-4: nie kłam o wyniku. block_jti zwraca True tylko gdy JTI realnie trafił
    # do blocklist w Redis. Bez Redis revoke jest no-op po stronie serwera —
    # zwracamy revoked:false, żeby klient wiedział, że musi przynajmniej wyczyścić
    # token lokalnie (token pozostaje ważny do wygaśnięcia exp).
    blocked = await block_jti(str(jti), ttl)
    if not blocked:
        logger.warning(
            "Token JTI %s NIE unieważniony serwerowo (Redis niedostępny) — "
            "revoke no-op, token ważny do exp.", jti
        )
        return {
            "revoked": False,
            "detail": (
                "Revocation niedostępna (brak Redis) — token pozostaje ważny do "
                "wygaśnięcia. Wyczyść token po stronie klienta."
            ),
        }
    logger.info("Token JTI %s unieważniony (TTL=%ds)", jti, ttl)
    return {"revoked": True}
