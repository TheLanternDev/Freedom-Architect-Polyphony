"""
Agregacja kosztów LLM (cost_log.jsonl), async append oraz twarde limity budżetu.

Blokuje pętlę zdarzeń: zapis przez asyncio.to_thread zamiast sync open().
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

try:
    from datetime import UTC  # Python ≥ 3.11
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[misc,assignment]
from pathlib import Path
from typing import Any, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover — Windows
    fcntl = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


def cost_log_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    default = root / "data" / "cost_log.jsonl"
    return Path(os.getenv("COST_LOG_PATH", str(default)))


def _append_cost_line_sync(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        if fcntl is not None:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
        finally:
            if fcntl is not None:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


async def append_cost_log_async(entry: dict[str, Any]) -> None:
    """Append jednej linii JSON do cost_log.jsonl bez blokowania event loop."""
    path = cost_log_path()
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _append_cost_line_sync, path, line)


def sum_cost_for_day_utc(path: Path, day_iso: str) -> float:
    """day_iso = YYYY-MM-DD (UTC)."""
    if not path.is_file():
        return 0.0
    total = 0.0
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                ts = str(entry.get("timestamp", ""))
                if len(ts) >= 10 and ts[:10] == day_iso:
                    total += float(entry.get("cost_usd", 0) or 0)
    except OSError as e:
        logger.warning("cost log read failed: %s", e)
    return round(total, 6)


def sum_cost_for_month_utc(path: Path, year: int, month: int) -> float:
    prefix = f"{year:04d}-{month:02d}-"
    if not path.is_file():
        return 0.0
    total = 0.0
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                ts = str(entry.get("timestamp", ""))
                if len(ts) >= 10 and ts.startswith(prefix[:7]):  # YYYY-MM
                    total += float(entry.get("cost_usd", 0) or 0)
    except OSError as e:
        logger.warning("cost log month read failed: %s", e)
    return round(total, 6)


def tail_cost_entries(path: Path, limit: int = 80) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for raw in lines[-limit:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


@dataclass
class BudgetSnapshot:
    spent_today_usd: float
    spent_month_usd: float
    day_iso: str
    year: int
    month: int


def load_budget_snapshot(path: Optional[Path] = None) -> BudgetSnapshot:
    p = path or cost_log_path()
    now = datetime.now(UTC)
    day = now.strftime("%Y-%m-%d")
    return BudgetSnapshot(
        spent_today_usd=sum_cost_for_day_utc(p, day),
        spent_month_usd=sum_cost_for_month_utc(p, now.year, now.month),
        day_iso=day,
        year=now.year,
        month=now.month,
    )


def _parse_positive_float(raw: Optional[str]) -> Optional[float]:
    if raw is None or not str(raw).strip():
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    if v <= 0:
        return None
    return v


@dataclass
class BudgetBlock:
    kind: str  # daily_hard | monthly_hard
    spent_usd: float
    ceiling_usd: float
    message_pl: str


def evaluate_hard_budget(snapshot: BudgetSnapshot) -> Optional[BudgetBlock]:
    """
    Twarde limity — jeśli przekroczone, debata nie powinna wystartować.

    Env:
      DAILY_BUDGET_HARD_USD — obrót dzienny UTC ≥ wartość → blokada
      MONTHLY_BUDGET_HARD_USD — obrót miesiąca kalendarzowego UTC ≥ wartość → blokada
    """
    monthly = _parse_positive_float(os.getenv("MONTHLY_BUDGET_HARD_USD"))
    daily = _parse_positive_float(os.getenv("DAILY_BUDGET_HARD_USD"))

    if monthly is not None and snapshot.spent_month_usd >= monthly:
        return BudgetBlock(
            kind="monthly_hard",
            spent_usd=snapshot.spent_month_usd,
            ceiling_usd=monthly,
            message_pl=(
                f"Przekroczono miesięczny budżet twardy ({monthly:.4f} USD). "
                "Zwiększ MONTHLY_BUDGET_HARD_USD lub poczekaj na nowy miesiąc."
            ),
        )
    if daily is not None and snapshot.spent_today_usd >= daily:
        return BudgetBlock(
            kind="daily_hard",
            spent_usd=snapshot.spent_today_usd,
            ceiling_usd=daily,
            message_pl=(
                f"Przekroczono dzienny budżet twardy ({daily:.4f} USD). "
                "Zwiększ DAILY_BUDGET_HARD_USD lub poczekaj na reset UTC."
            ),
        )
    return None


async def maybe_fire_cost_webhook(payload: dict[str, Any]) -> None:
    url = (os.getenv("COST_ALERT_WEBHOOK_URL") or "").strip()
    if not url:
        return
    try:
        import httpx

        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        logger.warning("cost webhook post failed: %s", e)


def build_cost_entry(
    *,
    agent: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    context: str,
) -> dict[str, Any]:
    brief_hash = hashlib.sha256(context.encode("utf-8")).hexdigest()[:16]
    # P1-E1: per-tenant metering — bez tenant_id w logu nie da się rozliczyć
    # kosztów per klient (SaaS) ani audytować, czyj brief spalił budżet.
    # ContextVar ustawiany przez http_guard; poza requestem (CLI/testy) — "".
    # Lazy import + defensywnie: log kosztów nie może wywrócić ścieżki LLM.
    try:
        from db.tenant import current_tenant_id

        tenant_id = current_tenant_id() or ""
    except Exception:
        tenant_id = ""
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": agent,
        "model": model,
        "in_tokens": input_tokens,
        "out_tokens": output_tokens,
        "cost_usd": round(cost_usd, 6),
        "brief_hash": brief_hash,
        "tenant_id": tenant_id,
    }


def cost_status_payload(*, recent_limit: int = 80) -> dict[str, Any]:
    snap = load_budget_snapshot()
    block = evaluate_hard_budget(snap)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "log_path": str(cost_log_path()),
        "spent_today_usd": snap.spent_today_usd,
        "spent_month_usd": snap.spent_month_usd,
        "day_utc": snap.day_iso,
        "budget_blocked": block is not None,
        "budget_block": (
            {"kind": block.kind, "spent_usd": block.spent_usd, "ceiling_usd": block.ceiling_usd}
            if block
            else None
        ),
        "limits": {
            "daily_hard_usd": os.getenv("DAILY_BUDGET_HARD_USD"),
            "monthly_hard_usd": os.getenv("MONTHLY_BUDGET_HARD_USD"),
            "daily_soft_warning_usd": os.getenv("DAILY_BUDGET_USD"),
        },
        "recent": tail_cost_entries(cost_log_path(), limit=recent_limit),
    }
