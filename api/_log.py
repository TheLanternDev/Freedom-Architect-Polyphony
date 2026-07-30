"""Structured JSON logging helper.

Standardowy `logger.info("LLM [%s] %s ...", agent, model)` jest czytelny dla
człowieka, ale nieparsowany przez Loki/Cloud Logging/Datadog. `slog(...)`
emituje JSON-friendly logi przez `extra={}`, które kolektory mogą indeksować
po polach (`agent`, `model`, `tenant_id`, `latency_ms`, `cache_hit`).

Użycie:
    from api._log import slog
    slog("llm_call_completed", agent="Syez", model="claude-sonnet-5",
         input_tokens=420, output_tokens=1200, cost_usd=0.018, cache_hit=False)

W trybie dev/test (`LOG_FORMAT != "json"`) loguje czytelnie dla człowieka.
W prod (`LOG_FORMAT=json`) — jako JSON do stdout, gotowe pod kolektor.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

_logger = logging.getLogger("architekt")


def _json_enabled() -> bool:
    return (os.getenv("LOG_FORMAT") or "").lower() == "json"


def slog(event: str, **fields: Any) -> None:
    """Strukturalny log z polami `event` + dowolne `**fields`.

    `event` to nazwa zdarzenia (snake_case): np. `llm_call_completed`,
    `rls_guc_set`, `rate_limit_exceeded`, `completion_audit_violation`.

    Pola zarezerwowane: `ts`, `level`, `msg`. Nie nadpisuj ich.
    """
    payload: dict[str, Any] = {
        "ts": time.time(),
        "event": event,
    }
    payload.update(fields)
    if _json_enabled():
        # JSON do stdout — kolektor parsuje. `default=str` ratuje datetime/Decimal.
        sys.stdout.write(json.dumps(payload, default=str, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    else:
        # Human-readable: event=... k=v k=v
        kv = " ".join(f"{k}={v!r}" for k, v in fields.items())
        _logger.info("[%s] %s", event, kv)
