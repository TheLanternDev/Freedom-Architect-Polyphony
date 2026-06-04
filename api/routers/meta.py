"""Endpointy meta: health, readiness, koszty LLM."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(tags=["meta"])

# P1-A7: publiczny probe k8s — limit per IP żeby nie floodować SELECT 1.
_ready_limiter = Limiter(key_func=get_remote_address)


@router.get("/health")
async def health():
    import main as m

    from api.settings import demo_config_public

    try:
        from config.llm_providers import effective_llm_backend

        llm_b = effective_llm_backend() if m.CORE_AVAILABLE else "none"
    except Exception:
        llm_b = "none"
    payload: dict[str, object] = {
        "status": "alive",
        "council_agents": len(m.COUNCIL) if m.RADA_AVAILABLE else 0,
        "synthesizer": m.SYNTHESIZER.name if m.RADA_AVAILABLE else None,
        "version": "3.3",
        "redis": "connected" if m.redis_client else "disconnected",
        "rada_status": "aktywna" if m.RADA_AVAILABLE else "niedostępna",
        "db_status": "aktywna" if m.DB_AVAILABLE else "niedostępna",
        "core_status": "aktywne" if m.CORE_AVAILABLE else "niedostępne",
        "max_active_projects": m.MAX_ACTIVE_PROJECTS if m.CORE_AVAILABLE else None,
        "llm_backend": llm_b,
        # Debata biznesowa: nagłówek X-Council-Mode: fa2 (ramowanie w main._stream_debate_inner).
        "fa2_via_header": True,
        "sse_endpoint": "POST /debate/stream",
        "sse_continue_endpoint": "POST /debate/continue/stream",
        "history_endpoint": "GET /history",
        "debate_detail_endpoint": "GET /debate/{id}",
        "commitment_endpoint": "POST /commitment",
        "ready_endpoint": "GET /health/ready",
    }
    demo_cfg = demo_config_public()
    if demo_cfg.get("enabled"):
        payload["demo"] = demo_cfg
    return payload


@router.get("/health/ready")
@_ready_limiter.limit("120/minute")
async def health_ready(request: Request):
    import main as m

    from db import DB_PATH
    from db.backend import probe_db_ready

    if not m.DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="db niedostępna")
    ok, reason = await probe_db_ready(DB_PATH)
    if not ok:
        raise HTTPException(status_code=503, detail=reason or "db niedostępna")

    # P1-D1: gdy Redis jest WYMAGANY (prod, poza demo, z REDIS_URL) — readiness
    # musi go realnie sprawdzić. Inaczej LB dostaje "ready" przy padniętym Redis
    # i kieruje ruch (JTI revoke / rate-limit / refresh) do wadliwej instancji.
    # W dev/demo/SQLite (Redis nieobowiązkowy) pomijamy — bez zmiany zachowania.
    from api.startup import redis_required_in_prod

    if redis_required_in_prod():
        if m.redis_client is None:
            raise HTTPException(status_code=503, detail="redis wymagany, brak połączenia")
        try:
            await asyncio.wait_for(m.redis_client.ping(), timeout=1.0)
        except Exception:
            # Timeout / odrzucone połączenie / błąd protokołu → nie jesteśmy ready.
            raise HTTPException(status_code=503, detail="redis nieosiągalny")

    return {"ready": True}


@router.get("/costs/status")
async def costs_status():
    try:
        from core.cost_tracking import cost_status_payload
    except ImportError:
        cost_status_payload = None  # type: ignore[assignment,misc]

    if cost_status_payload is None:
        raise HTTPException(
            status_code=503,
            detail="moduł cost_tracking niedostępny",
        )
    return await asyncio.to_thread(cost_status_payload)
