"""
Smoke test izolacji cache LLM v8 (multi-tenancy hard isolation).

Uruchom z roota repo:  python scripts/verify_cache_isolation.py

Co robi:
  1. Symuluje dwóch userów (`user-A`, `user-B`) w tym samym tenancie.
  2. Wylicza klucz cache dla identycznego briefu — KAŻDY musi być inny.
  3. Zapisuje SETEX → GET → DEL na lokalnym Redisie (`REDIS_URL` lub localhost).
  4. Drukuje wynik. Exit code 0 = izolacja OK, 1 = naruszenie.

Skrypt nie woła LLM — sprawdza wyłącznie warstwę klucza + transport Redis.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Skrypt wołany jako `python scripts/...` — root repo nie jest w sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base_agent import BaseAgent
from db.tenant import (
    reset_current_tenant_id,
    reset_current_user_id,
    set_current_tenant_id,
    set_current_user_id,
)


def _key_for(user_id: str, tenant_id: str = "smoke-tenant") -> str:
    tok_t = set_current_tenant_id(tenant_id)
    tok_u = set_current_user_id(user_id)
    try:
        # Replikujemy logikę _call_llm: gdy caller nie poda ID, czyta ContextVar.
        from db.tenant import current_tenant_id, current_user_id
        return BaseAgent._cache_key(
            "Kogit", "identyczny brief", "claude-sonnet-4-6", 0.5,
            tenant_id=current_tenant_id(), user_id=current_user_id(),
        )
    finally:
        reset_current_user_id(tok_u)
        reset_current_tenant_id(tok_t)


async def _roundtrip(redis, key: str, value: str) -> str | None:
    await redis.setex(key, 30, value)
    got = await redis.get(key)
    await redis.delete(key)
    return got


async def main() -> int:
    key_a = _key_for("user-A")
    key_b = _key_for("user-B")
    print(f"key(user-A) = {key_a}")
    print(f"key(user-B) = {key_b}")

    if key_a == key_b:
        print("FAIL: identyczne klucze dla różnych userów — izolacja złamana.")
        return 1
    if not (key_a.startswith("llm:v8:") and key_b.startswith("llm:v8:")):
        print("FAIL: klucz nie ma prefiksu llm:v8 — bump cache_key nie zadziałał.")
        return 1
    print("OK: klucze rozdzielne, prefix v8.")

    try:
        import redis.asyncio as aioredis
    except ImportError:
        print("SKIP: brak biblioteki redis — sam klucz OK, transport niesprawdzony.")
        return 0

    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    r = aioredis.from_url(url, decode_responses=True,
                          socket_connect_timeout=2, socket_timeout=2)
    try:
        got_a = await _roundtrip(r, key_a, "resp-A")
        got_b = await _roundtrip(r, key_b, "resp-B")
    except Exception as e:
        print(f"SKIP: Redis ({url}) niedostępny — {type(e).__name__}: {e}. "
              "Sam klucz OK, transport niesprawdzony.")
        return 0

    if got_a != "resp-A" or got_b != "resp-B":
        print(f"FAIL: roundtrip Redis: got_a={got_a!r}, got_b={got_b!r}.")
        return 1
    print(f"OK: SETEX/GET/DEL roundtrip na {url} działa pod kluczami v8.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
