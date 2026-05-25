"""Operacje na projektach: list, detail, complete, archive, check functionality."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException

try:
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[assignment]

try:
    from core import (
        CompletionViolation,
        MAX_ACTIVE_PROJECTS,
        assert_full_functionality,
        enforce_active_project_limit,
    )
    from core.completion_enforcer import (
        FunctionalityItem,
        Project,
        ProjectStatus,
        validate_archive_reason,
    )
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False

try:
    from db import repo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    repo = None  # type: ignore[assignment]


def _require_core_and_db() -> None:
    if not (CORE_AVAILABLE and DB_AVAILABLE):
        raise HTTPException(status_code=503, detail="core lub db niedostępne")


def _require_db() -> None:
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")


def _build_project_domain(raw: dict[str, Any]) -> Project:
    """Buduje obiekt domenowy Project z wiersza DB."""
    items = [FunctionalityItem(**f) for f in raw["functionality"]]
    return Project(
        id=int(raw["id"]),
        dream_id=str(raw["dream_id"]),
        status=ProjectStatus(raw["status"]),
        started_at=raw.get("started_at"),
        last_progress_at=raw.get("last_progress_at"),
        functionality=items,
    )


# ── List projects ────────────────────────────────────────────────────────────


async def list_projects_with_stats(db: Any) -> dict[str, Any]:
    """Lista aktywnych projektów + completion_ratio + dni bez postępu."""
    _require_core_and_db()
    rows = await repo.list_active_projects(db)
    out: list[dict[str, Any]] = []
    for r in rows:
        full = await repo.get_project(db, int(r["id"]))
        if not full:
            continue
        proj = _build_project_domain(full)
        out.append(
            {
                "id": proj.id,
                "dream_id": proj.dream_id,
                "core_dream": r.get("core_dream"),
                "status": proj.status.value,
                "completion_ratio": round(proj.completion_ratio(), 3),
                "days_since_progress": proj.days_since_progress(),
                "remaining": [f.description for f in proj.remaining_items()],
                "total_items": len(proj.functionality),
            }
        )
    return {"projects": out, "limit": MAX_ACTIVE_PROJECTS}


# ── Detail ───────────────────────────────────────────────────────────────────


async def get_project(db: Any, project_id: int) -> dict[str, Any]:
    _require_core_and_db()
    proj = await repo.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Projekt nie znaleziony")
    return proj


# ── Project commitments ──────────────────────────────────────────────────────


async def get_project_commitments(db: Any, project_id: int, limit: int = 80) -> dict[str, Any]:
    _require_db()
    row = await repo.get_project(db, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Projekt nie znaleziony")
    rows = await repo.list_commitments_for_project(db, project_id, limit=limit)
    return {"commitments": rows}


# ── Check functionality item ─────────────────────────────────────────────────


async def check_functionality_item(
    db: Any,
    project_id: int,
    item_id: int,
    evidence_url: Optional[str] = None,
) -> dict[str, Any]:
    _require_db()
    affected_project = await repo.mark_functionality_done(
        db, item_id, evidence_url=evidence_url
    )
    if affected_project is None:
        raise HTTPException(status_code=404, detail="Pozycja nie znaleziona")
    if affected_project != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Pozycja {item_id} nie należy do projektu {project_id}",
        )
    await db.commit()
    proj = await repo.get_project(db, project_id)
    return {"ok": True, "project": proj}


# ── Complete project ─────────────────────────────────────────────────────────


async def complete_project(db: Any, project_id: int) -> dict[str, Any]:
    """Oznacza projekt jako COMPLETED — wymaga 100% checklisty."""
    _require_core_and_db()
    raw = await repo.get_project(db, project_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Projekt nie znaleziony")
    project = _build_project_domain(raw)
    try:
        assert_full_functionality(project)
    except CompletionViolation as cv:
        raise HTTPException(status_code=422, detail=cv.to_payload()) from cv
    await repo.update_project_status(
        db,
        project_id,
        ProjectStatus.COMPLETED.value,
        completed_at=datetime.now(UTC).isoformat(),
    )
    await db.commit()
    return {"ok": True, "status": ProjectStatus.COMPLETED.value}


# ── Archive project ──────────────────────────────────────────────────────────


async def archive_project(db: Any, project_id: int, reason: str) -> dict[str, Any]:
    """Archiwizuje projekt z wymaganym uzasadnieniem (AKSJOMAT 2)."""
    _require_core_and_db()
    try:
        clean_reason = validate_archive_reason(reason)
    except CompletionViolation as cv:
        raise HTTPException(status_code=422, detail=cv.to_payload()) from cv
    proj = await repo.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Projekt nie znaleziony")
    await repo.update_project_status(
        db,
        project_id,
        ProjectStatus.ARCHIVED_CONSCIOUSLY.value,
        archived_reason=clean_reason,
        archived_at=datetime.now(UTC).isoformat(),
    )
    await db.commit()
    return {"ok": True, "status": ProjectStatus.ARCHIVED_CONSCIOUSLY.value}


# ── Dream enrichment helpers (used by dreams list endpoint) ──────────────────


def enrich_dream_with_project(dream_row: dict[str, Any], full_project: dict[str, Any]) -> None:
    """Dodaje project data + days_since_progress do wiersza marzenia."""
    dream_row["project"] = full_project
    if CORE_AVAILABLE:
        proj = _build_project_domain(full_project)
        dream_row["days_since_progress"] = proj.days_since_progress()


# ── Enforcement (AKSJOMAT 2) ─────────────────────────────────────────────────


async def enforce_active_project_limit_for_brief(brief: "Any", db: Any) -> None:
    """AKSJOMAT 2: Reguła 'Najpierw kończ' — tylko przy category=projekt."""
    if not (CORE_AVAILABLE and DB_AVAILABLE):
        return
    rows = await repo.list_active_projects(db)
    projects = [
        Project(
            id=int(r["id"]),
            dream_id=str(r["dream_id"]),
            status=ProjectStatus(r["status"]),
            started_at=r.get("started_at"),
            last_progress_at=r.get("last_progress_at"),
        )
        for r in rows
    ]
    try:
        enforce_active_project_limit(projects, attempting_new_project=True)
    except CompletionViolation as cv:
        raise HTTPException(status_code=409, detail=cv.to_payload()) from cv
