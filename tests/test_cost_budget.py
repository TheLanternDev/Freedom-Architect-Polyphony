"""Twarde limity kosztów i endpoint `/costs/status`."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import api.services.budget_guard as budget_guard
from core.cost_tracking import BudgetSnapshot, _append_cost_line_sync, build_cost_entry


def test_costs_status_returns_payload(client_no_redis):
    r = client_no_redis.get("/costs/status")
    assert r.status_code == 200
    data = r.json()
    assert "spent_today_usd" in data
    assert "spent_month_usd" in data
    assert "limits" in data
    assert "recent" in data


def test_debate_stream_402_when_daily_hard_exceeded(
    client_no_redis, valid_brief_payload, monkeypatch
):
    monkeypatch.setenv("DAILY_BUDGET_HARD_USD", "1.0")
    monkeypatch.setattr(
        budget_guard,
        "load_budget_snapshot",
        lambda: BudgetSnapshot(
            spent_today_usd=100.0,
            spent_month_usd=100.0,
            day_iso="2099-01-01",
            year=2099,
            month=1,
        ),
    )

    r = client_no_redis.post("/debate/stream", json=valid_brief_payload)
    assert r.status_code == 402
    body = r.json()
    assert body["detail"]["error"] == "budget_exceeded"
    assert body["detail"]["kind"] == "daily_hard"


def test_append_cost_line_sync_concurrent_writes(tmp_path: Path) -> None:
    """P1-B2: flock przy append — wiele wątków nie psuje linii JSONL."""
    log_path = tmp_path / "cost_log.jsonl"
    barrier = threading.Barrier(8)

    def writer(i: int) -> None:
        barrier.wait()
        _append_cost_line_sync(log_path, json.dumps({"i": i}) + "\n")

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 8
    indices = {json.loads(ln)["i"] for ln in lines}
    assert indices == set(range(8))


def _entry_kwargs() -> dict:
    return dict(
        agent="Syez", model="m", input_tokens=10, output_tokens=20,
        cost_usd=0.001234, context="brief",
    )


def test_build_cost_entry_includes_tenant_from_contextvar() -> None:
    """P1-E1: wpis kosztu niesie tenant_id z ContextVar (per-tenant metering)."""
    from db.tenant import reset_current_tenant_id, set_current_tenant_id

    token = set_current_tenant_id("tenant-abc")
    try:
        entry = build_cost_entry(**_entry_kwargs())
    finally:
        # Izolacja między testami — przywróć poprzedni stan ContextVar.
        reset_current_tenant_id(token)
    assert entry["tenant_id"] == "tenant-abc"
    assert entry["cost_usd"] == 0.001234


def test_build_cost_entry_tenant_defaults_outside_request() -> None:
    """Poza requestem (CLI/testy) tenant_id = DEFAULT_TENANT — wpis się nie wywraca."""
    from db.tenant import DEFAULT_TENANT

    entry = build_cost_entry(**_entry_kwargs())
    assert entry["tenant_id"] == DEFAULT_TENANT
    assert "brief_hash" in entry and len(entry["brief_hash"]) == 16
