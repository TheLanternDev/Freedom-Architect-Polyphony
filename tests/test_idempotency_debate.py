"""P1-B1: Idempotency-Key — duplikat żądania debaty (retry SSE) → 409."""

from __future__ import annotations

import pytest
from fastapi import HTTPException


class _Req:
    def __init__(self, key: str | None):
        self.headers = {"Idempotency-Key": key} if key else {}


@pytest.fixture(autouse=True)
def _no_redis_and_clean_mem(monkeypatch):
    import api.idempotency as idem
    import api.runtime as runtime

    monkeypatch.setattr(runtime, "get_redis", lambda: None)
    idem._mem.clear()
    yield
    idem._mem.clear()


@pytest.mark.asyncio
async def test_first_claim_passes_duplicate_409():
    from api.idempotency import claim_debate_idempotency_key

    await claim_debate_idempotency_key(_Req("k-1"))  # pierwszy — OK
    with pytest.raises(HTTPException) as ei:
        await claim_debate_idempotency_key(_Req("k-1"))  # retry → 409
    assert ei.value.status_code == 409
    assert ei.value.detail["code"] == "duplicate_debate_request"


@pytest.mark.asyncio
async def test_missing_header_is_noop():
    from api.idempotency import claim_debate_idempotency_key

    await claim_debate_idempotency_key(_Req(None))
    await claim_debate_idempotency_key(_Req(None))  # brak nagłówka = brak blokady


@pytest.mark.asyncio
async def test_key_namespaced_per_tenant():
    from api.idempotency import claim_debate_idempotency_key
    from db.tenant import reset_current_tenant_id, set_current_tenant_id

    t_a = set_current_tenant_id("tenant-a")
    try:
        await claim_debate_idempotency_key(_Req("k-x"))
    finally:
        reset_current_tenant_id(t_a)

    t_b = set_current_tenant_id("tenant-b")
    try:
        # Ten sam klucz, inny tenant — NIE może być zablokowany (izolacja).
        await claim_debate_idempotency_key(_Req("k-x"))
    finally:
        reset_current_tenant_id(t_b)


@pytest.mark.asyncio
async def test_key_too_long_422():
    from api.idempotency import claim_debate_idempotency_key

    with pytest.raises(HTTPException) as ei:
        await claim_debate_idempotency_key(_Req("x" * 129))
    assert ei.value.status_code == 422
