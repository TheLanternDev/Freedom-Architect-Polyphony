"""Limity i walidacja trybu demo interaktywnego (AW_DEMO_MODE)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from api.settings import (
    demo_allowed_categories,
    demo_allowed_modes,
    demo_max_brief_chars,
    demo_max_debates,
    demo_mode_enabled,
)


def is_demo_tenant(tenant_id: str | None) -> bool:
    tid = (tenant_id or "").strip()
    return tid.startswith("demo_")


async def count_tenant_debates(db: Any, tenant_id: str) -> int:
    from db import repo

    return await repo.count_debates_for_tenant(db, tenant_id)


async def demo_usage_for_tenant(db: Any, tenant_id: str) -> dict[str, int]:
    used = await count_tenant_debates(db, tenant_id)
    maximum = demo_max_debates()
    return {
        "debates_used": used,
        "debates_max": maximum,
        "debates_remaining": max(0, maximum - used),
    }


async def ensure_demo_can_start_debate(
    db: Any,
    tenant_id: str | None,
    brief: Any,
    *,
    is_continuation: bool = False,
) -> None:
    """Blokuje debatę demo poza dozwolonymi limitami (HTTP 403/422)."""
    if not demo_mode_enabled() or not is_demo_tenant(tenant_id):
        return

    tid = str(tenant_id)
    usage = await demo_usage_for_tenant(db, tid)
    if usage["debates_remaining"] <= 0:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "demo_limit_reached",
                "message_pl": (
                    f"Limit demo wyczerpany ({usage['debates_max']} debat na sesję). "
                    "Pełna wersja: founders / lokalna instalacja."
                ),
                **usage,
            },
        )

    allowed_modes = demo_allowed_modes()
    if brief.mode not in allowed_modes:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "demo_mode_restricted",
                "message_pl": f"W demo dozwolone tryby: {', '.join(sorted(allowed_modes))}.",
                "allowed_modes": sorted(allowed_modes),
            },
        )

    allowed_cats = demo_allowed_categories()
    if brief.category not in allowed_cats:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "demo_category_restricted",
                "message_pl": f"W demo dozwolone kategorie: {', '.join(sorted(allowed_cats))}.",
                "allowed_categories": sorted(allowed_cats),
            },
        )

    max_chars = demo_max_brief_chars()
    text = (brief.description or "").strip()
    if len(text) > max_chars:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "demo_brief_too_long",
                "message_pl": f"Brief w demo: max {max_chars} znaków.",
                "max_brief_chars": max_chars,
            },
        )

    if is_continuation:
        return

    # follow_up w kontynuacji ma osobny limit w DebateContinueRequest
    follow = (getattr(brief, "extra_context", None) or "").strip()
    if follow and len(follow) > max_chars:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "demo_context_too_long",
                "message_pl": f"Kontekst w demo: max {max_chars} znaków.",
                "max_brief_chars": max_chars,
            },
        )


def ensure_not_demo_blocked_route(tenant_id: str | None, feature: str) -> None:
    """Blokuje funkcje poza rdzeniem debaty (integracje, RODO, …)."""
    if demo_mode_enabled() and is_demo_tenant(tenant_id):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "demo_feature_disabled",
                "message_pl": f"Funkcja „{feature}” niedostępna w wersji demo.",
            },
        )
