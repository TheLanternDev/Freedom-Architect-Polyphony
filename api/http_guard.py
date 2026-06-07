"""
HTTP: autoryzacja — współdzielony Bearer (legacy), nagłówek serwisowy BFF lub JWT użytkownika.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from api import settings
from api.auth_identity import decode_user_jwt_checked
from db.tenant import (
    DEFAULT_TENANT,
    DEFAULT_USER,
    set_current_tenant_id,
    set_current_user_id,
)

logger = logging.getLogger(__name__)


def _public_paths() -> frozenset[str]:
    p = frozenset(
        {
            "/health",
            "/health/ready",
            "/edition",
            "/",
        }
    )
    force_docs = os.getenv("AW_FORCE_OPENAPI", "").strip().lower() in ("1", "true", "yes")
    if not settings.is_production() or force_docs:
        return p | frozenset({"/openapi.json", "/docs", "/redoc"})
    return p


def _admin_self_auth_paths(path: str) -> bool:
    """Endpointy z własnym fail-closed (`ARCHITEKT_ADMIN_TOKEN` w handlerze).

    Pomijamy wspólną weryfikację JWT/legacy w guardzie — inaczej Bearer admin
    token koliduje z `Authorization` używanym do JWT (P0-A1).
    """
    return path == "/metrics" or path.startswith("/admin/")


def _device_gate_allowlist(path: str) -> bool:
    """Ścieżki dostępne nawet przy zablokowanym urządzeniu.

    SPA musi móc się załadować i pokazać ekran blokady: statyczne assety,
    /edition (bootstrap UI), /health (liveness) oraz /device/status (samo
    sprawdzenie blokady). Reszta jest twardo zablokowana 423-ką.
    """
    return (
        path == "/device/status"
        or path in _public_paths()
        or path.startswith("/assets/")
    )


async def architekt_http_guard(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path

    # ── Warstwa 0: device binding (przed auth) ──────────────────────────────
    # Miękka bariera przeciw skopiowaniu folderu aplikacji na inny komputer.
    # NIE jest izolacją danych (tę zapewnia auth + RLS) — to osobna, wcześniejsza
    # warstwa. Gdy pieczęć pochodzi z innej maszyny → 423 Locked na wszystkim
    # poza allowlistą potrzebną do wyświetlenia ekranu blokady w SPA.
    from core.device_seal import ensure_and_verify

    seal = ensure_and_verify()
    if seal.status == "locked" and not _device_gate_allowlist(path):
        return JSONResponse(
            {
                "detail": (
                    "Ta instalacja Architekta jest powiązana z innym komputerem. "
                    "Uruchomienie skopiowanej wersji na nowej maszynie jest "
                    "niemożliwe. Jeśli zmieniasz sprzęt — uruchom reset: "
                    "python -m tools.device_reset"
                ),
                "code": "device_locked",
            },
            status_code=423,
        )

    # /device/status jest publiczny: SPA sprawdza blokadę urządzenia ZANIM
    # pokaże ekran logowania, więc nie może wymagać auth (inaczej 401 zamiast
    # statusu blokady).
    if (
        path == "/device/status"
        or path in _public_paths()
        or path.startswith("/assets/")
        or path.startswith("/auth/")
    ):
        return await call_next(request)

    if _admin_self_auth_paths(path):
        return await call_next(request)

    # Faza 4 — multi-user: ustaw ContextVar tenant_id na podstawie auth.
    # Ważne: ContextVar działa per-asyncio-Task. call_next uruchamia handler
    # w tym samym Task, więc wartość jest widoczna w handlerze i w generatorach
    # SSE, które działają wewnątrz tego samego Task.  NIE resetujemy w finally
    # — reset byłby wykonany zanim generator SSE wyprodukuje jakikolwiek chunk.
    # Wartość i tak jest izolowana per-Task dzięki mechanizmowi ContextVar.
    set_current_tenant_id(DEFAULT_TENANT)
    set_current_user_id(DEFAULT_USER)

    api_key = settings.api_key_legacy()
    jwt_on = settings.jwt_secret_configured()

    if not api_key and not jwt_on:
        # Stage 1 hardening: fail-closed gdy brak sekretów.
        # Dev-only bypass (nigdy w produkcji): AW_INSECURE_NO_AUTH=1
        if os.getenv("AW_INSECURE_NO_AUTH", "").strip().lower() in ("1", "true", "yes"):
            if settings.is_production():
                logger.critical(
                    "AW_INSECURE_NO_AUTH=1 niedozwolone w produkcji — blokuję żądanie"
                )
                return JSONResponse(
                    {"detail": "AW_INSECURE_NO_AUTH niedozwolone w środowisku produkcyjnym."},
                    status_code=403,
                )
            logger.warning(
                "⚠️  AW_INSECURE_NO_AUTH=1 — uwierzytelnianie pominięte (wyłącznie dev/test)"
            )
            return await call_next(request)
        return JSONResponse(
            {
                "detail": (
                    "Brak konfiguracji autoryzacji — ustaw ARCHITEKT_JWT_SECRET lub "
                    "ARCHITEKT_API_KEY. Dev-only bypass (nigdy w produkcji): AW_INSECURE_NO_AUTH=1."
                )
            },
            status_code=401,
        )

    hdr_svc = settings.service_api_header_name()
    svc_val = (request.headers.get(hdr_svc) or "").strip()
    if api_key and svc_val and hmac.compare_digest(svc_val, api_key):
        request.state.architekt_auth = "service_header"
        # Faza 4: ścieżka BFF/proxy. Współdzielony klucz serwisowy NIE niesie
        # tożsamości — musi ją przekazać BFF w nagłówkach (X-Tenant-Id / X-User-Id).
        # Bez tego cały ruch przez BFF działałby jako jeden tenant `default` →
        # cross-user leak. W trybie multi-user (JWT aktywne) brak tenanta = 403.
        th = settings.tenant_header_name()
        fwd_tid = (request.headers.get(th) or "").strip()
        uh = (os.getenv("AW_USER_HEADER") or "X-User-Id").strip()
        fwd_uid = (request.headers.get(uh) or "").strip()
        if jwt_on:
            if not fwd_tid:
                return JSONResponse(
                    {
                        "detail": (
                            f"Service-header w trybie multi-user wymaga nagłówka tenanta "
                            f"({th}) — BFF musi propagować tożsamość usera ({uh})."
                        )
                    },
                    status_code=403,
                )
            # Faza 4 hardening: w multi-user X-User-Id jest WYMAGANY. Fallback
            # `user_id := tenant_id` dawał wszystkim userom tenanta wspólny
            # `_cache_key` → cross-user wyciek odpowiedzi LLM w obrębie tenanta
            # (mina pod team-plan). Fail-closed: bez user_id nie ma izolacji cache.
            if not fwd_uid:
                return JSONResponse(
                    {
                        "detail": (
                            f"Service-header w trybie multi-user wymaga nagłówka usera "
                            f"({uh}) — BFF musi propagować tożsamość usera dla izolacji cache."
                        )
                    },
                    status_code=403,
                )
            set_current_tenant_id(fwd_tid)
            set_current_user_id(fwd_uid)
        elif fwd_tid:
            # Single-tenant deployment: nagłówki opcjonalne, ale honorujemy je gdy są.
            set_current_tenant_id(fwd_tid)
            set_current_user_id(fwd_uid or fwd_tid)
        return await call_next(request)

    auth = (request.headers.get("authorization") or "").strip()
    bearer: str | None = None
    if auth.lower().startswith("bearer "):
        bearer = auth[7:].strip()

    if bearer and jwt_on:
        payload = await decode_user_jwt_checked(bearer)
        if payload:
            request.state.architekt_auth = "jwt"
            sub = payload.get("sub")
            tid = payload.get("tenant_id")
            request.state.architekt_subject = sub
            request.state.architekt_tenant_id = tid
            # Faza 4: tenant_id z JWT → ContextVar; fallback: sub.
            set_current_tenant_id(str(tid or sub or DEFAULT_TENANT))
            # AKSJOMAT 1 / cache isolation: user_id (claim `sub`) → ContextVar.
            # `BaseAgent._cache_key` używa go do hard-isolation cache LLM między
            # userami tego samego tenanta (zapobiega cross-user wycieku odpowiedzi).
            set_current_user_id(str(sub or DEFAULT_USER))
            if settings.enforce_tenant_header_match():
                th = settings.tenant_header_name()
                hdr_tid = (request.headers.get(th) or "").strip()
                claim_tid = str(tid or "").strip()
                if hdr_tid and claim_tid and hdr_tid != claim_tid:
                    return JSONResponse(
                        {"detail": "tenant mismatch — nagłówek vs JWT"},
                        status_code=403,
                    )
            return await call_next(request)

    if api_key and bearer and hmac.compare_digest(bearer, api_key):
        # Stage 1 hardening: gdy JWT skonfigurowane, legacy bearer odrzucony.
        # Shared key nie derivuje tenant_id → ryzyko cross-user data leaku.
        if jwt_on:
            return JSONResponse(
                {
                    "detail": (
                        "Legacy ARCHITEKT_API_KEY odrzucony — serwer ma aktywny JWT. "
                        "Użyj POST /auth/login aby uzyskać per-user JWT."
                    )
                },
                status_code=401,
            )
        request.state.architekt_auth = "legacy_bearer"
        response = await call_next(request)
        response.headers["Deprecation"] = "true"
        response.headers["X-Auth-Warning"] = (
            "Shared ARCHITEKT_API_KEY is deprecated. "
            "Use per-user JWT via POST /auth/login instead."
        )
        return response

    return JSONResponse(
        {
            "detail": (
                "Unauthorized — podaj JWT użytkownika (ARCHITEKT_JWT_SECRET), "
                "Bearer ARCHITEKT_API_KEY (wyłącznie poza przeglądarką / przez BFF), "
                "lub nagłówek serwisowy — patrz docs/SECURITY_PRODUCTION.md."
            )
        },
        status_code=401,
    )
