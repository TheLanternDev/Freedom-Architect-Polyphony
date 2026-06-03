"""Testy fail-fast startup w produkcji (Redis, init_db)."""

from __future__ import annotations

import pytest

from api.startup import handle_init_db_failure, redis_required_in_prod


def test_redis_required_in_prod_when_redis_url_set(monkeypatch):
    monkeypatch.setenv("AW_ENV", "production")
    monkeypatch.delenv("AW_DEMO_MODE", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

    assert redis_required_in_prod() is True


def test_redis_not_required_in_demo_prod(monkeypatch):
    monkeypatch.setenv("AW_ENV", "production")
    monkeypatch.setenv("AW_DEMO_MODE", "1")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

    assert redis_required_in_prod() is False


def test_redis_not_required_in_development(monkeypatch):
    monkeypatch.setenv("AW_ENV", "development")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

    assert redis_required_in_prod() is False


def test_init_db_failure_exits_in_production(monkeypatch):
    monkeypatch.setenv("AW_ENV", "production")

    with pytest.raises(SystemExit, match="inicjalizacja bazy"):
        handle_init_db_failure(RuntimeError("db down"))


def test_init_db_failure_logs_in_development(monkeypatch):
    monkeypatch.setenv("AW_ENV", "development")

    handle_init_db_failure(RuntimeError("db down"))
