"""
Architekt Wolności — backend FastAPI v3.3.

v3.2 wbija w kod dwa AKSJOMATY pierwotnego sensu projektu:
  AKSJOMAT 1: Architektura Marzenia (core/dream_architect.py)
  AKSJOMAT 2: Doprowadzanie Projektów Do Końca (core/completion_enforcer.py)

Zmiany kluczowe vs. v3.1:
- Faza A0: PRZED 9 agentami destylujemy `DreamArchitecture` i emitujemy
  SSE event `dream_architecture`. Marzenie jest kontekstem dla każdego agenta.
- Hard-lock `MAX_ACTIVE_PROJECTS` przy `category=projekt`.
- Synteza Syeza jest **polską prozą**; audyt domknięcia (AKSJOMAT 2) jest
  walidowany z treści prozy (lub — legacy — z pola JSON `completion_audit`).
  Przy naruszeniu następuje jeden re-prompt naprawczy.
- Endpointy `/dreams`, `/projects`, `/projects/{id}/functionality/{item_id}`,
  `/projects/{id}/complete`, `/projects/{id}/archive`.
- SQLite persystencja (lifespan init).
"""

from __future__ import annotations

# `src/.env` (lub `AW_ENV_FILE`) — przed importami lokalnymi; wypełnia brakujące / puste zmienne.
try:  # pragma: no cover
    import importlib.util
    from pathlib import Path as _RepoPath

    _aw_root = _RepoPath(__file__).resolve().parent
    _aw_spec = importlib.util.spec_from_file_location(
        "aw_env_bootstrap", _aw_root / "env_bootstrap.py"
    )
    if _aw_spec and _aw_spec.loader:
        _aw_env = importlib.util.module_from_spec(_aw_spec)
        _aw_spec.loader.exec_module(_aw_env)
        _aw_env.load_repo_env()
except Exception:
    pass

import asyncio
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# `datetime.UTC` jest dostępne od Pythona 3.11 — zapewniamy zgodność wsteczną do 3.10.
try:
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - tylko Python < 3.11
    UTC = timezone.utc  # type: ignore[assignment]
from pathlib import Path
from typing import Any, Literal, Optional

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from pydantic import BaseModel, Field, field_validator
from starlette.staticfiles import StaticFiles

# ==================== KONFIG ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ArchitektWolnosci")


def _init_sentry() -> None:
    """Opcjonalny Sentry — tylko gdy SENTRY_DSN w ENV; bez DSN = no-op."""
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning(
            "SENTRY_DSN ustawione, ale sentry-sdk niezainstalowane — Sentry pominięte"
        )
        return

    traces_raw = (os.getenv("SENTRY_TRACES_SAMPLE_RATE") or "0").strip()
    try:
        traces_sample_rate = float(traces_raw)
    except ValueError:
        traces_sample_rate = 0.0

    environment = (
        os.getenv("SENTRY_ENVIRONMENT") or os.getenv("AW_ENV") or "development"
    ).strip()
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
        ],
        send_default_pii=False,
    )
    logger.info("Sentry aktywne (environment=%s)", environment)


def _http_obs_context(request: Request) -> dict[str, str]:
    """Metadane żądania do logów/Sentry — bez treści debat ani briefów (PII)."""
    ctx: dict[str, str] = {
        "http_method": request.method,
        "http_path": request.url.path,
    }
    tid = getattr(request.state, "architekt_tenant_id", None)
    if tid:
        ctx["tenant_id"] = str(tid)
    sub = getattr(request.state, "architekt_subject", None)
    if sub:
        ctx["subject"] = str(sub)
    return ctx


_init_sentry()

# Rada Nadzorcza
try:
    from agents import COUNCIL, SYNTHESIZER, afull_synthesis  # noqa: F401
    RADA_AVAILABLE = True
except ImportError:
    RADA_AVAILABLE = False
    logger.warning("⚠️ agents/ package not found – Rada disabled, using fallback")

# AKSJOMATY (core) — minimalny import na potrzeby main.py routing guards + health
try:
    from core import CompletionViolation, MAX_ACTIVE_PROJECTS  # noqa: F401
    CORE_AVAILABLE = True
except ImportError as e:
    CORE_AVAILABLE = False
    MAX_ACTIVE_PROJECTS = None  # type: ignore[assignment]
    logger.error("⚠️ core/ package not importable: %s", e)

try:
    from core.debate_export import render_debate_markdown
except ImportError:
    render_debate_markdown = None  # type: ignore[misc,assignment]

try:
    from core.debate_export_pdf import render_debate_pdf_bytes
except ImportError:
    render_debate_pdf_bytes = None  # type: ignore[misc,assignment]

# Serwisy wyekstrahowane z main.py v3.3
from api.services.budget_guard import ensure_hard_budget_or_raise as _ensure_hard_budget_or_raise
from api.services.completion_service import run_phase2_maintenance as _run_phase2_startup_tasks
from api.services.debate_orchestrator import stream_debate as _stream_debate
from api.services.project_service import enforce_active_project_limit_for_brief as _enforce_active_project_limit_for_brief

# Persystencja
try:
    from db import DB_PATH, get_db, init_db, repo
    DB_AVAILABLE = True
except ImportError as e:
    DB_AVAILABLE = False
    logger.warning("⚠️ db/ package not importable: %s", e)


redis_client: Optional[aioredis.Redis] = None

