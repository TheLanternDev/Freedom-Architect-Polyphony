"""Freedom Architect 2.0 — sub-app biznesowa montowana pod /business."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

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
    """Proxy: wymusza council_mode=fa2 na głównym pipeline debaty."""
    import main as m

    body = await request.json()
    from main import Brief
    brief = Brief(**body)

    if not m.RADA_AVAILABLE:
        from datetime import datetime, timezone
        async def fallback():
            yield m._sse("debate_start", {"agents": [], "synthesizer": "unavailable"})
            yield m._sse("synthesis_done", {"full_text": "Rada niedostępna"})
            yield m._sse("debate_done", {
                "debate_id": None, "agent_count": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return StreamingResponse(fallback(), media_type="text/event-stream")

    return StreamingResponse(
        m._stream_debate(brief, council_mode="fa2"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def fa2_health():
    return {"status": "alive", "edition": "business_fa2", "version": "2.0.0"}
