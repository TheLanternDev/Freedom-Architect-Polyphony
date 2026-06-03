"""Logika fail-fast startup (prod vs dev) — testowalna bez importu main.py."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("ArchitektWolnosci")


def redis_required_in_prod() -> bool:
    """Prod (poza demo) wymaga działającego Redis — zgodnie z production_preflight_errors."""
    from api.settings import demo_mode_enabled, is_production

    return (
        is_production()
        and not demo_mode_enabled()
        and bool((os.getenv("REDIS_URL") or "").strip())
    )


def handle_init_db_failure(exc: Exception) -> None:
    """init_db w prod → SystemExit; dev → log i kontynuacja."""
    from api.settings import is_production

    if is_production():
        logger.critical("🛑 init_db failed w produkcji: %s", exc)
        raise SystemExit(
            f"Startup zablokowany — inicjalizacja bazy nieudana ({exc})."
        ) from exc
    logger.error("⚠️ init_db failed: %s", exc)
