"""Endpoint feedback dla soft launchu (Tydzień 4 mapy luk).

Cel: zebrać konkretne dane od 3-5 zaproszonych userów bez stawiania
oddzielnej infrastruktury (Typeform/Tally). Każdy feedback wpada do tej
samej bazy co reszta danych, jest izolowany per tenant (RLS) i widoczny
w logach JSON (`api._log.slog`).

NIE wysyłamy maila — feedback przepływa przez normalną warstwę DB+RLS,
nie przez external service. To zmniejsza scope i utrzymuje izolację.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter

from api._log import slog
from api._rate_limit import jwt_or_ip_key

logger = logging.getLogger(__name__)

_limiter = Limiter(key_func=jwt_or_ip_key)

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackPayload(BaseModel):
    """Trzy pytania soft launchu — proste, krótkie, deterministyczne."""

    rating: int = Field(..., ge=1, le=5, description="1=słabo, 5=świetnie")
    what_worked: str = Field("", max_length=2000,
                             description="Co realnie pomogło? (opcjonalne)")
    what_broke: str = Field("", max_length=2000,
                            description="Co było mylące / nie działało? (opcjonalne)")
    debate_id: Optional[int] = Field(
        None, description="ID debaty której dotyczy feedback (opcjonalne)"
    )


@router.post("")
@_limiter.limit("10/minute")
async def submit_feedback(request: Request, payload: FeedbackPayload):
    """Zapisuje feedback usera. Tenant_id pochodzi z ContextVar (http_guard)."""
    try:
        from db import repo
        from db.backend import acquire_http_db
        from db.connection import DB_PATH
    except ImportError:
        repo = None  # type: ignore[assignment]
        acquire_http_db = None  # type: ignore[assignment]
        DB_PATH = None  # type: ignore[assignment]

    sub = getattr(request.state, "architekt_subject", None) or "anonymous"
    ts = datetime.now(timezone.utc).isoformat()

    persisted = False
    if repo is not None and acquire_http_db is not None and hasattr(repo, "insert_feedback"):
        try:
            async with acquire_http_db(DB_PATH) as db:
                await repo.insert_feedback(
                    db,
                    user_subject=sub,
                    rating=payload.rating,
                    what_worked=payload.what_worked.strip(),
                    what_broke=payload.what_broke.strip(),
                    debate_id=payload.debate_id,
                    created_at=ts,
                )
                await db.commit()
            persisted = True
        except Exception as e:
            logger.warning("DB persist feedback failed, falling back to JSONL: %s", e)

    if not persisted:
        # Fallback: append do jsonl. Świadomie nie blokujemy soft launchu
        # gdyby migracja `feedback` tabeli była jeszcze nie wdrożona.
        import json
        import os
        from pathlib import Path

        out_dir = Path(os.getenv("AW_FEEDBACK_DIR") or "data")
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "feedback.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": ts, "user_subject": sub,
                "rating": payload.rating,
                "what_worked": payload.what_worked.strip(),
                "what_broke": payload.what_broke.strip(),
                "debate_id": payload.debate_id,
            }, ensure_ascii=False) + "\n")

    slog(
        "feedback_submitted",
        user=sub, rating=payload.rating,
        what_worked_len=len(payload.what_worked),
        what_broke_len=len(payload.what_broke),
        debate_id=payload.debate_id,
    )
    return {"status": "ok", "ts": ts}
