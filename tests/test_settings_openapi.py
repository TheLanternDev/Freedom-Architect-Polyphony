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
    from api.settings import cors_allow_origins

    assert cors_allow_origins() == ["https://a.example", "https://b.example"]
