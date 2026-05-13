"""
HTTP: autoryzacja — współdzielony Bearer (legacy), nagłówek serwisowy BFF lub JWT użytkownika.
"""

from __future__ import annotations

import logging
import os
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from api import settings
from api.auth_identity import decode_user_jwt

logger = logging.getLogger(__name__)


def _public_paths() -> frozenset[str]:
    p = frozenset(
        {
            "/health",
            "/health/ready",
            "/",
        }
    )
    force_docs = os.getenv("AW_FORCE_OPENAPI", "").strip().lower() in ("1", "true", "yes")
    if not settings.is_production() or force_docs:
        return p | frozenset({"/openapi.json", "/docs", "/redoc"})
    return p


async def architekt_http_guard(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if path in _public_paths() or path.startswith("/assets/"):
        return await call_next(request)

    api_key = settings.api_key_legacy()
    jwt_on = settings.jwt_secret_configured()

    if not api_key and not jwt_on:
        return await call_next(request)

    hdr_svc = settings.service_api_header_name()
    svc_val = (request.headers.get(hdr_svc) or "").strip()
    if api_key and svc_val == api_key:
        request.state.architekt_auth = "service_header"
        return await call_next(request)

    auth = (request.headers.get("authorization") or "").strip()
    bearer: str | None = None
    if auth.lower().startswith("bearer "):
        bearer = auth[7:].strip()

    if bearer and jwt_on:
        payload = decode_user_jwt(bearer)
        if payload:
            request.state.architekt_auth = "jwt"
            request.state.architekt_subject = payload.get("sub")
            request.state.architekt_tenant_id = payload.get("tenant_id")
            if settings.enforce_tenant_header_match():
                th = settings.tenant_header_name()
                hdr_tid = (request.headers.get(th) or "").strip()
                claim_tid = str(payload.get("tenant_id") or "").strip()
                if hdr_tid and claim_tid and hdr_tid != claim_tid:
                    return JSONResponse(
                        {"detail": "tenant mismatch — nagłówek vs JWT"},
                        status_code=403,
                    )
            return await call_next(request)

    if api_key and bearer == api_key:
        request.state.architekt_auth = "legacy_bearer"
        return await call_next(request)

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
