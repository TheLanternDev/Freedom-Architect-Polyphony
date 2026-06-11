"""Endpointy administracyjne (`/admin/*`) — ścieżka uprzywilejowana.

Wydzielone z `main.py` (tech-debt punkt 4): skupienie tras admin w jednym
module zmniejsza powierzchnię ataku i ułatwia audyt — każdy endpoint tutaj
MUSI przejść przez `_require_admin` (fail-closed na brak/zły `ARCHITEKT_ADMIN_TOKEN`).

UWAGA bezpieczeństwo: te trasy mają WŁASNĄ autoryzację bearer-tokenem i są
celowo pomijane przez `architekt_http_guard` (`_admin_self_auth_paths`), żeby
admin token nie kolidował z `Authorization` używanym do JWT (P0-A1). Auth jest
więc egzekwowane wyłącznie tutaj — nie osłabiać `_require_admin`.

Globalne z `main.py` (`_run_phase2_startup_tasks`, `get_db`, `DB_AVAILABLE`,
`COUNCIL`, `RADA_AVAILABLE`, `repo`) sięgamy lazy przez `import main as m`
WEWNĄTRZ handlerów — ten sam wzorzec co `api/routers/meta.py`, żeby uniknąć
cyklicznego importu przy ładowaniu modułu.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from db import get_db  # `db` nie importuje `main` → brak cyklu (jak w main.py)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(authorization: Optional[str]) -> None:
    """Fail-closed: token zawsze wymagany; brak → 403, zły → 401.

    Stała ścieżka dla wszystkich tras admin — jedno miejsce do audytu auth.
    """
    admin_tok = (os.getenv("ARCHITEKT_ADMIN_TOKEN") or "").strip()
    if not admin_tok:
        raise HTTPException(
            status_code=403,
            detail="ARCHITEKT_ADMIN_TOKEN nie ustawiony — endpoint /admin wyłączony.",
        )
    auth = (authorization or "").strip()
    if not hmac.compare_digest(auth, f"Bearer {admin_tok}"):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing Authorization bearer for admin",
        )


PW_RESET_PREFIX = "pwreset:"
PW_RESET_TTL = 1800  # 30 min


class PasswordResetTokenRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)


@router.post("/users/password-reset-token")
async def admin_issue_password_reset_token(
    body: PasswordResetTokenRequest,
    authorization: Optional[str] = Header(None),
):
    """P1-E2: jednorazowy token resetu hasła, wydawany przez operatora.

    Model founders/BYOK: brak infrastruktury e-mail — operator dostarcza token
    użytkownikowi out-of-band. Token: 256-bit urlsafe; w Redis ląduje wyłącznie
    sha256(token) z TTL 30 min (wzorzec jak refresh tokeny). Single-use —
    konsumpcja w `/auth/password-reset/confirm` przez GETDEL.
    Fail-closed: brak Redis → 503 (żadnego fallbacku in-memory dla sekretów).
    """
    _require_admin(authorization)
    from api.runtime import get_redis

    r = get_redis()
    if r is None:
        raise HTTPException(
            status_code=503,
            detail="Redis niedostępny — reset hasła wyłączony (fail-closed).",
        )
    username = body.username.strip().lower()
    async for db in get_db():
        cur = await db.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        )
        if not await cur.fetchone():
            # Endpoint admin-only — 404 nie jest wektorem enumeracji.
            raise HTTPException(status_code=404, detail="Użytkownik nie istnieje.")
    token = secrets.token_urlsafe(32)
    h = hashlib.sha256(token.encode()).hexdigest()
    try:
        await r.setex(f"{PW_RESET_PREFIX}{h}", PW_RESET_TTL, username)
    except Exception as e:
        logger.error("password-reset-token: zapis Redis padł: %s", e)
        raise HTTPException(status_code=503, detail="Zapis tokenu nie powiódł się.")
    logger.info("Wydano token resetu hasła dla %s (TTL %ss).", username, PW_RESET_TTL)
    return {
        "username": username,
        "reset_token": token,
        "expires_in_seconds": PW_RESET_TTL,
        "single_use": True,
        "confirm_endpoint": "POST /auth/password-reset/confirm",
    }


@router.post("/trigger-followups")
async def admin_trigger_followups(
    authorization: Optional[str] = Header(None),
):
    """
    Idempotentny „kopniak" Fazy 2: przeterminowane follow-upy + synchronizacja projektów.

    Wymaga nagłówka `Authorization: Bearer <ARCHITEKT_ADMIN_TOKEN>`.
    Bez ustawionego tokenu endpoint jest wyłączony (fail-closed).
    """
    _require_admin(authorization)

    import main as m

    await m._run_phase2_startup_tasks()
    return {"ok": True}


@router.post("/rebuild-evolution")
async def admin_rebuild_evolution(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db),
):
    """Przebudowuje rolling notatki ewolucyjne dla wszystkich agentów.

    Wymaga nagłówka `Authorization: Bearer <ARCHITEKT_ADMIN_TOKEN>`.
    Bez ustawionego tokenu endpoint jest wyłączony (fail-closed).
    """
    _require_admin(authorization)

    import main as m

    if not m.DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="DB niedostępna")

    try:
        from core.agent_learner import run_full_evolution_cycle

        agent_names = [a.name for a in m.COUNCIL] if m.RADA_AVAILABLE else []
        # Atomowo: wszystkie notatki ewolucyjne zapisują się razem albo wcale.
        # Wcześniej każdy merge auto-commit'ował się osobno (pg_wrap), a `commit()`
        # był no-op → częściowa awaria zostawiała niespójny stan.
        async with db.transaction():
            results = await run_full_evolution_cycle(db, m.repo, agent_names)
        return {"ok": True, "agents_updated": list(results.keys())}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("rebuild-evolution failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
