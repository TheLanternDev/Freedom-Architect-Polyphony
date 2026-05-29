"""Status sesji demo (pozostałe debaty)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.services.demo_guard import demo_usage_for_tenant, is_demo_tenant
from api.settings import demo_config_public, demo_mode_enabled
from db import get_db

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/status")
async def demo_status(request: Request):
    """Zużycie limitu demo dla bieżącego JWT (tylko tenant demo_*)."""
    if not demo_mode_enabled():
        return {"demo": False}

    tenant_id = getattr(request.state, "architekt_tenant_id", None)
    if not is_demo_tenant(tenant_id):
        return {"demo": False, "config": demo_config_public()}

    async for db in get_db():
        usage = await demo_usage_for_tenant(db, str(tenant_id))
        return {"demo": True, "config": demo_config_public(), **usage}

    raise HTTPException(status_code=503, detail="baza niedostępna")
