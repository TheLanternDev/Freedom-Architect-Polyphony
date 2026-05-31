"""Endpointy „personal mode": onboarding (20 pytań), codzienny rytuał."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from personal_v1.rituals.onboarding import PYTANIA as ONBOARDING_PYTANIA
from personal_v1.rituals.daily import PYTANIA_PORANNE, PYTANIA_WIECZORNE

router = APIRouter(prefix="/personal", tags=["personal"])

@router.get("/onboarding/questions")
def onboarding_questions():
    return {"items": ONBOARDING_PYTANIA, "ton": "lagodny", "tempo": "ile_chcesz"}


class OnboardingAnswer(BaseModel):
    question_idx: int = Field(..., ge=0, lt=len(ONBOARDING_PYTANIA))
    answer: str = Field(..., max_length=4000)


class OnboardingSavePayload(BaseModel):
    """Batch zapis odpowiedzi onboardingowych. Klient wysyła po każdym
    przejściu pytania (lub całość na koniec)."""
    answers: list[OnboardingAnswer] = Field(..., max_length=len(ONBOARDING_PYTANIA))


@router.post("/onboarding/save")
async def onboarding_save(request: Request, payload: OnboardingSavePayload):
    """Persystuje odpowiedzi. RLS izoluje per tenant (migracja 0004).
    Bez `repo.upsert_onboarding_answer` → fallback JSONL żeby soft launch
    nie był blokowany niewdrożoną migracją."""
    sub = getattr(request.state, "architekt_subject", None) or "anonymous"
    ts = datetime.now(timezone.utc).isoformat()

    try:
        from db import repo
        from db.backend import acquire_http_db
        from db.connection import DB_PATH
    except ImportError:
        repo = None  # type: ignore[assignment]
        acquire_http_db = None  # type: ignore[assignment]
        DB_PATH = None  # type: ignore[assignment]

    persisted = False
    if (repo is not None and acquire_http_db is not None
            and hasattr(repo, "upsert_onboarding_answer")):
        try:
            async with acquire_http_db(DB_PATH) as db:
                for a in payload.answers:
                    await repo.upsert_onboarding_answer(
                        db,
                        user_subject=sub,
                        question_idx=a.question_idx,
                        answer=a.answer.strip(),
                        updated_at=ts,
                    )
                await db.commit()
            persisted = True
        except Exception:
            # Fallback poniżej.
            pass

    if not persisted:
        out_dir = Path(os.getenv("AW_FEEDBACK_DIR") or "data")
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "onboarding_answers.jsonl").open("a", encoding="utf-8") as f:
            for a in payload.answers:
                f.write(json.dumps({
                    "ts": ts, "user_subject": sub,
                    "question_idx": a.question_idx,
                    "answer": a.answer.strip(),
                }, ensure_ascii=False) + "\n")

    return {"status": "ok", "saved": len(payload.answers), "ts": ts}


@router.get("/ritual/daily")
def ritual_daily():
    return {"poranek": PYTANIA_PORANNE, "wieczor": PYTANIA_WIECZORNE}
