"""FA2 settings — konfiguracja trybu biznesowego."""

from __future__ import annotations

import functools
import os


@functools.lru_cache(maxsize=1)
def get_fa2_settings() -> dict:
    return {
        "council_mode": "fa2",
        "database_path": os.getenv("FA2_DATABASE_PATH", "data/fa2.db"),
        "llm_concurrency": int(os.getenv("FA2_LLM_CONCURRENCY", "4")),
        "cache_ttl": int(os.getenv("AW_FA2_CACHE_TTL", "604800")),
        "rate_limit": os.getenv("AW_FA2_RATE", "30"),
    }
