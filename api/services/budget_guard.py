"""Twardy budżet LLM + warningi SSE."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

from fastapi import HTTPException


from api.services._sse import sse as _sse


try:
    from core.cost_tracking import (
        evaluate_hard_budget,
        load_budget_snapshot,
        maybe_fire_cost_webhook,
    )
except ImportError:
    evaluate_hard_budget = None  # type: ignore[misc,assignment]
    load_budget_snapshot = None  # type: ignore[misc,assignment]
    maybe_fire_cost_webhook = None  # type: ignore[misc,assignment]


def spent_today_usd() -> float:
    """Koszt dzienny UTC z cost_log.jsonl."""
    if load_budget_snapshot is None:
        return 0.0
    return float(load_budget_snapshot().spent_today_usd)


async def ensure_hard_budget_or_raise() -> None:
    """Twarde limity env — blokuje start debaty (HTTP 402)."""
    if evaluate_hard_budget is None or load_budget_snapshot is None:
        return
    block = evaluate_hard_budget(load_budget_snapshot())
    if block is None:
        return
    if maybe_fire_cost_webhook is not None:
        asyncio.create_task(
            maybe_fire_cost_webhook(
                {
                    "event": "budget_hard_block",
                    "kind": block.kind,
                    "spent_usd": block.spent_usd,
                    "ceiling_usd": block.ceiling_usd,
                }
            )
        )
    raise HTTPException(
        status_code=402,
        detail={
            "error": "budget_exceeded",
            "kind": block.kind,
            "spent_usd": block.spent_usd,
            "ceiling_usd": block.ceiling_usd,
            "message_pl": block.message_pl,
        },
    )


def maybe_budget_warning_sse() -> Optional[str]:
    """Zwraca SSE event jeśli próg DAILY_BUDGET_USD osiągnięty, inaczej None."""
    raw = os.getenv("DAILY_BUDGET_USD")
    if not raw:
        return None
    try:
        ceiling = float(raw)
    except ValueError:
        return None
    spent = spent_today_usd()
    if spent >= ceiling:
        return _sse(
            "budget_warning",
            {
                "spent_usd": spent,
                "ceiling_usd": ceiling,
                "message": (
                    "Dzienny próg kosztów LLM został osiągnięty lub przekroczony "
                    "(zmienna DAILY_BUDGET_USD). Rada nadal działa — świadomy wybór."
                ),
            },
        )
    return None
