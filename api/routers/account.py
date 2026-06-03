"""RODO: eksport i trwałe usunięcie danych konta (tenant z JWT)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter

from api._rate_limit import jwt_or_ip_key
from api.settings import write_rate_limit
from db import get_db, repo

logger = logging.getLogger(__name__)

# Endpointy `/account/*` są ZAWSZE zaautentykowane → limit per JWT `sub`.
_limiter = Limiter(key_func=jwt_or_ip_key)

router = APIRouter(prefix="/account", tags=["account"])

_CONFIRM_DELETE = "USUŃ MOJE KONTO"


def _require_jwt_tenant(request: Request) -> tuple[str, str]:
    if getattr(request.state, "architekt_auth", None) != "jwt":
        raise HTTPException(
            status_code=401,
            detail="Wymagany token JWT użytkownika (POST /auth/login).",
        )
    tenant_id = getattr(request.state, "architekt_tenant_id", None)
    subject = getattr(request.state, "architekt_subject", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Token JWT bez tenant_id.")
    return str(tenant_id), str(subject or "")


class DeleteAccountRequest(BaseModel):
    confirm: str = Field(..., min_length=1, max_length=200)


@router.get("/export")
@_limiter.limit("30/minute")
async def export_account(request: Request):
    """Prawo dostępu (RODO): JSON wszystkich danych zalogowanego tenanta."""
    tenant_id, _ = _require_jwt_tenant(request)
    from api.services.demo_guard import ensure_not_demo_blocked_route

    ensure_not_demo_blocked_route(tenant_id, "RODO")
    async for db in get_db():
        payload = await repo.export_tenant_data(db, tenant_id=tenant_id)
        payload["exported_at"] = datetime.now(timezone.utc).isoformat()
        return payload
    raise HTTPException(status_code=503, detail="baza niedostępna")


@router.delete("")
@_limiter.limit(write_rate_limit())
async def delete_account(request: Request, body: DeleteAccountRequest):
    """Prawo do usunięcia: purge tenanta z JWT + unieważnienie tokenów."""
    if body.confirm != _CONFIRM_DELETE:
        raise HTTPException(
            status_code=400,
            detail=f'Potwierdź dokładnym tekstem: "{_CONFIRM_DELETE}"',
        )

    tenant_id, _subject = _require_jwt_tenant(request)
    from api.services.demo_guard import ensure_not_demo_blocked_route

    ensure_not_demo_blocked_route(tenant_id, "RODO")

    async for db in get_db():
        deleted = await repo.purge_tenant_data(db, tenant_id=tenant_id)
        await db.commit()

    from api.routers.auth import invalidate_refresh_tokens_for_tenant

    refresh_revoked = await invalidate_refresh_tokens_for_tenant(tenant_id)

    logger.info(
        "RODO purge tenant_id=%s deleted=%s refresh_revoked=%s",
        tenant_id,
        deleted,
        refresh_revoked,
    )
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "deleted": deleted,
        "refresh_tokens_revoked": refresh_revoked,
    }
