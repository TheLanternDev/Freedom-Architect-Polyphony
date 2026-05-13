"""Endpointy meta: health, readiness, koszty LLM."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from db import get_db

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health():
    import main as m

    try:
        from config.llm_providers import effective_llm_backend

        llm_b = effective_llm_backend() if m.CORE_AVAILABLE else "none"
    except Exception:
        llm_b = "none"
    return {
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
        "sse_endpoint": "POST /debate/stream",
        "sse_continue_endpoint": "POST /debate/continue/stream",
        "history_endpoint": "GET /history",
        "debate_detail_endpoint": "GET /debate/{id}",
        "commitment_endpoint": "POST /commitment",
        "ready_endpoint": "GET /health/ready",
    }


@router.get("/health/ready")
async def health_ready(db=Depends(get_db)):
    import main as m

    if not m.DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="db niedostępna")
    await db.execute("SELECT 1")
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
