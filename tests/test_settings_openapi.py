"""Konfiguracja prod vs dokumentacja OpenAPI."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_aw_env(monkeypatch):
    monkeypatch.delenv("AW_FORCE_OPENAPI", raising=False)


def test_openapi_hidden_in_production(monkeypatch):
    monkeypatch.setenv("AW_ENV", "production")
    from api.settings import openapi_urls

    assert openapi_urls() == (None, None, None)


def test_openapi_force_in_production(monkeypatch):
    monkeypatch.setenv("AW_ENV", "production")
    monkeypatch.setenv("AW_FORCE_OPENAPI", "1")
    from api.settings import openapi_urls

    assert openapi_urls() == ("/docs", "/redoc", "/openapi.json")


def test_openapi_visible_in_development(monkeypatch):
    monkeypatch.setenv("AW_ENV", "development")
    from api.settings import openapi_urls

    assert openapi_urls()[0] == "/docs"


def test_cors_explicit_origins(monkeypatch):
    monkeypatch.setenv("AW_CORS_ORIGINS", "https://a.example,https://b.example")
    monkeypatch.setenv("AW_ENV", "production")
    from api.settings import cors_allow_origins

    assert cors_allow_origins() == ["https://a.example", "https://b.example"]


def test_cors_dev_default_wildcard(monkeypatch):
    monkeypatch.delenv("AW_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("AW_ENV", "development")
    from api.settings import cors_allow_origins

    assert cors_allow_origins() == ["*"]


def test_cors_production_rejects_wildcard(monkeypatch):
    monkeypatch.setenv("AW_ENV", "production")
    monkeypatch.setenv("AW_CORS_ORIGINS", "*")
    from api.settings import ProductionConfigError, cors_allow_origins

    with pytest.raises(ProductionConfigError, match="PRODUKCJA wymaga AW_CORS_ORIGINS"):
        cors_allow_origins()


def test_cors_production_rejects_missing(monkeypatch):
    monkeypatch.setenv("AW_ENV", "production")
    monkeypatch.delenv("AW_CORS_ORIGINS", raising=False)
    from api.settings import ProductionConfigError, cors_allow_origins

    with pytest.raises(ProductionConfigError, match="PRODUKCJA wymaga AW_CORS_ORIGINS"):
        cors_allow_origins()


def test_production_preflight_lists_critical_gaps(monkeypatch):
    monkeypatch.setenv("AW_ENV", "production")
    monkeypatch.delenv("AW_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("ARCHITEKT_JWT_SECRET", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    from api.settings import production_preflight_errors

    msgs = production_preflight_errors()
    assert any("ARCHITEKT_JWT_SECRET" in m for m in msgs)
    assert any("AW_CORS_ORIGINS" in m for m in msgs)
    assert any("REDIS_URL" in m for m in msgs)
