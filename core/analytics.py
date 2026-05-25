"""
Lekka analityka produktowa — zdarzenia dopisywane do data/events.jsonl.

Ten sam wzorzec co cost_log.jsonl: jeden JSON per linia, asyncio.to_thread,
zero zewnętrznych zależności. Daje mierzalne dane do iteracji produktowej:
- debate → commitment conversion rate
- commitment completion rate
- mode / category preference distribution
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from datetime import UTC  # Python ≥ 3.11
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


def events_log_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    default = root / "data" / "events.jsonl"
    return Path(os.getenv("EVENTS_LOG_PATH", str(default)))


def _append_line_sync(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


async def track(event: str, tenant_id: str, **props: Any) -> None:
    """Dopisuje jedno zdarzenie do events.jsonl bez blokowania event loop.

    Użycie:
        await track("debate_done", tenant_id, debate_id=42, mode="personal", agents=9)
        await track("commitment_created", tenant_id, debate_id=42, source="auto")
        await track("commitment_completed", tenant_id, commitment_id=7)
    """
    entry: dict[str, Any] = {
        "event": event,
        "tenant_id": tenant_id,
        "ts": datetime.now(UTC).isoformat(),
        **props,
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, _append_line_sync, events_log_path(), line)
    except Exception as e:
        logger.warning("analytics.track failed (%s): %s", event, e)


async def track_fire_and_forget(event: str, tenant_id: str, **props: Any) -> None:
    """Wersja bez await — tworzy Task i oddaje sterowanie natychmiast.
    Używaj w SSE handlerach gdzie nie chcesz opóźniać streamu.
    """
    task = asyncio.create_task(track(event, tenant_id, **props))
    # Przechowaj referencję żeby GC nie zebrał taska przed wykonaniem
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


_pending_tasks: set[asyncio.Task] = set()
