"""Konfiguracja środowiska: produkcja, CORS, dokumentacja OpenAPI."""

from __future__ import annotations

import os


class ProductionConfigError(RuntimeError):
    """Niebezpieczna lub niekompletna konfiguracja produkcyjna — fail-fast przy starcie."""


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


def cors_origins_env_raw() -> str:
    """Wartość AW_CORS_ORIGINS z ENV (pusty string = brak ustawienia)."""
    return (os.getenv("AW_CORS_ORIGINS") or "").strip()


def validate_production_cors() -> None:
    """Produkcja: jawna lista origins — bez '*' i bez pustej wartości."""
    if not is_production():
        return
    raw = cors_origins_env_raw()
    if not raw or raw == "*":
        raise ProductionConfigError(
            "PRODUKCJA wymaga AW_CORS_ORIGINS — ustaw konkretne origins CSV "
            "(np. https://app.example.com). Wildcard '*' i brak zmiennej są zabronione."
        )
    origins = [p.strip() for p in raw.split(",") if p.strip()]
    if not origins:
        raise ProductionConfigError(
            "PRODUKCJA wymaga AW_CORS_ORIGINS — lista origins nie może być pusta."
        )
    if "*" in origins:
        raise ProductionConfigError(
            "PRODUKCJA wymaga AW_CORS_ORIGINS — wildcard '*' w liście jest zabroniony."
        )


def postgres_configured() -> bool:
    u = (os.getenv("DATABASE_URL") or "").strip().lower()
    return u.startswith(("postgresql://", "postgres://"))


def jwt_secret_strength_ok() -> bool:
    """PyJWT zaleca ≥32 bajty entropii dla HS256."""
    secret = (os.getenv("ARCHITEKT_JWT_SECRET") or "").strip()
    return len(secret) >= 32


def production_preflight_errors() -> list[str]:
    """Krytyczne braki konfiguracji produkcyjnej (teksty do logów i SystemExit)."""
    if not is_production():
        return []
    errors: list[str] = []
    demo = demo_mode_enabled()
    if not postgres_configured():
        errors.append(
            "DATABASE_URL=postgresql://… wymagany w produkcji — SQLite nie ma RLS; "
            "multi-user wymaga Postgres + migracji RLS (0001–0005)."
        )
    if not jwt_secret_configured():
        errors.append(
            "ARCHITEKT_JWT_SECRET wymagany w produkcji — logowanie JWT (/auth/login) "
            "i izolacja tenantów."
        )
    elif not jwt_secret_strength_ok():
        errors.append(
            "ARCHITEKT_JWT_SECRET za krótki (< 32 znaki) — użyj losowego sekretu "
            "≥32 bajtów (PyJWT / OWASP)."
        )
    try:
        validate_production_cors()
    except ProductionConfigError as exc:
        errors.append(str(exc))
    if not demo and not (os.getenv("REDIS_URL") or "").strip():
        errors.append(
            "REDIS_URL wymagany w produkcji — refresh tokeny (/auth/refresh), "
            "globalny rate-limit przy wielu instancjach i JTI revoke."
        )
    if not (os.getenv("ANTHROPIC_API_KEY") or "").strip():
        errors.append("ANTHROPIC_API_KEY wymagany w produkcji.")
    if not (os.getenv("ARCHITEKT_ADMIN_TOKEN") or "").strip():
        # Stage 1: usunięto `not demo` — admin token wymagany zawsze (endpointy fail-closed).
        errors.append(
            "ARCHITEKT_ADMIN_TOKEN wymagany w produkcji — /admin/* i /metrics są wyłączone bez tokenu."
        )
    return errors


def cors_allow_origins() -> list[str]:
    """Produkcja: `AW_CORS_ORIGINS=https://app.example.com` (lista CSV, fail-fast).
    Dev (`AW_ENV != production`): jeśli ENV ustawione — używamy go, ale
    automatycznie *dosypujemy* origins Vite/Tauri (1420 + tauri://localhost),
    żeby przykładowy `.env` skopiowany bez świadomości nie blokował lokalnego UI.
    Brak ENV w dev → `*` (otwarcie, jak dotąd).
    """
    if is_production():
        validate_production_cors()
        return [p.strip() for p in cors_origins_env_raw().split(",") if p.strip()]

    raw = (os.getenv("AW_CORS_ORIGINS") or "*").strip()
    if raw == "*":
        return ["*"]
    out = [p.strip() for p in raw.split(",") if p.strip()]
    if not out:
        return ["*"]
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


