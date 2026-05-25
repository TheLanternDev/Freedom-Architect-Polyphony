"""Faza A0 — destylacja marzenia + zapis do DB."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)

try:
    from core import DreamArchitecture, adistill_dream
    from core.dream_architect import _fallback_dream
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False

try:
    from db import repo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    repo = None  # type: ignore[assignment]


from api.services.mode_helpers import daily_checkin_question, mode_decorator_for_dream  # noqa: E402, F401


from api.services._sse import sse as _sse


async def distill_dream(
    raw_brief: str,
    mode: str,
    language: str,
) -> Optional[DreamArchitecture]:
    """Destyluje marzenie (LLM lub fallback). Zwraca None gdy core niedostępne."""
    if not CORE_AVAILABLE:
        return None
    if mode == "codzienny":
        return _fallback_dream(raw_brief, language=language)
    return await adistill_dream(raw_brief, language=language)


def dream_architecture_sse(dream: DreamArchitecture) -> str:
    """Formatuje DreamArchitecture jako SSE event."""
    return _sse(
        "dream_architecture",
        {
            "dream_id": dream.dream_id,
            "core_dream": dream.core_dream,
            "value_anchor": dream.value_anchor,
            "pillars": dream.pillars,
            "milestones": [m.model_dump() for m in dream.milestones],
            "next_move": dream.next_move.model_dump(),
            "completion_criteria": dream.completion_criteria,
            "functionality_checklist": dream.functionality_checklist,
        },
    )


async def persist_dream_and_project(
    db: Any,
    dream: DreamArchitecture,
    brief: Any,
    *,
    continuation_parent_id: Optional[int] = None,
) -> tuple[Optional[int], Optional[int]]:
    """Zapisuje marzenie + projekt + debatę. Zwraca (debate_id, project_id)."""
    if db is None or not DB_AVAILABLE:
        return None, None
    await repo.insert_dream(db, dream)
    project_id = await repo.ensure_project_for_dream(
        db, dream.dream_id, dream.functionality_checklist
    )
    debate_id = await repo.insert_debate(
        db,
        category=brief.category,
        mode=brief.mode,
        brief_description=brief.description,
        intention=brief.intention,
        extra_context=brief.extra_context,
        dream_id=dream.dream_id,
        parent_debate_id=continuation_parent_id,
    )
    await repo.link_dream_debate(db, dream.dream_id, debate_id)
    await db.commit()
    return debate_id, project_id
