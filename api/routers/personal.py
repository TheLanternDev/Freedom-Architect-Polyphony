"""Endpointy „personal mode": onboarding (20 pytań), codzienny rytuał."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.settings import is_production
from db.tenant import current_tenant_id

from personal_v1.rituals.onboarding import (
    PYTANIA as ONBOARDING_PYTANIA,
    SEKCJE as ONBOARDING_SEKCJE,
)
from personal_v1.rituals.daily import PYTANIA_PORANNE, PYTANIA_WIECZORNE

router = APIRouter(prefix="/personal", tags=["personal"])

@router.get("/onboarding/questions")
def onboarding_questions():
    return {
        "items": ONBOARDING_PYTANIA,
        "sekcje": ONBOARDING_SEKCJE,
        "ton": "lagodny",
        "tempo": "ile_chcesz",
    }


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
    persist_error: str | None = None
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
        except Exception as e:
            persist_error = str(e)

    if not persisted:
        if is_production():
            raise HTTPException(
                503,
                detail=(
                    "Nie udało się zapisać odpowiedzi onboardingowych w bazie — "
                    f"{'błąd: ' + persist_error if persist_error else 'sprawdź migrację onboarding_answers.'}"
                ),
            )
        # Dev-only fallback JSONL.
        out_dir = Path(os.getenv("AW_FEEDBACK_DIR") or "data")
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "onboarding_answers.jsonl").open("a", encoding="utf-8") as f:
            for a in payload.answers:
                f.write(json.dumps({
                    "ts": ts,
                    "tenant_id": current_tenant_id(),
                    "user_subject": sub,
                    "question_idx": a.question_idx,
                    "answer": a.answer.strip(),
                }, ensure_ascii=False) + "\n")

    return {"status": "ok", "saved": len(payload.answers), "ts": ts}


@router.get("/onboarding/answers")
async def onboarding_answers(request: Request):
    """Zapisane odpowiedzi onboardingowe bieżącego użytkownika („Mój obraz").
    DB-first; dev fallback z JSONL. Izolacja: filtr po user_subject (+ tenant)."""
    sub = getattr(request.state, "architekt_subject", None) or "anonymous"

    try:
        from db import repo
        from db.backend import acquire_http_db
        from db.connection import DB_PATH
    except ImportError:
        repo = None  # type: ignore[assignment]
        acquire_http_db = None  # type: ignore[assignment]
        DB_PATH = None  # type: ignore[assignment]

    base = {"sekcje": ONBOARDING_SEKCJE, "items": ONBOARDING_PYTANIA}

    if (repo is not None and acquire_http_db is not None
            and hasattr(repo, "list_onboarding_answers")):
        try:
            async with acquire_http_db(DB_PATH) as db:
                rows = await repo.list_onboarding_answers(db, user_subject=sub)
            return {
                **base,
                "answers": [
                    {
                        "question_idx": int(r["question_idx"]),
                        "answer": r["answer"],
                        "updated_at": r.get("updated_at"),
                    }
                    for r in rows
                ],
            }
        except Exception:
            pass  # fallback poniżej

    # Dev-only fallback JSONL — ostatni wpis per question_idx.
    out_dir = Path(os.getenv("AW_FEEDBACK_DIR") or "data")
    path = out_dir / "onboarding_answers.jsonl"
    latest: dict[int, dict] = {}
    if path.exists():
        tid = current_tenant_id()
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("user_subject") != sub:
                    continue
                if tid and rec.get("tenant_id") not in (None, tid):
                    continue
                qi = int(rec.get("question_idx", -1))
                if qi >= 0:
                    latest[qi] = {
                        "question_idx": qi,
                        "answer": rec.get("answer", ""),
                        "updated_at": rec.get("ts"),
                    }
    return {**base, "answers": [latest[k] for k in sorted(latest)]}


async def _acquire_repo_db():
    """(repo, acquire_http_db, DB_PATH) lub (None, None, None) gdy warstwa DB
    niedostępna. Wspólne dla syntezy i odczytu Obrazu."""
    try:
        from db import repo
        from db.backend import acquire_http_db
        from db.connection import DB_PATH
        return repo, acquire_http_db, DB_PATH
    except ImportError:
        return None, None, None


@router.post("/onboarding/synthesize")
async def onboarding_synthesize(request: Request):
    """Destyluje zapisane odpowiedzi onboardingowe w trwały `ObrazUzytkownika`
    (AKSJOMAT 1). DB-required: Obraz musi trafić do bazy, żeby Rada go widziała.
    Izolacja: odpowiedzi i Obraz filtrowane po tenant_id (RLS) ORAZ user_subject."""
    sub = getattr(request.state, "architekt_subject", None) or "anonymous"
    ts = datetime.now(timezone.utc).isoformat()

    repo, acquire_http_db, DB_PATH = await _acquire_repo_db()
    if not (repo is not None and acquire_http_db is not None
            and hasattr(repo, "upsert_user_obraz")
            and hasattr(repo, "list_onboarding_answers")):
        raise HTTPException(
            503,
            detail="Synteza Obrazu wymaga bazy — sprawdź migrację user_obraz (0007).",
        )

    from core.obraz_uzytkownika import adistill_obraz

    async with acquire_http_db(DB_PATH) as db:
        rows = await repo.list_onboarding_answers(db, user_subject=sub)
        answers = [
            {"question_idx": int(r["question_idx"]), "answer": r["answer"]} for r in rows
        ]
        prev = await repo.get_user_obraz(db, user_subject=sub)
        wersja = int(prev["wersja"]) + 1 if prev else 1
        obraz = await adistill_obraz(answers, wersja=wersja)
        await repo.upsert_user_obraz(
            db,
            user_subject=sub,
            obraz_json=obraz.model_dump_json(),
            wersja=wersja,
            updated_at=ts,
        )
        await db.commit()

    return {"status": "ok", "wersja": wersja, "obraz": obraz.model_dump(), "ts": ts}


@router.get("/onboarding/obraz")
async def onboarding_obraz(request: Request):
    """Bieżący Obraz użytkownika („Mój obraz" — wersja zdestylowana).
    Izolacja: tenant_id (RLS) ORAZ user_subject."""
    sub = getattr(request.state, "architekt_subject", None) or "anonymous"

    repo, acquire_http_db, DB_PATH = await _acquire_repo_db()
    if not (repo is not None and acquire_http_db is not None
            and hasattr(repo, "get_user_obraz")):
        return {"obraz": None, "wersja": None, "updated_at": None}

    async with acquire_http_db(DB_PATH) as db:
        row = await repo.get_user_obraz(db, user_subject=sub)
    if not row:
        return {"obraz": None, "wersja": None, "updated_at": None}
    try:
        obraz = json.loads(row["obraz_json"])
    except Exception:
        obraz = None
    return {"obraz": obraz, "wersja": row.get("wersja"), "updated_at": row.get("updated_at")}


@router.get("/ritual/daily")
def ritual_daily():
    return {"poranek": PYTANIA_PORANNE, "wieczor": PYTANIA_WIECZORNE}
