"""Freedom Architect 2.0 — sub-app biznesowa montowana pod /business."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(
    title="Freedom Architect 2.0",
    description="Tryb biznesowy Rady Nadzorczej — analityka founder/operator.",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.post("/debate/stream")
async def fa2_debate_stream(request: Request):
    """Proxy: wymusza council_mode=fa2 na głównym pipeline debaty.

    Izolacja/auth: ten endpoint biegnie ZA guardem aplikacji głównej
    (`architekt_http_guard` jako middleware) — montaż `/business` nie omija
    guarda, a ContextVar `tenant_id` propaguje się do `_stream_debate` i do
    generatora SSE. Regresję pilnuje `tests/test_business_fa2_tenant_isolation.py`.

    #F: zależymy od kanonicznych źródeł (serwis), nie od prywatnych
    re-exportów `main`. #G: niepoprawny brief → 422 zamiast 500.
    """
    from pydantic import ValidationError

    from api.services._sse import sse as _sse
    from api.services.debate_orchestrator import (
        RADA_AVAILABLE,
        stream_debate as _stream_debate,
    )
    from main import Brief  # model API zdefiniowany tylko w main

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse(
            {"detail": "Body żądania nie jest poprawnym JSON-em."}, status_code=400
        )
    if not isinstance(body, dict):
        return JSONResponse(
            {"detail": "Body briefu musi być obiektem JSON."}, status_code=422
        )

    try:
        brief = Brief(**body)
    except ValidationError as exc:
        detail = [
            {"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return JSONResponse({"detail": detail}, status_code=422)
    except TypeError as exc:
        return JSONResponse({"detail": f"Nieprawidłowy brief: {exc}"}, status_code=422)

    if not RADA_AVAILABLE:
        from datetime import datetime, timezone

        async def fallback():
            yield _sse("debate_start", {"agents": [], "synthesizer": "unavailable"})
            yield _sse("synthesis_done", {"full_text": "Rada niedostępna"})
            yield _sse("debate_done", {
                "debate_id": None, "agent_count": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return StreamingResponse(fallback(), media_type="text/event-stream")

    return StreamingResponse(
        _stream_debate(brief, council_mode="fa2"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def fa2_health():
    return {"status": "alive", "edition": "business_fa2", "version": "2.0.0"}
