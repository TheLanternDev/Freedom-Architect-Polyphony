"""Async testy `apply_followup_nudges` i `sync_stale_projects` (AKSJOMAT 2).

Mockujemy `db` i `db.repo`. Repo woła się jako moduł, więc patchujemy
`api.services.completion_service.repo` w runtime.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services import completion_service as cs


# ── apply_followup_nudges ────────────────────────────────────────────────────


def _past_iso(hours_ago: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _future_iso(hours_ahead: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours_ahead)).isoformat()


def test_apply_followup_nudges_marks_overdue_commitments():
    repo = MagicMock()
    repo.list_open_commitments_with_followup = AsyncMock(return_value=[
        {"id": 1, "follow_up_at": _past_iso(2), "text": "zrób X", "needs_attention": 0},
        {"id": 2, "follow_up_at": _future_iso(2), "text": "zrób Y", "needs_attention": 0},
    ])
    repo.set_commitment_needs_attention = AsyncMock()
    db = MagicMock()
    with patch.object(cs, "repo", repo):
        n = asyncio.run(cs.apply_followup_nudges(db))
    assert n == 1
    # Tylko commit #1 (przeterminowany) został oznaczony.
    repo.set_commitment_needs_attention.assert_awaited_once()
    args = repo.set_commitment_needs_attention.await_args.args
    assert args[1] == 1
    assert "Przełamywanie Schematu" in args[2]
    assert "zrób X" in args[2]


def test_apply_followup_nudges_skips_already_flagged():
    repo = MagicMock()
    repo.list_open_commitments_with_followup = AsyncMock(return_value=[
        {"id": 9, "follow_up_at": _past_iso(5), "text": "zrób Z", "needs_attention": 1},
    ])
    repo.set_commitment_needs_attention = AsyncMock()
    with patch.object(cs, "repo", repo):
        n = asyncio.run(cs.apply_followup_nudges(MagicMock()))
    assert n == 0
    repo.set_commitment_needs_attention.assert_not_awaited()


def test_apply_followup_nudges_skips_missing_follow_up_at():
    repo = MagicMock()
    repo.list_open_commitments_with_followup = AsyncMock(return_value=[
        {"id": 1, "follow_up_at": None, "text": "x", "needs_attention": 0},
        {"id": 2, "follow_up_at": "", "text": "y", "needs_attention": 0},
        {"id": 3, "follow_up_at": "not-an-iso-date", "text": "z", "needs_attention": 0},
    ])
    repo.set_commitment_needs_attention = AsyncMock()
    with patch.object(cs, "repo", repo):
        n = asyncio.run(cs.apply_followup_nudges(MagicMock()))
    assert n == 0


def test_apply_followup_nudges_uses_en_prefix_when_text_starts_with_pattern_break():
    repo = MagicMock()
    repo.list_open_commitments_with_followup = AsyncMock(return_value=[
        {"id": 5, "follow_up_at": _past_iso(3),
         "text": "[Pattern Break] previous note", "needs_attention": 0},
    ])
    repo.set_commitment_needs_attention = AsyncMock()
    with patch.object(cs, "repo", repo):
        asyncio.run(cs.apply_followup_nudges(MagicMock()))
    new_text = repo.set_commitment_needs_attention.await_args.args[2]
    assert "Pattern Break" in new_text  # użyto EN prefix


def test_apply_followup_nudges_does_not_double_prefix():
    """Gdy `text` już zawiera prefix → nie dokleja drugi raz."""
    prefix = cs.shadow_followup_prefix("pl").strip()
    repo = MagicMock()
    repo.list_open_commitments_with_followup = AsyncMock(return_value=[
        {"id": 7, "follow_up_at": _past_iso(1),
         "text": prefix + " już z prefixem", "needs_attention": 0},
    ])
    repo.set_commitment_needs_attention = AsyncMock()
    with patch.object(cs, "repo", repo):
        asyncio.run(cs.apply_followup_nudges(MagicMock()))
    new_text = repo.set_commitment_needs_attention.await_args.args[2]
    # Prefix pojawia się tylko raz.
    assert new_text.count(prefix) == 1


# ── sync_stale_projects ──────────────────────────────────────────────────────


def test_sync_stale_returns_zeros_when_core_unavailable(monkeypatch):
    """Bez `core.completion_enforcer` → graceful zero."""
    monkeypatch.setattr(cs, "CORE_AVAILABLE", False)
    out = asyncio.run(cs.sync_stale_projects(MagicMock()))
    assert out == {"projects_updated": 0, "stale_commitments_created": 0}


def test_sync_stale_promotes_in_progress_to_at_risk():
    """Projekt z `last_progress_at` > 14 dni temu → AT_RISK + nudge."""
    from core.completion_enforcer import STALE_DAYS_AT_RISK
    long_ago = (datetime.now(timezone.utc)
                - timedelta(days=STALE_DAYS_AT_RISK + 1)).isoformat()

    repo = MagicMock()
    repo.list_active_projects = AsyncMock(return_value=[{"id": 42}])
    repo.get_project = AsyncMock(return_value={
        "id": 42, "dream_id": "d-1", "status": "in_progress",
        "started_at": long_ago, "last_progress_at": long_ago,
        "functionality": [{"description": "task to complete", "is_done": False}],
    })
    repo.update_project_status = AsyncMock()
    repo.has_open_stale_nudge = AsyncMock(return_value=False)
    repo.insert_commitment = AsyncMock()

    with patch.object(cs, "repo", repo):
        out = asyncio.run(cs.sync_stale_projects(MagicMock()))

    assert out["projects_updated"] == 1
    assert out["stale_commitments_created"] == 1
    repo.update_project_status.assert_awaited_once_with(repo.update_project_status.await_args.args[0], 42, "at_risk")


def test_sync_stale_does_not_double_create_nudge():
    """Gdy `has_open_stale_nudge` zwraca True → nudge NIE jest tworzony."""
    from core.completion_enforcer import STALE_DAYS_STUCK
    very_old = (datetime.now(timezone.utc)
                - timedelta(days=STALE_DAYS_STUCK + 5)).isoformat()

    repo = MagicMock()
    repo.list_active_projects = AsyncMock(return_value=[{"id": 99}])
    repo.get_project = AsyncMock(return_value={
        "id": 99, "dream_id": "d-x", "status": "in_progress",
        "started_at": very_old, "last_progress_at": very_old,
        "functionality": [{"description": "stale long task", "is_done": False}],
    })
    repo.update_project_status = AsyncMock()
    repo.has_open_stale_nudge = AsyncMock(return_value=True)  # już istnieje
    repo.insert_commitment = AsyncMock()

    with patch.object(cs, "repo", repo):
        out = asyncio.run(cs.sync_stale_projects(MagicMock()))

    assert out["projects_updated"] == 1
    assert out["stale_commitments_created"] == 0
    repo.insert_commitment.assert_not_awaited()


def test_sync_stale_skips_projects_already_in_recommended_status():
    """Projekt już w STUCK z bardzo starym last_progress → status NIE zmieniany."""
    from core.completion_enforcer import STALE_DAYS_STUCK
    very_old = (datetime.now(timezone.utc)
                - timedelta(days=STALE_DAYS_STUCK + 5)).isoformat()

    repo = MagicMock()
    repo.list_active_projects = AsyncMock(return_value=[{"id": 7}])
    repo.get_project = AsyncMock(return_value={
        "id": 7, "dream_id": "d", "status": "stuck",
        "started_at": very_old, "last_progress_at": very_old,
        "functionality": [{"description": "already stuck item", "is_done": False}],
    })
    repo.update_project_status = AsyncMock()
    repo.has_open_stale_nudge = AsyncMock(return_value=False)
    repo.insert_commitment = AsyncMock()

    with patch.object(cs, "repo", repo):
        out = asyncio.run(cs.sync_stale_projects(MagicMock()))

    assert out["projects_updated"] == 0
    repo.update_project_status.assert_not_awaited()


def test_sync_stale_skips_when_get_project_returns_none():
    repo = MagicMock()
    repo.list_active_projects = AsyncMock(return_value=[{"id": 1}])
    repo.get_project = AsyncMock(return_value=None)
    with patch.object(cs, "repo", repo):
        out = asyncio.run(cs.sync_stale_projects(MagicMock()))
    assert out == {"projects_updated": 0, "stale_commitments_created": 0}
