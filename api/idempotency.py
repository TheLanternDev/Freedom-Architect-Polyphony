"""P1-B1: Idempotency-Key dla POST /debate/stream i /debate/continue/stream.

Retry SSE w `useDebate` (przed pierwszym eventem) mógł utworzyć DRUGĄ debatę,
gdy pierwsze żądanie żyło po stronie serwera mimo zerwanej sieci. Klient wysyła
unikalny `Idempotency-Key` per logiczna debata (ten sam na retry); serwer
przyjmuje klucz tylko raz w oknie TTL — duplikat → 409 `duplicate_debate_request`.

Klucz jest namespacowany tenant+user (izolacja multi-tenant: cudzy klucz nie
może zablokować mojego żądania). Redis SET NX (multi-instancja); fallback
in-memory dla dev/desktop bez Redis (pojedynczy proces — wystarczające).
Nagłówek opcjonalny: starzy klienci działają bez zmian (brak ochrony = status quo).
"""

from __future__ import annotations

import time

from fastapi import HTTPException, Request

_TTL_SECONDS = 300  # okno retry klienta to sekundy; 5 min z zapasem
_mem: dict[str, float] = {}


def _prune_mem(now: float) -> None:
    if len(_mem) > 1024:
        for k, exp in list(_mem.items()):
            if exp < now:
                _mem.pop(k, None)


async def claim_debate_idempotency_key(request: Request) -> None:
    """Rezerwuje Idempotency-Key żądania. Duplikat w oknie TTL → 409."""
    raw = (request.headers.get("Idempotency-Key") or "").strip()
    if not raw:
        return
    if len(raw) > 128:
        raise HTTPException(422, "Idempotency-Key: max 128 znaków.")

    from db.tenant import current_tenant_id, current_user_id

    key = f"idem:debate:{current_tenant_id()}:{current_user_id()}:{raw}"

    from api.runtime import get_redis

    r = get_redis()
    if r is not None:
        try:
            ok = await r.set(key, "1", nx=True, ex=_TTL_SECONDS)
            if ok:
                return
            raise HTTPException(
                409,
                detail={
                    "code": "duplicate_debate_request",
                    "message": (
                        "To żądanie debaty zostało już przyjęte — pierwotne "
                        "połączenie nadal jest przetwarzane. Sprawdź historię "
                        "debat zamiast ponawiać."
                    ),
                },
            )
        except HTTPException:
            raise
        except Exception:
            pass  # awaria Redis nie blokuje debaty — spadamy na pamięć procesu

    now = time.monotonic()
    _prune_mem(now)
    exp = _mem.get(key)
    if exp is not None and exp >= now:
        raise HTTPException(
            409,
            detail={
                "code": "duplicate_debate_request",
                "message": (
                    "To żądanie debaty zostało już przyjęte — pierwotne "
                    "połączenie nadal jest przetwarzane. Sprawdź historię "
                    "debat zamiast ponawiać."
                ),
            },
        )
    _mem[key] = now + _TTL_SECONDS
