"""Testy budget_guard: twardy budżet, warning SSE, brak Redis."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

from api.services.budget_guard import (
    spent_today_usd,
    maybe_budget_warning_sse,
    ensure_hard_budget_or_raise,
)


class TestSpentTodayUsd:
    def test_returns_zero_when_cost_tracking_unavailable(self):
        """Bez modułu cost_tracking → 0.0."""
        with patch("api.services.budget_guard.load_budget_snapshot", None):
            assert spent_today_usd() == 0.0

    def test_returns_value_from_snapshot(self):
        """Z dostępnym snapshot → zwraca spent_today_usd."""
        snap = MagicMock()
        snap.spent_today_usd = 1.23
        with patch("api.services.budget_guard.load_budget_snapshot", return_value=snap):
            assert spent_today_usd() == 1.23


class TestMaybeBudgetWarningSse:
    def test_no_env_returns_none(self, monkeypatch):
        """Bez DAILY_BUDGET_USD → None."""
        monkeypatch.delenv("DAILY_BUDGET_USD", raising=False)
        assert maybe_budget_warning_sse() is None

    def test_under_budget_returns_none(self, monkeypatch):
        """Wydano mniej niż ceiling → None."""
        monkeypatch.setenv("DAILY_BUDGET_USD", "5.0")
        with patch("api.services.budget_guard.spent_today_usd", return_value=2.0):
            assert maybe_budget_warning_sse() is None

    def test_over_budget_returns_sse_event(self, monkeypatch):
        """Wydano >= ceiling → SSE event budget_warning."""
        monkeypatch.setenv("DAILY_BUDGET_USD", "3.0")
        with patch("api.services.budget_guard.spent_today_usd", return_value=3.5):
            result = maybe_budget_warning_sse()
            assert result is not None
            assert "event: budget_warning" in result
            assert "3.5" in result

    def test_invalid_env_returns_none(self, monkeypatch):
        """Nieparsowalna wartość DAILY_BUDGET_USD → None."""
        monkeypatch.setenv("DAILY_BUDGET_USD", "not_a_number")
        assert maybe_budget_warning_sse() is None


class TestEnsureHardBudgetOrRaise:
    def test_no_cost_tracking_passes(self):
        """Bez modułu cost_tracking → nie rzuca."""
        import asyncio
        with patch("api.services.budget_guard.evaluate_hard_budget", None):
            asyncio.run(ensure_hard_budget_or_raise())  # nie rzuca

    def test_within_budget_passes(self):
        """W budżecie → nie rzuca."""
        import asyncio
        with patch("api.services.budget_guard.evaluate_hard_budget", return_value=None), \
             patch("api.services.budget_guard.load_budget_snapshot", return_value=MagicMock()):
            asyncio.run(ensure_hard_budget_or_raise())  # nie rzuca

    def test_over_budget_raises_402(self):
        """Przekroczony budżet → HTTPException 402."""
        import asyncio
        block = MagicMock()
        block.kind = "daily"
        block.spent_usd = 10.0
        block.ceiling_usd = 5.0
        block.message_pl = "Limit dzienny"
        with patch("api.services.budget_guard.evaluate_hard_budget", return_value=block), \
             patch("api.services.budget_guard.load_budget_snapshot", return_value=MagicMock()), \
             patch("api.services.budget_guard.maybe_fire_cost_webhook", None):
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(ensure_hard_budget_or_raise())
            assert exc_info.value.status_code == 402
            assert exc_info.value.detail["kind"] == "daily"
