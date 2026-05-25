"""AKSJOMAT 2 — stale nudges, followupy, egzekucja limitu projektów."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

try:
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[assignment]

try:
    from core import (
        CompletionViolation,
        MAX_ACTIVE_PROJECTS,
        enforce_active_project_limit,
    )
    from core.completion_enforcer import (
        FunctionalityItem,
        Project,
        ProjectStatus,
        classify_stale_status,
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


# ── Tone: Szow / Deega — konfrontacja, nie „miłe przypomnienie" ──────────────

SHADOW_FOLLOWUP_PREFIX_PL = (
    "[Przełamywanie Schematu] Minęły 72 godziny. Co się stało z Twoim zobowiązaniem?\n\n"
)
SHADOW_FOLLOWUP_PREFIX_EN = (
    "[Pattern Break] 72 hours have passed. What happened to your commitment?\n\n"
)

DEEGA_STALE_AT_RISK_PL = (
    "[Przełamywanie Schematu — głos Deegi] Za długo nie było ruchu, który odhacza checklistę. "
    "Co konkretnie dziś — w jednym zdaniu — rusza pierwszą zaległą funkcjonalność?"
)
SZOW_STALE_STUCK_PL = (
    "[Przełamywanie Schematu \u2014 g\u0142os Szowa] To ju\u017c nie \u201ezaj\u0119ty jestem\u201d. To ucieczka przed domkni\u0119ciem. "
    "Nazwij jedn\u0105 rzecz, kt\u00f3r\u0105 udajesz, \u017ce nie widzisz \u2014 i zr\u00f3b z ni\u0105 co\u015b dzi\u015b."
)
DEEGA_STALE_AT_RISK_EN = (
    "[Pattern Break — Deega] Silence does not complete functionality. "
    "In one sentence: what moves the first unchecked item today?"
)
SZOW_STALE_STUCK_EN = (
    "[Pattern Break — Szow] This is no longer 'busy'. This is avoidance of finishing. "
    "Name one thing you pretend not to see — and act on it today."
)

AUTO_72H_SCHEMATY_BODY_PL = (
    "Tryb agresywny: masz 72 godziny, by pokazać ruch albo jawnie zmienić kurs. "
    "Zapisz dowód (nawet mały) albo nowe zobowiązanie — cisza = wzorzec."
)
AUTO_72H_SCHEMATY_BODY_EN = (
    "Aggressive mode: 72 hours to show motion or explicitly change course. "
    "Record proof (even tiny) or a new commitment — silence is the pattern."
)


def shadow_followup_prefix(language: str) -> str:
    return SHADOW_FOLLOWUP_PREFIX_EN if language == "en" else SHADOW_FOLLOWUP_PREFIX_PL


def auto_72h_schematy_body(language: str) -> str:
    return AUTO_72H_SCHEMATY_BODY_EN if language == "en" else AUTO_72H_SCHEMATY_BODY_PL


def stale_nudge_text(status: str, language: str) -> str:
    if language == "en":
        return DEEGA_STALE_AT_RISK_EN if status == "at_risk" else SZOW_STALE_STUCK_EN
    return DEEGA_STALE_AT_RISK_PL if status == "at_risk" else SZOW_STALE_STUCK_PL


def _stale_status_order(status: str) -> int:
    return {"dreaming": 0, "in_progress": 1, "at_risk": 2, "stuck": 3}.get(status, -1)


# ── Maintenance tasks ────────────────────────────────────────────────────────


async def apply_followup_nudges(db: Any) -> int:
    """Oznacza przeterminowane follow-upy jako needs_attention + dokleja prefix Szowa."""
    n = 0
    now = datetime.now(timezone.utc)
    for row in await repo.list_open_commitments_with_followup(db):
        if int(row.get("needs_attention") or 0) != 0:
            continue
        raw = row.get("follow_up_at")
        if not raw:
            continue
        try:
            fu = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if fu.tzinfo is None:
            fu = fu.replace(tzinfo=timezone.utc)
        if fu > now:
            continue
        cid = int(row["id"])
        lang = "en" if str(row.get("text", "")).startswith("[Pattern Break]") else "pl"
        prefix = shadow_followup_prefix(lang)
        old_text = str(row.get("text") or "")
        new_text = old_text if old_text.startswith(prefix.strip()) else prefix + old_text
        await repo.set_commitment_needs_attention(db, cid, new_text)
        n += 1
    return n


async def sync_stale_projects(db: Any) -> dict[str, int]:
    """Utrwala AT_RISK/STUCK i tworzy zobowiązania stale_project (Deega/Szow)."""
    if not CORE_AVAILABLE:
        return {"projects_updated": 0, "stale_commitments_created": 0}
    updates = 0
    created = 0
    rows = await repo.list_active_projects(db)
    for r in rows:
        pid = int(r["id"])
        full = await repo.get_project(db, pid)
        if not full:
            continue
        items = [FunctionalityItem(**f) for f in full["functionality"]]
        current = ProjectStatus(str(full["status"]))
        p = Project(
            id=pid,
            dream_id=str(full["dream_id"]),
            status=current,
            started_at=full.get("started_at"),
            last_progress_at=full.get("last_progress_at"),
            functionality=items,
        )
        rec = classify_stale_status(p, now=datetime.now(UTC))
        if rec in (ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED_CONSCIOUSLY):
            continue
        if rec == current:
            continue
        if _stale_status_order(rec.value) <= _stale_status_order(current.value):
            continue
        await repo.update_project_status(db, pid, rec.value)
        updates += 1
        if await repo.has_open_stale_nudge(db, pid):
            continue
        lang = "pl"
        txt = stale_nudge_text(rec.value, lang)
        fu = (datetime.now(UTC) + timedelta(hours=72)).isoformat()
        await repo.insert_commitment(
            db,
            text=txt,
            debate_id=None,
            project_id=pid,
            due_at=None,
            follow_up_at=fu,
            trigger_type="stale_project",
            needs_attention=0,
        )
        created += 1
    return {"projects_updated": updates, "stale_commitments_created": created}


async def run_phase2_maintenance() -> None:
    """Lifespan/admin: follow-upy + synchronizacja zastojów projektów."""
    if not DB_AVAILABLE:
        return
    try:
        from db.backend import acquire_http_db
        from db.connection import DB_PATH as _DB

        async with acquire_http_db(_DB) as db:
            nudged = await apply_followup_nudges(db)
            sync = await sync_stale_projects(db)
            await db.commit()
            logger.info(
                "Faza 2 maintenance: followup_nudges=%s stale_sync=%s", nudged, sync
            )
    except Exception as e:
        logger.warning("Faza 2 startup maintenance failed: %s", e)


