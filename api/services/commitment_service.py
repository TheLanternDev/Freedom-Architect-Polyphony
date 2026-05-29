"""Logika zobowiązań: create, release, complete, delete-forbidden (AKSJOMAT 2)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException

try:
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[assignment]

try:
    from db import repo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    repo = None  # type: ignore[assignment]

try:
    from core.analytics import track_fire_and_forget as _track
except ImportError:  # pragma: no cover
    async def _track(event: str, tenant_id: str, **props: Any) -> None:  # type: ignore[misc]
        pass


# ── Stałe ─────────────────────────────────────────────────────────────────────

SHADOW_NO_SILENT_RELEASE_PL = (
    "Nie możesz po cichu zniknąć ze swojego własnego zobowiązania."
)
SHADOW_NO_SILENT_RELEASE_EN = (
    "You cannot quietly vanish from a commitment you made to yourself."
)

MIN_COMMITMENT_RELEASE_REASON_LEN = 30

_background_tasks: set[asyncio.Task] = set()


# ── Service functions ─────────────────────────────────────────────────────────


def _require_db() -> None:
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")


async def create_commitment(
    *,
    text: str,
    debate_id: Optional[int],
    project_id: Optional[int],
    due_at: Optional[str],
    follow_up_at: Optional[str],
    db: Any,
) -> dict[str, Any]:
    """Tworzy zobowiązanie i zwraca payload odpowiedzi."""
    _require_db()
    debate_row: Optional[dict[str, Any]] = None
    if debate_id is not None:
        debate_row = await repo.get_debate_row_minimal(db, int(debate_id))
        if debate_row is None:
            raise HTTPException(status_code=404, detail="debata nie istnieje")

    resolved_project = project_id
    dream_id = (debate_row or {}).get("dream_id")
    if resolved_project is None and dream_id:
        resolved_project = await repo.project_id_for_dream(db, str(dream_id))

    mode = str((debate_row or {}).get("mode") or "pelna")
    follow_up = follow_up_at
    if mode == "schematy" and not follow_up:
        follow_up = (datetime.now(UTC) + timedelta(hours=72)).isoformat()

    new_id = await repo.insert_commitment(
        db,
        text=text.strip(),
        debate_id=debate_id,
        project_id=resolved_project,
        due_at=due_at,
        follow_up_at=follow_up,
        trigger_type="manual",
    )
    if resolved_project is not None:
        await repo.touch_project_last_progress(db, int(resolved_project))
    await db.commit()
    from db.tenant import current_tenant_id as _tid_now
    _t = asyncio.create_task(
        _track(
            "commitment_created", _tid_now(),
            commitment_id=new_id, debate_id=debate_id,
            project_id=resolved_project, trigger_type="manual",
        )
    )
    _background_tasks.add(_t)
    _t.add_done_callback(_background_tasks.discard)
    return {
        "id": new_id,
        "status": "open",
        "follow_up_at": follow_up,
        "trigger_type": "manual",
        "project_id": resolved_project,
    }


async def release_commitment(db: Any, commitment_id: int, reason: str) -> dict[str, Any]:
    """Zwalnia zobowiązanie z wymaganym uzasadnieniem (AKSJOMAT 2)."""
    _require_db()
    row = await repo.get_commitment(db, commitment_id)
    if not row:
        raise HTTPException(status_code=404, detail="nie znaleziono")
    if str(row.get("status")) != "open":
        raise HTTPException(status_code=409, detail="zobowiązanie nie jest otwarte")
    ok = await repo.release_commitment(db, commitment_id, reason=reason.strip())
    if not ok:
        raise HTTPException(status_code=409, detail="nie udało się zwolnić")
    await db.commit()
    return {"ok": True, "id": commitment_id, "status": "released"}


async def complete_commitment(
    db: Any,
    commitment_id: int,
    evidence_note: Optional[str] = None,
    evidence_url: Optional[str] = None,
) -> dict[str, Any]:
    """Odhacza zobowiązanie + aktualizuje postęp projektu (AKSJOMAT 2)."""
    _require_db()
    row = await repo.get_commitment(db, commitment_id)
    if not row:
        raise HTTPException(status_code=404, detail="nie znaleziono")
    pid = row.get("project_id")
    ok = await repo.complete_commitment(
        db,
        commitment_id,
        evidence_note=evidence_note,
        evidence_url=evidence_url,
    )
    if not ok:
        raise HTTPException(status_code=409, detail="nie udało się odhaczyć")
    if pid is not None:
        await repo.touch_project_last_progress(db, int(pid))
    await db.commit()
    from db.tenant import current_tenant_id as _tid_now
    _t = asyncio.create_task(
        _track("commitment_completed", _tid_now(), commitment_id=commitment_id, project_id=pid)
    )
    _background_tasks.add(_t)
    _t.add_done_callback(_background_tasks.discard)
    return {"ok": True, "id": commitment_id, "status": "completed"}


def delete_forbidden_payload(commitment_id: int) -> dict[str, Any]:
    """Payload dla HTTP 422 — DELETE jest celowo zablokowany (AKSJOMAT 2)."""
    return {
        "kind": "shadow_no_silent_release",
        "message_pl": SHADOW_NO_SILENT_RELEASE_PL,
        "message_en": SHADOW_NO_SILENT_RELEASE_EN,
        "use_endpoint": f"POST /commitment/{commitment_id}/release",
        "min_reason_chars": MIN_COMMITMENT_RELEASE_REASON_LEN,
    }
