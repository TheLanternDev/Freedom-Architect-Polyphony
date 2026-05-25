"""Konfiguracja środowiska: produkcja, CORS, dokumentacja OpenAPI."""

from __future__ import annotations

import os


def is_production() -> bool:
    v = (os.getenv("AW_ENV") or os.getenv("NODE_ENV") or "").strip().lower()
    return v in ("production", "prod")


def openapi_urls() -> tuple[str | None, str | None, str | None]:
    """
    W produkcji domyślnie wyłączamy `/docs`, `/redoc`, `/openapi.json`
    (mniejsza powierzchnia ataku). Wymuszenie: AW_FORCE_OPENAPI=1.
    """
    if is_production() and os.getenv("AW_FORCE_OPENAPI", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return None, None, None
    return "/docs", "/redoc", "/openapi.json"


_DEV_VITE_ORIGINS = (
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    "tauri://localhost",
    "http://tauri.localhost",
)


def cors_allow_origins() -> list[str]:
    """Produkcja: `AW_CORS_ORIGINS=https://app.example.com` (lista CSV).
    Dev (`AW_ENV != production`): jeśli ENV ustawione — używamy go, ale
    automatycznie *dosypujemy* origins Vite/Tauri (1420 + tauri://localhost),
    żeby przykładowy `.env` skopiowany bez świadomości nie blokował lokalnego UI.
    Brak ENV w dev → `*` (otwarcie, jak dotąd).
    """
    raw = (os.getenv("AW_CORS_ORIGINS") or "*").strip()

    if is_production() and raw == "*":
        import logging
        logging.getLogger(__name__).warning(
            "⚠️  PRODUKCJA: AW_CORS_ORIGINS='*' — ustaw konkretne origins!"
        )

    if raw == "*":
        return ["*"]
    out = [p.strip() for p in raw.split(",") if p.strip()]
    if not out:
        return ["*"]
    if not is_production():
        for origin in _DEV_VITE_ORIGINS:
            if origin not in out:
                out.append(origin)
    return out


def rate_limit_enabled() -> bool:
    return os.getenv("AW_DISABLE_RATE_LIMIT", "").lower() not in ("1", "true", "yes")


def debate_rate_limit() -> str:
    try:
        n = int(os.getenv("AW_RATE_DEBATE_PER_MINUTE", "30") or "30")
    except ValueError:
        n = 30
    n = max(5, min(n, 120))
    return f"{n}/minute"


def service_api_header_name() -> str:
    """Nagłówek zaufanej warstwy (BFF/proxy), nie z przeglądarki."""
    return (os.getenv("ARCHITEKT_SERVICE_HEADER") or "X-Architekt-Service-Key").strip()


def api_key_legacy() -> str:
    return (os.getenv("ARCHITEKT_API_KEY") or "").strip()


def jwt_secret_configured() -> bool:
    return bool((os.getenv("ARCHITEKT_JWT_SECRET") or "").strip())


def require_tenant_claim() -> bool:
    return os.getenv("AW_REQUIRE_TENANT_JWT_CLAIM", "").lower() in ("1", "true", "yes")


def enforce_tenant_header_match() -> bool:
    """Jeśli JWT ma tenant_id oraz klient podaje X-Tenant-Id — muszą być zgodne."""
    return os.getenv("AW_ENFORCE_TENANT_HEADER", "").lower() in ("1", "true", "yes")


def tenant_header_name() -> str:
    return (os.getenv("AW_TENANT_HEADER") or "X-Tenant-Id").strip()
