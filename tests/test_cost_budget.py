"""Twarde limity kosztów i endpoint `/costs/status`."""

from __future__ import annotations

import api.services.budget_guard as budget_guard
from core.cost_tracking import BudgetSnapshot


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