from api.settings import cors_allow_origins, debate_rate_limit, openapi_urls, rate_limit_enabled, write_rate_limit
from api.http_guard import architekt_http_guard
from api.routers.meta import router as meta_router

# Faza 4/5: dodatkowe routery
try:
    from api.routers.personal import router as personal_router
except ImportError:
    personal_router = None  # type: ignore[assignment]

try:
    from api.routers.integrations import router as integrations_router
except ImportError:
    integrations_router = None  # type: ignore[assignment]

try:
    from api.routers.auth import router as auth_router
except ImportError:
    auth_router = None  # type: ignore[assignment]

try:
    from api.routers.voice import router as voice_router
except ImportError:
    voice_router = None  # type: ignore[assignment]

try:
    from api.routers.attachment import router as attachment_router
except ImportError:
    attachment_router = None  # type: ignore[assignment]

try:
    from api.routers.account import router as account_router
except ImportError:
    account_router = None  # type: ignore[assignment]

try:
    from api.routers.demo import router as demo_router
except ImportError:
    demo_router = None  # type: ignore[assignment]

try:
    from api.routers.feedback import router as feedback_router
except ImportError:
    feedback_router = None  # type: ignore[assignment]


def _production_startup_checks() -> None:
    """Preflight produkcyjny: brak krytycznych ENV → odmowa startu (fail-fast)."""
    from api.settings import api_key_legacy, is_production, jwt_secret_configured, production_preflight_errors

    if not is_production():
        return

    if api_key_legacy() and not jwt_secret_configured():
        logger.warning(
            "⚠️  ARCHITEKT_API_KEY (shared legacy key) jest ustawiony bez ARCHITEKT_JWT_SECRET. "
            "Shared key dzieli jeden tenant między wszystkich klientów i jest deprecated — "
            "ustaw ARCHITEKT_JWT_SECRET i przełącz klientów na /auth/login (per-user JWT)."
        )

    errors = production_preflight_errors()
    if errors:
        for e in errors:
            logger.critical("🛑 %s", e)
        raise SystemExit(
            "Startup zablokowany — niebezpieczna konfiguracja produkcyjna. "
            "Ustaw wymagane zmienne ENV (patrz logi powyżej)."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _production_startup_checks()

    global redis_client
    # Redis (opcjonalny)
    try:
        redis_url = (os.getenv("REDIS_URL") or "redis://localhost:6379").strip()
        redis_client = aioredis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        await redis_client.ping()
        logger.info("✅ Redis podłączony – cache aktywny")
        import api.runtime as rt

        rt.redis_client = redis_client
    except Exception as e:
        logger.warning(f"⚠️ Redis niedostępny ({e}) – działamy bez cache")
        redis_client = None
        import api.runtime as rt

        rt.redis_client = None

    # Baza: SQLite lub Postgres (`DATABASE_URL`) — patrz db.backend
    if DB_AVAILABLE:
        try:
            await init_db()
            try:
                from db.backend import use_postgres

                if use_postgres():
                    logger.info("✅ PostgreSQL — pool aktywny (DATABASE_URL)")
                else:
                    logger.info("✅ SQLite zainicjalizowany: %s", DB_PATH)
            except Exception:
                logger.info("✅ DB zainicjalizowany: %s", DB_PATH)
            await _run_phase2_startup_tasks()
        except Exception as e:
            logger.error("⚠️ init_db failed: %s", e)

    # Auto-scheduler Fazy 2 (AKSJOMAT 2): okresowy stale-sync + follow-upy.
    # ENV AW_MAINTENANCE_INTERVAL_SEC: 0/brak = wyłączone (default), >0 = co N sekund.
    _maint_task: Optional[asyncio.Task] = None
    _maint_interval = int(os.getenv("AW_MAINTENANCE_INTERVAL_SEC", "0") or "0")
    if DB_AVAILABLE and _maint_interval > 0:
        async def _maintenance_loop() -> None:
            while True:
                await asyncio.sleep(_maint_interval)
                logger.info("[Maintenance] Running scheduled tasks...")
                try:
                    await _run_phase2_startup_tasks()
                except Exception as e:  # pętla nigdy nie wywala aplikacji
                    logger.warning("[Maintenance] failed: %s", e)
        _maint_task = asyncio.create_task(_maintenance_loop())
        logger.info("✅ Maintenance włączone — interwał %ss", _maint_interval)
    else:
        logger.info("ℹ️ Maintenance wyłączone (AW_MAINTENANCE_INTERVAL_SEC=0 lub brak DB)")

    from api.settings import demo_mode_enabled

    if demo_mode_enabled():
        logger.info("🎭 AW_DEMO_MODE=1 — interaktywne demo (sesje gościa, limity debat)")

    yield
    if _maint_task is not None:
        _maint_task.cancel()
    try:
        from db.backend import shutdown_database

        await shutdown_database()
    except Exception as e:
        logger.warning("shutdown_database: %s", e)
    if redis_client:
        await redis_client.close()


_docs_url, _redoc_url, _openapi_url = openapi_urls()

app = FastAPI(
    title="Architekt Wolności - AI Engine v3.3",
    description=(
        'Rada Nadzorcza „Mój Świat” (9 agentów + Syez) + dwa AKSJOMATY: '
        "Architektura Marzenia + Doprowadzanie Projektów Do Końca."
    ),
    version="3.3.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

# Storage rate-limitu: Redis (globalny przy wielu instancjach) lub in-memory
# fallback (pojedynczy proces). Bez storage_uri slowapi liczy per-proces.
_rl_storage = (os.getenv("REDIS_URL") or "").strip() or "memory://"
from api._rate_limit import jwt_or_ip_key
limiter = Limiter(
    key_func=jwt_or_ip_key,
    enabled=rate_limit_enabled(),
    storage_uri=_rl_storage,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Prometheus /metrics (observability, Tydzień 2 mapy luk) ─────────────────
from api import _metrics as _arch_metrics  # noqa: E402


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint() -> Response:
    """Prometheus exposition. Bez auth — typowo skrobane wewnętrznie przez Prom/Grafana.
    Gdy `prometheus_client` nie jest zainstalowane → 503 (nie 500, żeby probe wiedział)."""
    if not _arch_metrics.is_available():
        return Response(
            content="prometheus_client not installed",
            status_code=503,
            media_type="text/plain",
        )
    return Response(content=_arch_metrics.render(), media_type=_arch_metrics.CONTENT_TYPE_LATEST)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Nieobsłużone wyjątki: log + Sentry, klient dostaje generyczny 500 (bez stacktrace)."""
    ctx = _http_obs_context(request)
    logger.error(
        "Unhandled exception: %s",
        type(exc).__name__,
        exc_info=exc,
        extra=ctx,
    )
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in ctx.items():
                scope.set_tag(key, value)
            sentry_sdk.capture_exception(exc)
    except ImportError:
        pass

    return JSONResponse(
        status_code=500,
        content={"detail": "Wewnętrzny błąd serwera."},
    )


app.include_router(meta_router)
if personal_router:
    app.include_router(personal_router)
if integrations_router:
    app.include_router(integrations_router)
if auth_router:
    app.include_router(auth_router)
if voice_router:
    app.include_router(voice_router)
if attachment_router:
    app.include_router(attachment_router)
if account_router:
    app.include_router(account_router)
if demo_router:
    app.include_router(demo_router)
if feedback_router:
    app.include_router(feedback_router)

# ── Dwa Tryby (spec v1.0): osobisty (ten program) + biznesowy (business_fa2) ──
# Mount sub-aplikacji `Freedom Architect 2.0` pod prefiksem /business. Lazy
# import + fail-soft: jeśli zależności biznesowe (np. shared.utils.cache,
# Redis) nie są obecne, osobisty tryb dalej działa.
try:
    from business_fa2.api.main import app as _business_app  # noqa: WPS433
    app.mount("/business", _business_app, name="freedom_architect_2_business")
    _editions_available = ("personal", "business")
except Exception as _biz_err:  # noqa: BLE001
    logger.warning("Tryb biznesowy niedostępny (business_fa2): %s", _biz_err)
    _editions_available = ("personal",)


@app.get("/edition", tags=["meta"])
async def _editions() -> dict[str, object]:
    """Spec v1.0 §3: przełącznik między trybami dostępny w każdej chwili."""
    from api.settings import demo_config_public

    out: dict[str, object] = {
        "current": "personal",
        "available": list(_editions_available),
        "business_mount": "/business" if "business" in _editions_available else None,
    }
    demo_cfg = demo_config_public()
    if demo_cfg.get("enabled"):
        out["demo"] = demo_cfg
    return out


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins(),
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _security_headers_middleware(request: Request, call_next):
    response = await architekt_http_guard(request, call_next)
    from api.settings import is_production
    if is_production():
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ==================== MODELE API ====================


class Brief(BaseModel):
    """
    Brief Patryka do Rady.

    Kategorie pochodzą ze spec v1.0 (Decyzja / Projekt / Marzenie / Schemat).
    Tryby działania zmieniają orkiestrację:
      - pelna     → 9 agentów + Syez
      - codzienny → check-in ~5 min: 4 agentów + Syez; marzenie z fallbacku (bez LLM A0); tańsze max_tokens
      - marzen    → 9 + Syez, wzmocniona faza A0 (AKSJOMAT 1)
      - schematy  → 9 + Syez, agresywniejszy Szow/Deega, wymuszone commitments

    `scale` + `budget` są zachowane jako legacy (kompatybilność z poprzednim UI).
    """

    description: str = Field(..., min_length=20, max_length=8000)
    category: Literal["decyzja", "projekt", "marzenie", "schemat"] = "decyzja"
    mode: Literal["pelna", "marzen", "schematy", "codzienny"] = "pelna"
    language: Literal["pl", "en"] = "pl"
    intention: Optional[str] = Field(default=None, max_length=400)
    extra_context: Optional[str] = Field(default=None, max_length=8000)

    # legacy
    scale: Optional[Literal["startup", "enterprise", "small"]] = None
    budget: Optional[Literal["low", "medium", "high"]] = None
    user_id: Optional[str] = None

    @field_validator("description")
    @classmethod
    def validate_idea(cls, v: str) -> str:
        if len(v.split()) < 5:
            raise ValueError("Marzenia nie rodzą się z 3 słów.")
        return v


class DebateContinueRequest(BaseModel):
    """Nowy brief zbudowany na bazie zakończonej debaty — pełny pipeline SSE."""

    previous_debate_id: int = Field(..., ge=1)
    follow_up: str = Field(..., min_length=20, max_length=2000)

    @field_validator("follow_up")
    @classmethod
    def validate_follow_words(cls, v: str) -> str:
        if len(v.split()) < 5:
            raise ValueError("Kontynuacja wymaga co najmniej pięciu słów (jak brief).")
        return v


# ==================== SSE HELPERS ====================

_CONTINUATION_EXTRA_CTX_LIMIT = 2000


def _build_continuation_extra_ctx(
    chain: list[dict],
    voices: list[dict],
    leaf_debate_id: int,
    *,
    limit: int = _CONTINUATION_EXTRA_CTX_LIMIT,
) -> str:
    """Kontekst wątku dla kontynuacji: jedna tura = format jak dotąd; wiele tur = budżet ważony."""
    if len(chain) == 1:
        parent_row = chain[0]
        synthesis_prior = (parent_row.get("synthesis_text") or "").strip()
        lines = [
            f"--- Kontynuacja wątku po debacie #{leaf_debate_id} ---",
            f"Wcześniejszy brief:\n{parent_row['brief_description'][:900]}",
            "--- Poprzednia synteza Syeza (wycinamy środek jeśli długa) ---",
            synthesis_prior[:1600] if synthesis_prior else "(brak zapisanej syntezy)",
            "--- Skrót poprzednich głosów ---",
        ]
        for v in voices:
            raw_txt = (v.get("voice_text") or "").strip()
            snippet = raw_txt[:400] + ("…" if len(raw_txt) > 400 else "")
            lines.append(f"[{v.get('agent_name', '?')}]: {snippet}")
        return "\n".join(lines)[:limit]

    voice_lines = ["--- Skrót głosów z ostatniej tury ---"]
    for v in voices:
        raw_txt = (v.get("voice_text") or "").strip()
        snippet = raw_txt[:400] + ("…" if len(raw_txt) > 400 else "")
        voice_lines.append(f"[{v.get('agent_name', '?')}]: {snippet}")
    voices_block = "\n".join(voice_lines)

    header = f"--- Kontynuacja wątku ({len(chain)} tur, liść #{leaf_debate_id}) ---"
    overhead = len(header) + 1 + len(voices_block) + 1
    turn_budget = max(0, limit - overhead)

    n = len(chain)
    weights = list(range(1, n + 1))
    weight_sum = sum(weights)

    turn_parts: list[str] = []
    for i, turn in enumerate(chain):
        share = (
            max(40, int(turn_budget * weights[i] / weight_sum))
            if turn_budget
            else 40
        )
        brief = (turn.get("brief_description") or "").strip()
        synth = (turn.get("synthesis_text") or "").strip()
        brief_cap = max(16, (share * 2) // 5)
        synth_cap = max(16, share - brief_cap - 40)
        turn_parts.append(
            f"--- Tura #{turn['id']} ---\n"
            f"Brief:\n{brief[:brief_cap]}\n"
            f"Synteza:\n{synth[:synth_cap] if synth else '(brak zapisanej syntezy)'}"
        )

    combined = "\n".join([header, *turn_parts, voices_block])
    return combined[:limit]


from api.services._sse import sse as _sse



from api.services.commitment_service import (
    MIN_COMMITMENT_RELEASE_REASON_LEN,
    create_commitment as _create_commitment_svc,
    release_commitment as _release_commitment_svc,
    complete_commitment as _complete_commitment_svc,
    delete_forbidden_payload as _delete_forbidden_payload,
)


def _council_mode_from_request(request: Request) -> str:
    """UI: nagłówek X-Council-Mode=fa2 → ramowanie biznesowe."""
    v = (request.headers.get("X-Council-Mode") or "").strip().lower()
    return "fa2" if v == "fa2" else "personal"




@app.post("/debate/stream")
@limiter.limit(debate_rate_limit())
async def debate_stream(request: Request, brief: Brief):
    """
    SSE endpoint — strumieniuje debatę Rady w czasie rzeczywistym.
    Przed startem Rady wymuszamy hard-lock `MAX_ACTIVE_PROJECTS` (AKSJOMAT 2).
    """
    if not RADA_AVAILABLE:
        async def fallback():
            yield _sse("debate_start", {"agents": [], "synthesizer": "unavailable"})
            yield _sse("synthesis_done", {"full_text": "Rada niedostępna — brak pakietu agents/"})
            yield _sse(
                "debate_done",
                {
                    "debate_id": None,
                    "agent_count": 0,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        return StreamingResponse(fallback(), media_type="text/event-stream")

    await _ensure_hard_budget_or_raise()

    if DB_AVAILABLE:
        from api.services.demo_guard import ensure_demo_can_start_debate
        from db.backend import acquire_http_db
        from db.connection import DB_PATH as _DB
        from db.tenant import current_tenant_id as _tid

        async with acquire_http_db(_DB) as db:
            await ensure_demo_can_start_debate(db, _tid(), brief)

    if brief.category == "projekt" and CORE_AVAILABLE and DB_AVAILABLE:
        from db.backend import acquire_http_db
        from db.connection import DB_PATH as _DB

        async with acquire_http_db(_DB) as db:
            await _enforce_active_project_limit_for_brief(brief, db)

    cm = _council_mode_from_request(request)
    return StreamingResponse(
        _stream_debate(brief, council_mode=cm),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/debate/continue/stream")
@limiter.limit(debate_rate_limit())
async def debate_continue_stream(request: Request, payload: DebateContinueRequest):
    """
    Kontynuacja wątku: wczytuje metadane i głosy poprzedniej debaty, składa
    `follow_up` + kontekst do `Brief`, puszcza ten sam strumień SSE co `/debate/stream`.
    """
    if not RADA_AVAILABLE:
        async def fallback():
            yield _sse("debate_start", {"agents": [], "synthesizer": "unavailable"})
            yield _sse("synthesis_done", {"full_text": "Rada niedostępna — brak pakietu agents/"})
            yield _sse(
                "debate_done",
                {
                    "debate_id": None,
                    "agent_count": 0,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        return StreamingResponse(fallback(), media_type="text/event-stream")

    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna — brak kontekstu kontynuacji")

    await _ensure_hard_budget_or_raise()

    from db.backend import acquire_http_db
    from db.connection import DB_PATH as _DB

    async with acquire_http_db(_DB) as db:
        chain = await repo.list_debate_chain(
            db, payload.previous_debate_id, max_turns=4
        )
        if not chain:
            raise HTTPException(status_code=404, detail="Debata źródłowa nie istnieje")
        parent_row = await repo.get_debate_row(db, payload.previous_debate_id)
        if not parent_row:
            raise HTTPException(status_code=404, detail="Debata źródłowa nie istnieje")
        voices = await repo.list_voices_for_debate(db, payload.previous_debate_id)

    extra_ctx = _build_continuation_extra_ctx(
        chain, voices, payload.previous_debate_id
    )

    brief = Brief(
        description=payload.follow_up.strip(),
        category=parent_row["category"],  # type: ignore[arg-type]
        mode=parent_row["mode"],  # type: ignore[arg-type]
        intention=parent_row.get("intention"),
        extra_context=extra_ctx,
    )

    if DB_AVAILABLE:
        from api.services.demo_guard import ensure_demo_can_start_debate
        from db.backend import acquire_http_db
        from db.connection import DB_PATH as _DB
        from db.tenant import current_tenant_id as _tid

        async with acquire_http_db(_DB) as db:
            await ensure_demo_can_start_debate(
                db, _tid(), brief, is_continuation=True
            )

    if brief.category == "projekt" and CORE_AVAILABLE and DB_AVAILABLE:
        async with acquire_http_db(_DB) as db:
            await _enforce_active_project_limit_for_brief(brief, db)

    cm = _council_mode_from_request(request)
    return StreamingResponse(
        _stream_debate(
            brief,
            continuation_parent_id=payload.previous_debate_id,
            council_mode=cm,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/history")
async def debate_history(
    limit: int = 40,
    q: Optional[str] = None,
    db=Depends(get_db),
):
    """Lista ostatnich debat (SQLite) — opcjonalnie `q`: wyszukiwanie po treści (brief, synteza, głosy)."""
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    lim = max(1, min(limit, 200))
    needle = (q or "").strip()[:500] or None
    rows = await repo.list_debates_recent(db, limit=lim, query=needle)
    # Wzbogać każdą debatę o root_debate_id — frontend grupuje sidebar po wątkach
    # niezależnie od tego, czy rodzic mieści się w aktualnym limicie /history.
    ids = [int(r["id"]) for r in rows if r.get("id") is not None]
    roots = await repo.resolve_root_debate_ids(db, ids) if ids else {}
    for r in rows:
        r["root_debate_id"] = roots.get(int(r["id"]), int(r["id"]))
    return {"debates": rows, "limit": lim, "query": needle or ""}


@app.get("/debate/{debate_id}")
async def debate_detail(debate_id: int, db=Depends(get_db)):
    """Pełny zapis debaty: metadane, głosy agentów, synteza, zobowiązania."""
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    row = await repo.get_debate_row(db, debate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Debata nie znaleziona")
    voices = await repo.list_voices_for_debate(db, debate_id)
    commitments = await repo.list_commitments_for_debate(db, debate_id)
    structured: Optional[dict[str, Any]] = None
    raw_json = row.get("full_synthesis_json")
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            structured = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            structured = None
    return {
        "debate": row,
        "voices": voices,
        "commitments": commitments,
        "synthesis_structured": structured,
    }


@app.get("/debate/{debate_id}/thread")
async def debate_thread(debate_id: int, db=Depends(get_db)):
    """Pełen wątek konwersacji: wszystkie tury od roota do podanego liścia.

    Każda tura = osobna debata połączona przez `parent_debate_id`. Zwracamy
    je chronologicznie (najstarsza → najnowsza), żeby UI mogło je wyświetlić
    jako konwersację: brief #1 → synteza #1 → follow_up #2 → synteza #2 → ...
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    # Limit 20 tur — zabezpieczenie przed patologicznymi łańcuchami; w praktyce
    # rzadko przekroczone, a chroni przed N+1 query attack.
    chain = await repo.list_debate_chain(db, debate_id, max_turns=20)
    if not chain:
        raise HTTPException(status_code=404, detail="Debata nie znaleziona")

    turns: list[dict[str, Any]] = []
    for entry in chain:
        turn_id = entry["id"]
        row = await repo.get_debate_row(db, turn_id)
        if not row:
            continue
        voices = await repo.list_voices_for_debate(db, turn_id)
        structured: Optional[dict[str, Any]] = None
        raw_json = row.get("full_synthesis_json")
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                structured = parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                structured = None
        turns.append({
            "debate": row,
            "voices": voices,
            "synthesis_structured": structured,
        })
    return {"turns": turns}


@app.get("/debate/{debate_id}/export.md")
async def export_debate_markdown_endpoint(debate_id: int, db=Depends(get_db)):
    """P6 — kanoniczny eksport debaty do Markdown (źródło: SQLite)."""
    if render_debate_markdown is None:
        raise HTTPException(status_code=503, detail="moduł eksportu niedostępny")
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    row = await repo.get_debate_row(db, debate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Debata nie znaleziona")
    voices = await repo.list_voices_for_debate(db, debate_id)
    commitments = await repo.list_commitments_for_debate(db, debate_id)
    structured: Optional[dict[str, Any]] = None
    raw_json = row.get("full_synthesis_json")
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            structured = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            structured = None
    body = render_debate_markdown(
        dict(row),
        voices,
        commitments,
        str(row.get("synthesis_text") or ""),
        structured,
    )
    return Response(
        content=body.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="architekt-debate-{debate_id}.md"'
        },
    )


@app.get("/debate/{debate_id}/export.pdf")
async def export_debate_pdf_endpoint(debate_id: int, db=Depends(get_db)):
    """Eksport debaty do PDF (UTF-8, ten sam kanon treści co Markdown)."""
    if render_debate_pdf_bytes is None:
        raise HTTPException(status_code=503, detail="moduł eksportu PDF niedostępny")
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    row = await repo.get_debate_row(db, debate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Debata nie znaleziona")
    voices = await repo.list_voices_for_debate(db, debate_id)
    commitments = await repo.list_commitments_for_debate(db, debate_id)
    structured: Optional[dict[str, Any]] = None
    raw_json = row.get("full_synthesis_json")
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            structured = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            structured = None
    pdf_bytes = render_debate_pdf_bytes(
        dict(row),
        voices,
        commitments,
        str(row.get("synthesis_text") or ""),
        structured,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="architekt-debate-{debate_id}.pdf"'
        },
    )


class CommitmentCreate(BaseModel):
    """Zobowiązanie Patryka spięte z debatą lub projektem (MVP v1.1 + Faza 2)."""

    text: str = Field(..., min_length=3, max_length=2000)
    debate_id: Optional[int] = None
    project_id: Optional[int] = None
    due_at: Optional[str] = Field(default=None, max_length=64)
    follow_up_at: Optional[str] = Field(default=None, max_length=64)


class CommitmentReleasePayload(BaseModel):
    """Siła cienia: nie da się „zwolnić" zobowiązania bez uzasadnienia (AKSJOMAT 2)."""

    reason: str = Field(..., min_length=MIN_COMMITMENT_RELEASE_REASON_LEN, max_length=2000)


class CommitmentCompletePayload(BaseModel):
    evidence_note: Optional[str] = Field(default=None, max_length=1200)
    evidence_url: Optional[str] = Field(default=None, max_length=500)


@app.post("/commitment")
@limiter.limit(write_rate_limit())
async def create_commitment_endpoint(request: Request, payload: CommitmentCreate, db=Depends(get_db)):
    return await _create_commitment_svc(
        text=payload.text,
        debate_id=payload.debate_id,
        project_id=payload.project_id,
        due_at=payload.due_at,
        follow_up_at=payload.follow_up_at,
        db=db,
    )


@app.get("/commitments/due")
async def commitments_due(within_hours: int = 24, db=Depends(get_db)):
    """Zobowiązania otwarte z follow_up w przeszłości lub w horyzoncie `within_hours`."""
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    wh = max(1, min(within_hours, 8760))
    items = await repo.list_commitments_due(db, within_hours=wh)
    return {"commitments": items, "within_hours": wh}


@app.post("/admin/trigger-followups")
async def admin_trigger_followups(
    authorization: Optional[str] = Header(None),
):
    """
    Idempotentny „kopniak" Fazy 2: przeterminowane follow-upy + synchronizacja projektów.

    Gdy ustawiono `ARCHITEKT_ADMIN_TOKEN`, wymagany jest nagłówek
    `Authorization: Bearer <token>` (ochrona przed publicznym otwartym adminem).
    """
    admin_tok = (os.getenv("ARCHITEKT_ADMIN_TOKEN") or "").strip()
    if admin_tok:
        auth = (authorization or "").strip()
        if not hmac.compare_digest(auth, f"Bearer {admin_tok}"):
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing Authorization bearer for admin",
            )
    await _run_phase2_startup_tasks()
    return {"ok": True}


@app.post("/commitment/{commitment_id}/release")
async def release_commitment_endpoint(
    commitment_id: int,
    payload: CommitmentReleasePayload,
    db=Depends(get_db),
):
    return await _release_commitment_svc(db, commitment_id, payload.reason)


@app.patch("/commitment/{commitment_id}/complete")
async def complete_commitment_endpoint(
    commitment_id: int,
    payload: CommitmentCompletePayload,
    db=Depends(get_db),
):
    """Odhaczenie zobowiązania + aktualizacja postępu projektu (AKSJOMAT 2)."""
    return await _complete_commitment_svc(
        db, commitment_id, payload.evidence_note, payload.evidence_url
    )


@app.delete("/commitment/{commitment_id}")
async def commitment_delete_forbidden(commitment_id: int):  # noqa: ARG001
    """AKSJOMAT 2: DELETE zablokowany - wymagane POST /release z uzasadnieniem."""
    raise HTTPException(status_code=422, detail=_delete_forbidden_payload(commitment_id))


# ── Dreams / Projects API ──────────────────────────────────────────────────


@app.get("/dreams")
async def list_dreams(limit: int = 50, db=Depends(get_db)):
    """Lista wszystkich marzeń (pełne DreamArchitecture z metadanymi).

    Jeden JOIN zastępuje poprzednie N+1 zapytania (4 query per dream → 1 total).
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    lim = max(1, min(limit, 100))
    from db.tenant import current_tenant_id as _tid
    tid = _tid()
    # Single query: dreams LEFT JOIN projects + aggregated commitment stats
    cur = await db.execute(  # allow-raw-execute: dreams not in _Repo yet; tenant_id enforced below
        """
        SELECT
            d.*,
            p.id            AS _proj_id,
            p.status        AS _proj_status,
            p.started_at    AS _proj_started_at,
            p.last_progress_at AS _proj_last_progress_at,
            COUNT(CASE WHEN c.completed_at IS NULL AND c.archived_at IS NULL THEN 1 END)
                            AS _open_commitments_count,
            MIN(CASE WHEN c.completed_at IS NULL AND c.archived_at IS NULL THEN c.follow_up_at END)
                            AS _next_follow_up_at
        FROM dreams d
        LEFT JOIN projects p ON p.dream_id = d.id AND p.tenant_id = d.tenant_id
        LEFT JOIN commitments c ON c.project_id = p.id AND c.tenant_id = d.tenant_id
        WHERE d.tenant_id = ?
        GROUP BY d.id
        ORDER BY d.created_at DESC
        LIMIT ?
        """,
        (tid, lim),
    )
    rows = await cur.fetchall()
    dreams = []
    for row in rows:
        r = dict(row)
        # Parse JSON blobs
        try:
            r["pillars"] = json.loads(r.get("pillars_json") or "[]")
            r["milestones"] = json.loads(r.get("milestones_json") or "[]")
            r["next_move"] = json.loads(r.get("next_move_json") or "{}")
            r["completion_criteria"] = json.loads(r.get("completion_criteria_json") or "[]")
            r["functionality_checklist"] = json.loads(r.get("functionality_checklist_json") or "[]")
        except json.JSONDecodeError:
            pass
        # Lift aggregated project fields; remove internal prefixed keys
        proj_id = r.pop("_proj_id", None)
        proj_status = r.pop("_proj_status", None)
        proj_started = r.pop("_proj_started_at", None)
        proj_last_progress = r.pop("_proj_last_progress_at", None)
        r["open_commitments_count"] = r.pop("_open_commitments_count", 0) or 0
        r["next_follow_up_at"] = r.pop("_next_follow_up_at", None)
        if proj_id is not None:
            from api.services.project_service import enrich_dream_with_project
            full = await repo.get_project(db, str(proj_id))
            if full:
                enrich_dream_with_project(r, full)
        dreams.append(r)
    return {"dreams": dreams}


@app.get("/dreams/{dream_id}")
async def get_dream_detail(dream_id: str, db=Depends(get_db)):
    """Pełne szczegóły marzenia: architektura, powiązane projekty, debaty."""
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    from db.tenant import current_tenant_id as _tid
    _current_tid = _tid()
    cur = await db.execute(  # allow-raw-execute: dreams not in _Repo yet; tenant_id enforced above
        "SELECT * FROM dreams WHERE id = ? AND tenant_id = ?", (dream_id, _current_tid)
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Marzenie nie znalezione")
    dream = dict(row)
    try:
        dream["pillars"] = json.loads(dream.get("pillars_json") or "[]")
        dream["milestones"] = json.loads(dream.get("milestones_json") or "[]")
        dream["next_move"] = json.loads(dream.get("next_move_json") or "{}")
        dream["completion_criteria"] = json.loads(dream.get("completion_criteria_json") or "[]")
        dream["functionality_checklist"] = json.loads(dream.get("functionality_checklist_json") or "[]")
    except json.JSONDecodeError:
        pass
    cur = await db.execute(  # allow-raw-execute: dreams not in _Repo yet; tenant_id enforced above
        "SELECT * FROM projects WHERE dream_id = ? AND tenant_id = ?", (dream_id, _current_tid)
    )
    project_row = await cur.fetchone()
    project = dict(project_row) if project_row else None
    cur = await db.execute(  # allow-raw-execute: dreams not in _Repo yet; tenant_id enforced above
        "SELECT d.* FROM debates d "
        "JOIN dream_debate_link l ON l.debate_id = d.id "
        "WHERE l.dream_id = ? AND d.tenant_id = ? "
        "ORDER BY d.created_at DESC LIMIT 10",
        (dream_id, _current_tid),
    )
    debate_rows = await cur.fetchall()
    debates = [dict(d) for d in debate_rows]
    return {"dream": dream, "project": project, "related_debates": debates}


@app.get("/projects")
async def list_projects(db=Depends(get_db)):
    """Lista aktywnych projektów + agregat completion_ratio + dni bez postępu."""
    from api.services.project_service import list_projects_with_stats
    return await list_projects_with_stats(db)


@app.get("/projects/{project_id}")
async def get_project_detail(project_id: int, db=Depends(get_db)):
    from api.services.project_service import get_project
    return await get_project(db, project_id)


@app.get("/projects/{project_id}/commitments")
async def list_project_commitments(project_id: int, db=Depends(get_db)):
    """Chronologiczna oś zobowiązań projektu (UI: CommitmentsTimeline)."""
    from api.services.project_service import get_project_commitments
    return await get_project_commitments(db, project_id)


class FunctionalityCheckPayload(BaseModel):
    evidence_url: Optional[str] = Field(default=None, max_length=500)


@app.patch("/projects/{project_id}/functionality/{item_id}")
async def check_functionality_item_endpoint(
    project_id: int,
    item_id: int,
    payload: FunctionalityCheckPayload,
    db=Depends(get_db),
):
    """Odhacza pozycję functionality_checklist (z opcjonalnym dowodem)."""
    from api.services.project_service import check_functionality_item
    return await check_functionality_item(db, project_id, item_id, payload.evidence_url)


@app.post("/projects/{project_id}/complete")
async def complete_project_endpoint(project_id: int, db=Depends(get_db)):
    """
    Oznacza projekt jako COMPLETED — TYLKO gdy `functionality_checklist` jest 100% ✓.
    Inaczej HTTP 422 z konkretną listą pozycji do zrealizowania.
    """
    from api.services.project_service import complete_project
    return await complete_project(db, project_id)


class ArchivePayload(BaseModel):
    reason: str = Field(
        ...,
        description="Świadome uzasadnienie odpuszczenia projektu (min. 50 znaków).",
    )


@app.post("/projects/{project_id}/archive")
async def archive_project_endpoint(
    project_id: int,
    payload: ArchivePayload,
    db=Depends(get_db),
):
    """
    Archiwizuje projekt jako ARCHIVED_CONSCIOUSLY z wymogiem uzasadnienia
    (AKSJOMAT 2). Bez uzasadnienia HTTP 422.
    """
    from api.services.project_service import archive_project
    return await archive_project(db, project_id, payload.reason)


# ── Faza 3: personalizacja agentów — rebuild evolution ───────────────────────


@app.post("/admin/rebuild-evolution")
async def admin_rebuild_evolution(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db),
):
    """Przebudowuje rolling notatki ewolucyjne dla wszystkich agentów."""
    admin_tok = (os.getenv("ARCHITEKT_ADMIN_TOKEN") or "").strip()
    if admin_tok:
        auth = (authorization or "").strip()
        if not hmac.compare_digest(auth, f"Bearer {admin_tok}"):
            raise HTTPException(status_code=401, detail="Invalid admin token")

    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="DB niedostępna")

    try:
        from core.agent_learner import run_full_evolution_cycle

        agent_names = [a.name for a in COUNCIL] if RADA_AVAILABLE else []
        results = await run_full_evolution_cycle(db, repo, agent_names)
        await db.commit()
        return {"ok": True, "agents_updated": list(results.keys())}
    except Exception as e:
        logger.warning("rebuild-evolution failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# Legacy endpoint — zachowany dla kompatybilności wstecznej z v3.1.
class ArchitectureResponse(BaseModel):
    status: str
    idea: str
    architecture: dict
    code_structure: dict
    deployment: dict
    monetization: dict
    agent_insights: list
    cache_hit: bool
    cached_at: Optional[str] = None
    generated_at: str


@app.post("/generate", response_model=ArchitectureResponse)
async def generate_architecture(brief: Brief):
    """
    Legacy endpoint v3.1. Zwraca uproszczoną strukturę — zachowany dla
    kompatybilności, nowe UI używa `/debate/stream`.
    """
    insights = [
        "Endpoint /generate jest legacy; nowe UI używa /debate/stream (SSE).",
        "Backend v3.2 wbija AKSJOMAT 1 (Architektura Marzenia) i AKSJOMAT 2 (Doprowadzanie Do Końca).",
    ]
    return ArchitectureResponse(
        status="legacy",
        idea=brief.description,
        architecture={"description": "Użyj POST /debate/stream"},
        code_structure={"folders": ["agents/", "core/", "db/"]},
        deployment={"recommended": "FastAPI + SQLite + Redis"},
        monetization={"model": "n/a (osobisty system Patryka)"},
        agent_insights=insights,
        cache_hit=False,
        generated_at=datetime.now(UTC).isoformat(),
    )


def _mount_single_origin_web_ui() -> None:
    """
    Punkt produktowy #9 — jedna domena API + SPA (zero Stripe w kodzie).
    Włącz: AW_SERVE_UI=1 oraz zbuduj `src/dist` (`npm run build` w src/).
    """
    if os.getenv("AW_SERVE_UI", "").strip().lower() not in ("1", "true", "yes"):
        return
    root = Path(os.getenv("AW_UI_DIST", Path(__file__).resolve().parent / "src" / "dist"))
    if not root.is_dir():
        logger.warning("AW_SERVE_UI włączone, ale brak folderu %s — pomijam SPA.", root)
        return
    idx = root / "index.html"
    if not idx.is_file():
        logger.warning("AW_SERVE_UI: brak index.html w %s — pomijam SPA.", root)
        return
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="spa_assets")

    @app.get("/", include_in_schema=False)
    async def _spa_home():
        return FileResponse(idx)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str):
        fp = (root / full_path).resolve()
        try:
            fp.relative_to(root.resolve())
        except ValueError:
            return FileResponse(idx)
        if fp.is_file():
            return FileResponse(fp)
        return FileResponse(idx)


_mount_single_origin_web_ui()