def write_rate_limit() -> str:
    """Limit dla mutacji (np. /commitment). Domyślnie 60/min."""
    try:
        n = int(os.getenv("AW_RATE_WRITE_PER_MINUTE", "60") or "60")
    except ValueError:
        n = 60
    n = max(5, min(n, 240))
    return f"{n}/minute"


def service_api_header_name() -> str:
    """Nagłówek zaufanej warstwy (BFF/proxy), nie z przeglądarki."""
    return (os.getenv("ARCHITEKT_SERVICE_HEADER") or "X-Architekt-Service-Key").strip()


def api_key_legacy() -> str:
    return (os.getenv("ARCHITEKT_API_KEY") or "").strip()


def jwt_secret_configured() -> bool:
    return bool((os.getenv("ARCHITEKT_JWT_SECRET") or "").strip())


def require_tenant_claim() -> bool:
    # Multi-user: JWT bez claimu `tenant_id` jest odrzucany. Domyślnie ON w
    # produkcji (fallback `tenant_id := sub` jest akceptowalny tylko dev/single-user;
    # w prod wymagamy jawnego tenanta, by uniknąć kolizji `sub` między wydawcami).
    # Jawny opt-out: AW_REQUIRE_TENANT_JWT_CLAIM=0.
    v = os.getenv("AW_REQUIRE_TENANT_JWT_CLAIM", "").strip().lower()
    if v in ("1", "true", "yes"):
        return True
    if v in ("0", "false", "no"):
        return False
    return is_production()


def enforce_tenant_header_match() -> bool:
    """Jeśli JWT ma tenant_id oraz klient podaje X-Tenant-Id — muszą być zgodne."""
    return os.getenv("AW_ENFORCE_TENANT_HEADER", "").lower() in ("1", "true", "yes")


def tenant_header_name() -> str:
    return (os.getenv("AW_TENANT_HEADER") or "X-Tenant-Id").strip()


def demo_mode_enabled() -> bool:
    """Publiczne demo interaktywne — sesje gościa, limity debat, bez rejestracji."""
    return os.getenv("AW_DEMO_MODE", "").strip().lower() in ("1", "true", "yes")


def demo_max_debates() -> int:
    try:
        n = int(os.getenv("AW_DEMO_MAX_DEBATES", "2") or "2")
    except ValueError:
        n = 2
    return max(1, min(n, 10))


def demo_max_brief_chars() -> int:
    try:
        n = int(os.getenv("AW_DEMO_MAX_BRIEF_CHARS", "800") or "800")
    except ValueError:
        n = 800
    return max(100, min(n, 2000))


def demo_allowed_modes() -> frozenset[str]:
    raw = (os.getenv("AW_DEMO_ALLOWED_MODES") or "codzienny").strip()
    modes = {m.strip() for m in raw.split(",") if m.strip()}
    return frozenset(modes) if modes else frozenset({"codzienny"})


def demo_allowed_categories() -> frozenset[str]:
    raw = (os.getenv("AW_DEMO_ALLOWED_CATEGORIES") or "decyzja").strip()
    cats = {c.strip() for c in raw.split(",") if c.strip()}
    return frozenset(cats) if cats else frozenset({"decyzja"})


def demo_jwt_ttl_seconds() -> int:
    try:
        n = int(os.getenv("AW_DEMO_JWT_TTL_SEC", "86400") or "86400")
    except ValueError:
        n = 86400
    return max(3600, min(n, 7 * 86400))


def demo_config_public() -> dict[str, object]:
    """Konfiguracja demo dla UI (bez sekretów)."""
    return {
        "enabled": demo_mode_enabled(),
        "max_debates": demo_max_debates(),
        "max_brief_chars": demo_max_brief_chars(),
        "allowed_modes": sorted(demo_allowed_modes()),
        "allowed_categories": sorted(demo_allowed_categories()),
    }
