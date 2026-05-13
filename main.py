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

# `ui/.env` (lub `AW_ENV_FILE`) — przed importami lokalnymi; wypełnia brakujące / puste zmienne.
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
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

# `datetime.UTC` jest dostępne od Pythona 3.11 — zapewniamy zgodność wsteczną do 3.10.
try:
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - tylko Python < 3.11
    UTC = timezone.utc  # type: ignore[assignment]
from pathlib import Path
from typing import Any, AsyncIterator, Literal, Optional

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
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

# Rada Nadzorcza
try:
    from agents import COUNCIL, SYNTHESIZER, afull_synthesis  # noqa: F401
    RADA_AVAILABLE = True
except ImportError:
    RADA_AVAILABLE = False
    logger.warning("⚠️ agents/ package not found – Rada disabled, using fallback")

# AKSJOMATY (core)
try:
    from core import (
        AGENT_COMPLETION_POSTSCRIPT,  # noqa: F401
        CompletionViolation,
        DreamArchitecture,
        MAX_ACTIVE_PROJECTS,
        adistill_dream,
        assert_full_functionality,
        enforce_active_project_limit,
        extract_completion_audit_from_prose,
        require_completion_audit,
        validate_archive_reason,
        validate_syez_prose_completion_audit,
    )
    from core.completion_enforcer import (
        FunctionalityItem,
        Project,
        ProjectStatus,
        classify_stale_status,
    )
    CORE_AVAILABLE = True
except ImportError as e:
    CORE_AVAILABLE = False
    logger.error("⚠️ core/ package not importable: %s", e)

try:
    from core.live_tensions import compute_live_pair_frictions
except ImportError:
    compute_live_pair_frictions = None  # type: ignore[assignment,misc]

try:
    from core.debate_export import render_debate_markdown
except ImportError:
    render_debate_markdown = None  # type: ignore[misc,assignment]

try:
    from core.debate_export_pdf import render_debate_pdf_bytes
except ImportError:
    render_debate_pdf_bytes = None  # type: ignore[misc,assignment]

# Persystencja
try:
    from db import DB_PATH, get_db, init_db, repo
    DB_AVAILABLE = True
except ImportError as e:
    DB_AVAILABLE = False
    logger.warning("⚠️ db/ package not importable: %s", e)


redis_client: Optional[aioredis.Redis] = None


def _rate_limit_enabled() -> bool:
    return os.getenv("AW_DISABLE_RATE_LIMIT", "").lower() not in ("1", "true", "yes")


def _debate_rate_limit() -> str:
    try:
        n = int(os.getenv("AW_RATE_DEBATE_PER_MINUTE", "30") or "30")
    except ValueError:
        n = 30
    n = max(5, min(n, 120))
    return f"{n}/minute"


def _cors_allow_origins() -> list[str]:
    """Produkcja: AW_CORS_ORIGINS=https://app.example.com,http://localhost:5173 — dev: *."""
    raw = (os.getenv("AW_CORS_ORIGINS") or "*").strip()
    if raw == "*":
        return ["*"]
    out = [p.strip() for p in raw.split(",") if p.strip()]
    return out if out else ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    except Exception as e:
        logger.warning(f"⚠️ Redis niedostępny ({e}) – działamy bez cache")
        redis_client = None

    # SQLite (wymagany dla AKSJOMATU 2 — projekty / functionality / audyty)
    if DB_AVAILABLE:
        try:
            await init_db()
            logger.info("✅ SQLite zainicjalizowany: %s", DB_PATH)
            await _run_phase2_startup_tasks()
        except Exception as e:
            logger.error("⚠️ init_db failed: %s", e)

    yield
    if redis_client:
        await redis_client.close()


app = FastAPI(
    title="Architekt Wolności - AI Engine v3.3",
    description=(
        "Rada Nadzorcza „Mój Świat” (9 agentów + Syez) + dwa AKSJOMATY: "
        "Architektura Marzenia + Doprowadzanie Projektów Do Końca."
    ),
    version="3.3.0",
    lifespan=lifespan,
)

limiter = Limiter(key_func=get_remote_address, enabled=_rate_limit_enabled())
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _architekt_api_key_guard(request: Request, call_next):
    """
    Gdy ustawiono ARCHITEKT_API_KEY — każde żądanie (poza ścieżkami publicznymi)
    wymaga nagłówka Authorization: Bearer <klucz>.
    """
    if request.method == "OPTIONS":
        return await call_next(request)
    key = (os.getenv("ARCHITEKT_API_KEY") or "").strip()
    if not key:
        return await call_next(request)
    path = request.url.path
    if path in (
        "/health",
        "/health/ready",
        "/openapi.json",
        "/docs",
        "/redoc",
        "/",
    ) or path.startswith("/assets/"):
        return await call_next(request)
    auth = (request.headers.get("authorization") or "").strip()
    if auth == f"Bearer {key}":
        return await call_next(request)
    return JSONResponse(
        {
            "detail": (
                "Unauthorized — ustaw nagłówek Authorization: Bearer "
                "<ARCHITEKT_API_KEY> (patrz README / docs/SECURITY_PRODUCTION.md)."
            )
        },
        status_code=401,
    )


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
    extra_context: Optional[str] = Field(default=None, max_length=2000)

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


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── Faza 2: ton Szowa / Deegi — nie „miłe przypomnienie”, lecz konfrontacja (AKSJOMAT 2) ──

SHADOW_FOLLOWUP_PREFIX_PL = (
    "[Przełamywanie Schematu] Minęły 72 godziny. Co się stało z Twoim zobowiązaniem?\n\n"
)
SHADOW_FOLLOWUP_PREFIX_EN = (
    "[Pattern Break] 72 hours have passed. What happened to your commitment?\n\n"
)

SHADOW_NO_SILENT_RELEASE_PL = (
    "Nie możesz po cichu zniknąć ze swojego własnego zobowiązania."
)
SHADOW_NO_SILENT_RELEASE_EN = (
    "You cannot quietly vanish from a commitment you made to yourself."
)

MIN_COMMITMENT_RELEASE_REASON_LEN = 30

DEEGA_STALE_AT_RISK_PL = (
    "[Przełamywanie Schematu — głos Deegi] Za długo nie było ruchu, który odhacza checklistę. "
    "Co konkretnie dziś — w jednym zdaniu — rusza pierwszą zaległą funkcjonalność?"
)
SZOW_STALE_STUCK_PL = (
    "[Przełamywanie Schematu — głos Szowa] To już nie „zajęty jestem”. To ucieczka przed domknięciem. "
    "Nazwij jedną rzecz, którą udajesz, że nie widzisz — i zrób z nią coś dziś."
)

DEEGA_STALE_AT_RISK_EN = (
    "[Pattern Break — Deega] Silence does not complete functionality. "
    "In one sentence: what moves the first unchecked item today?"
)
SZOW_STALE_STUCK_EN = (
    "[Pattern Break — Szow] This is no longer 'busy'. This is avoidance of finishing. "
    "Name one thing you pretend not to see — and act on it today."
)

AUTO_72H_SCHEMATY_BODY_PL = (
    "Tryb agresywny: masz 72 godziny, by pokazać ruch albo jawnie zmienić kurs. "
    "Zapisz dowód (nawet mały) albo nowe zobowiązanie — cisza = wzorzec."
)
AUTO_72H_SCHEMATY_BODY_EN = (
    "Aggressive mode: 72 hours to show motion or explicitly change course. "
    "Record proof (even tiny) or a new commitment — silence is the pattern."
)


def _shadow_followup_prefix(language: str) -> str:
    return SHADOW_FOLLOWUP_PREFIX_EN if language == "en" else SHADOW_FOLLOWUP_PREFIX_PL


def _auto_72h_schematy_body(language: str) -> str:
    return AUTO_72H_SCHEMATY_BODY_EN if language == "en" else AUTO_72H_SCHEMATY_BODY_PL


def _stale_nudge_text(status: str, language: str) -> str:
    if language == "en":
        return DEEGA_STALE_AT_RISK_EN if status == "at_risk" else SZOW_STALE_STUCK_EN
    return DEEGA_STALE_AT_RISK_PL if status == "at_risk" else SZOW_STALE_STUCK_PL


def _stale_status_order(status: str) -> int:
    return {
        "dreaming": 0,
        "in_progress": 1,
        "at_risk": 2,
        "stuck": 3,
    }.get(status, -1)


async def _apply_followup_nudges_db(db: Any) -> int:
    """
    Oznacza przeterminowane follow-upy jako wymagające uwagi i dokleja prefix Szowa
    do treści (tylko raz — gdy needs_attention jeszcze 0).
    """
    from datetime import timezone

    n = 0
    now = datetime.now(timezone.utc)
    for row in await repo.list_open_commitments_with_followup(db):
        if int(row.get("needs_attention") or 0) != 0:
            continue
        raw = row.get("follow_up_at")
        if not raw:
            continue
        try:
            fu = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if fu.tzinfo is None:
            fu = fu.replace(tzinfo=timezone.utc)
        if fu > now:
            continue
        cid = int(row["id"])
        lang = "en" if str(row.get("text", "")).startswith("[Pattern Break]") else "pl"
        prefix = _shadow_followup_prefix(lang)
        old_text = str(row.get("text") or "")
        new_text = old_text if old_text.startswith(prefix.strip()) else prefix + old_text
        await repo.set_commitment_needs_attention(db, cid, new_text)
        n += 1
    return n


async def _sync_stale_projects_db(db: Any) -> dict[str, int]:
    """
    AKSJOMAT 2: utrwala AT_RISK/STUCK w SQLite i tworzy zobowiązania `stale_project`
    (Deega / Szow) — bez spamu: max jedno otwarte stale_project na projekt.
    """
    if not CORE_AVAILABLE:
        return {"projects_updated": 0, "stale_commitments_created": 0}
    updates = 0
    created = 0
    rows = await repo.list_active_projects(db)
    for r in rows:
        pid = int(r["id"])
        full = await repo.get_project(db, pid)
        if not full:
            continue
        items = [FunctionalityItem(**f) for f in full["functionality"]]
        current = ProjectStatus(str(full["status"]))
        p = Project(
            id=pid,
            dream_id=str(full["dream_id"]),
            status=current,
            started_at=full.get("started_at"),
            last_progress_at=full.get("last_progress_at"),
            functionality=items,
        )
        rec = classify_stale_status(p, now=datetime.now(UTC))
        if rec in (ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED_CONSCIOUSLY):
            continue
        if rec == current:
            continue
        if _stale_status_order(rec.value) <= _stale_status_order(current.value):
            continue
        await repo.update_project_status(db, pid, rec.value)
        updates += 1
        if await repo.has_open_stale_nudge(db, pid):
            continue
        lang = "pl"
        txt = _stale_nudge_text(rec.value, lang)
        fu = (datetime.now(UTC) + timedelta(hours=72)).isoformat()
        await repo.insert_commitment(
            db,
            text=txt,
            debate_id=None,
            project_id=pid,
            due_at=None,
            follow_up_at=fu,
            trigger_type="stale_project",
            needs_attention=0,
        )
        created += 1
    return {"projects_updated": updates, "stale_commitments_created": created}


async def _run_phase2_startup_tasks() -> None:
    """Lifespan + admin: follow-upy + synchronizacja zastojów projektów."""
    if not DB_AVAILABLE:
        return
    try:
        from db.connection import aiosqlite, DB_PATH as _DB

        async with aiosqlite.connect(_DB) as db:  # type: ignore[union-attr]
            await db.execute("PRAGMA foreign_keys = ON")
            db.row_factory = aiosqlite.Row  # type: ignore[attr-defined,union-attr]
            nudged = await _apply_followup_nudges_db(db)
            sync = await _sync_stale_projects_db(db)
            await db.commit()
            logger.info(
                "Faza 2 maintenance: followup_nudges=%s stale_sync=%s",
                nudged,
                sync,
            )
    except Exception as e:
        logger.warning("Faza 2 startup maintenance failed: %s", e)


_COST_LOG_DEFAULT = Path(__file__).resolve().parent / "cost_log.jsonl"


def _sum_cost_logged_today_utc() -> float:
    """
    Agregacja dziennego kosztu z cost_log.jsonl (UTC, prefiks daty YYYY-MM-DD).
    Używane przy alarmie budżetowym v1.1 — nie blokuje debaty, tylko informuje SSE.
    """
    path = Path(os.getenv("COST_LOG_PATH", str(_COST_LOG_DEFAULT)))
    if not path.is_file():
        return 0.0
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    total = 0.0
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = str(entry.get("timestamp", ""))
                if len(ts) >= 10 and ts[:10] == day:
                    total += float(entry.get("cost_usd", 0) or 0)
    except OSError as e:
        logger.warning("cost log read failed: %s", e)
    return round(total, 6)


def _maybe_budget_warning_sse() -> Optional[str]:
    raw = os.getenv("DAILY_BUDGET_USD")
    if not raw:
        return None
    try:
        ceiling = float(raw)
    except ValueError:
        return None
    spent = _sum_cost_logged_today_utc()
    if spent >= ceiling:
        return _sse(
            "budget_warning",
            {
                "spent_usd": spent,
                "ceiling_usd": ceiling,
                "message": (
                    "Dzienny próg kosztów LLM został osiągnięty lub przekroczony "
                    "(zmienna DAILY_BUDGET_USD). Rada nadal działa — świadomy wybór."
                ),
            },
        )
    return None


def _extract_json_block(text: str) -> Optional[str]:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return t[start : end + 1]


# ==================== HARD LOCK — limit aktywnych projektów ====================


async def _enforce_active_project_limit_for_brief(brief: Brief, db: Any) -> None:
    """
    AKSJOMAT 2: Reguła „Najpierw kończ”.
    Sprawdza tylko przy `category=projekt`. Inne kategorie nie liczą się
    do limitu (marzenie/decyzja/schemat to rozmowy, nie zobowiązania).
    """
    if not (CORE_AVAILABLE and DB_AVAILABLE):
        return
    rows = await repo.list_active_projects(db)
    projects = [
        Project(
            id=int(r["id"]),
            dream_id=str(r["dream_id"]),
            status=ProjectStatus(r["status"]),
            started_at=r.get("started_at"),
            last_progress_at=r.get("last_progress_at"),
        )
        for r in rows
    ]
    try:
        enforce_active_project_limit(projects, attempting_new_project=True)
    except CompletionViolation as cv:
        raise HTTPException(status_code=409, detail=cv.to_payload()) from cv


# ==================== FAZA A0 — Architektura Marzenia ====================


_DAILY_QUESTIONS_PL: tuple[str, ...] = (
    "Co jest dziś najmniejszym krokiem, który przybliża Cię do tego, czego naprawdę chcesz?",
    "Czego unikasz nazwanie na głos — i jak jednym zdaniem byś to nazwał?",
    "Kim jesteś, gdy nikt nie patrzy — i czego ten moment Cię uczy?",
    "Co byś zrobił jutro, gdybyś nie bał się rozczarować nikogo?",
    "Jaki sygnał z ciała najbardziej Ci teraz ufa?",
    "Czego potrzebujesz od siebie dziś bardziej niż od innych?",
    "Co jest jedyną rzeczą do odhaczenia w najbliższej godzinie?",
)
_DAILY_QUESTIONS_EN: tuple[str, ...] = (
    "What is the smallest step today that moves you toward what you actually want?",
    "What are you avoiding naming out loud — and how would you name it in one sentence?",
    "Who are you when no one is watching — and what does that teach you?",
    "What would you do tomorrow if you weren't afraid to disappoint anyone?",
    "Which signal from your body do you trust most right now?",
    "What do you need from yourself today more than from anyone else?",
    "What is the one thing to tick off within the next hour?",
)


def _daily_checkin_question(language: str) -> str:
    i = date.today().toordinal() % len(_DAILY_QUESTIONS_PL)
    return _DAILY_QUESTIONS_EN[i] if language == "en" else _DAILY_QUESTIONS_PL[i]


def _mode_decorator_for_dream(mode: str, language: str = "pl") -> str:
    """
    Dodaje krótkie wzmocnienie do briefu przed destylacją marzenia, zależnie
    od trybu (AKSJOMAT 1 — tryb Marzeń = pełna ekspansja przed kompresją).

    Tryb codzienny: check-in ~5 min — bez pełnej debaty; krótkie głosy agentów.
    """
    if mode == "codzienny":
        q = _daily_checkin_question(language)
        if language == "en":
            return (
                "\n\n[DAILY MODE — ~5 minute check-in, NOT a full Council debate]\n"
                "Each agent: max 2 sentences; concrete, warm, no preamble.\n"
                "Focus on today's anchor question:\n"
                f"→ {q}\n"
            )
        return (
            "\n\n[Tryb codzienny — check-in ~5 min, to nie pełna debata Rady]\n"
            "Każdy agent: maks. 2 zdania; konkret, życzliwość, bez wstępów.\n"
            "Oś dzisiejszego pytania:\n"
            f"→ {q}\n"
        )
    if mode == "marzen":
        return (
            "\n\n[Tryb Marzeń] Najpierw pełna ekspansja wizji — NIE redukuj do realizmu, "
            "póki nie nazwiesz pełnej wersji."
        )
    if mode == "schematy":
        if language == "en":
            return (
                "\n\n[Pattern-Breaking Mode] Under the brief, find the abandonment or escape "
                "pattern — name the dream it hides.\n"
                "MANDATORY OUTPUT: end your voice with exactly one sentence starting with "
                "\"Today I will...\" that the user can say aloud or write down right now. "
                "No abstractions — one concrete action ≤60 minutes."
            )
        return (
            "\n\n[Tryb Przełamywania Schematów] Pod briefem szukaj wzorca porzucania "
            "lub ucieczki — nazwij marzenie, które ten schemat zasłania.\n"
            "OBOWIĄZKOWY OUTPUT: zakończ swój głos dokładnie jednym zdaniem zaczynającym się "
            "od \"Dziś zrobię...\" które użytkownik może powiedzieć głośno lub zapisać teraz. "
            "Żadnych abstrakcji — jedna konkretna akcja ≤60 minut."
        )
    return ""


def _build_council_context(brief: Brief) -> str:
    parts = [f"Brief Patryka ({brief.category}, tryb={brief.mode}): {brief.description}"]
    if brief.intention:
        parts.append(f"Intencja: {brief.intention}")
    if brief.extra_context:
        parts.append(f"Dodatkowy kontekst: {brief.extra_context}")
    if brief.scale or brief.budget:
        parts.append(
            f"(legacy) Skala: {brief.scale or '—'} | Budżet: {brief.budget or '—'}"
        )
    return "\n".join(parts)


def _agent_evolution_enabled() -> bool:
    """P5: rolling notatki per agent — wyłącz `AW_AGENT_EVOLUTION=0` (np. testy / prywatność)."""
    v = (os.getenv("AW_AGENT_EVOLUTION") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


# ==================== ORKIESTRACJA SSE ====================


# Lista agentów w trybie codziennym (4–5 + Syez). Wybór ma sens: logika (Kogit),
# emocja (Emojy), ciało (Smaty), meta-perspektywa (Obver) — pokrywa 4 osie spec.
_LIGHT_MODE_AGENTS: tuple[str, ...] = ("Kogit", "Emojy", "Smaty", "Obver")


def _select_council_for_mode(mode: str) -> list[Any]:
    if not RADA_AVAILABLE:
        return []
    if mode == "codzienny":
        return [a for a in COUNCIL if a.name in _LIGHT_MODE_AGENTS]
    return list(COUNCIL)


async def _stream_debate(
    brief: Brief,
    *,
    continuation_parent_id: Optional[int] = None,
) -> AsyncIterator[str]:
    """
    Generator SSE: A0 (Architektura Marzenia) → 9 agentów → Syez (z walidacją
    completion_audit) → zapis do DB.

    Zdarzenia:
      dream_architecture     – szkielet marzenia (AKSJOMAT 1)
      project_state          – aktualny stan projektu marzenia (AKSJOMAT 2)
      debate_start           – metadane debaty (+ continuation_parent_id przy kontynuacji)
      agent_start / chunk / done
      live_tensions          – heurystyka par agentów przed syntezą (napięcia leksykalne)
      synthesis_start / chunk / done
      synthesis_structured   – wyłącznie gdy synteza zawierała parsowalny JSON (legacy)
      completion_audit_violation – brak audytu po re-prompcie Syeza
      budget_warning          – próg DAILY_BUDGET_USD przekroczony (cost_log.jsonl)
      stream_error            – nieobsłużony wyjątek (graceful koniec, bez retry)
      debate_done             – koniec (z debate_id po zapisie SQLite)
    """
    try:
        async for evt in _stream_debate_inner(brief, continuation_parent_id):
            yield evt
    except Exception as e:
        logger.exception("_stream_debate crashed: %s", e)
        yield _sse(
            "stream_error",
            {
                "message": "Strumień debaty pękł — sprawdź logi serwera.",
                "error": str(e)[:300],
            },
        )
        yield _sse(
            "debate_done",
            {
                "debate_id": None,
                "agent_count": 0,
                "synthesizer": SYNTHESIZER.name if RADA_AVAILABLE else None,
                "timestamp": datetime.now(UTC).isoformat(),
                "error": True,
            },
        )


async def _stream_debate_inner(
    brief: Brief,
    continuation_parent_id: Optional[int],
) -> AsyncIterator[str]:
    """Właściwa orkiestracja — wywoływana zawsze przez `_stream_debate` w safety-net."""
    council = _select_council_for_mode(brief.mode)
    council_names = [a.name for a in council]
    raw_brief = _build_council_context(brief) + _mode_decorator_for_dream(
        brief.mode, brief.language
    )
    _cost_start = _sum_cost_logged_today_utc()

    # ── A0: Architektura Marzenia ──────────────────────────────────────────
    dream: Optional[Any] = None
    project_id: Optional[int] = None
    if CORE_AVAILABLE:
        try:
            # codzienny: bez LLM destylacji — jedna oszczędna ścieżka kosztowa (~1 wywołanie Sonnet mniej).
            if brief.mode == "codzienny":
                from core.dream_architect import _fallback_dream

                dream = _fallback_dream(raw_brief, language=brief.language)
            else:
                dream = await adistill_dream(raw_brief, language=brief.language)
            yield _sse(
                "dream_architecture",
                {
                    "dream_id": dream.dream_id,
                    "core_dream": dream.core_dream,
                    "value_anchor": dream.value_anchor,
                    "pillars": dream.pillars,
                    "milestones": [m.model_dump() for m in dream.milestones],
                    "next_move": dream.next_move.model_dump(),
                    "completion_criteria": dream.completion_criteria,
                    "functionality_checklist": dream.functionality_checklist,
                },
            )
        except Exception as e:
            logger.warning("A0 dream distillation failed: %s", e)
            yield _sse("dream_architecture_error", {"error": str(e)})

    # Zapis marzenia + projektu (tylko gdy mamy DB)
    debate_id: Optional[int] = None
    if DB_AVAILABLE and dream is not None:
        try:
            # otwieramy własne połączenie, bo to nie endpoint z Depends
            from db.connection import aiosqlite, DB_PATH as _DB
            async with aiosqlite.connect(_DB) as db:  # type: ignore[union-attr]
                await db.execute("PRAGMA foreign_keys = ON")
                db.row_factory = aiosqlite.Row  # type: ignore[attr-defined,union-attr]
                # Insert dream
                await repo.insert_dream(db, dream)
                # Projekt (architektura funkcjonalna) tworzymy ZAWSZE — AKSJOMAT 2
                project_id = await repo.ensure_project_for_dream(
                    db, dream.dream_id, dream.functionality_checklist
                )
                debate_id = await repo.insert_debate(
                    db,
                    category=brief.category,
                    mode=brief.mode,
                    brief_description=brief.description,
                    intention=brief.intention,
                    extra_context=brief.extra_context,
                    dream_id=dream.dream_id,
                    parent_debate_id=continuation_parent_id,
                )
                await repo.link_dream_debate(db, dream.dream_id, debate_id)
                await db.commit()

                if project_id is not None:
                    proj_row = await repo.get_project(db, project_id)
                    yield _sse("project_state", proj_row or {})
        except Exception as e:
            logger.warning("Persistence A0 step failed: %s", e)

    # ── Faza 1: głosy Rady ─────────────────────────────────────────────────
    budget_evt = _maybe_budget_warning_sse()
    if budget_evt:
        yield budget_evt

    yield _sse(
        "debate_start",
        {
            "agents": council_names,
            "synthesizer": SYNTHESIZER.name if RADA_AVAILABLE else None,
            "context_preview": raw_brief[:120],
            "mode": brief.mode,
            "category": brief.category,
            "dream_id": dream.dream_id if dream is not None else None,
            "continuation_parent_id": continuation_parent_id,
        },
    )

    if not council:
        # Tryb fallback gdy agents/ nie załadowane
        yield _sse(
            "synthesis_done",
            {"full_text": "Rada niedostępna — brak pakietu agents/"},
        )
        yield _sse(
            "debate_done",
            {
                "debate_id": debate_id,
                "agent_count": 0,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        return

    agent_queues: dict[str, asyncio.Queue] = {a.name: asyncio.Queue() for a in council}
    full_voices: dict[str, str] = {}

    evolution_by_agent: dict[str, str] = {}
    if DB_AVAILABLE and _agent_evolution_enabled():
        try:
            from db.connection import aiosqlite, DB_PATH as _DB

            async with aiosqlite.connect(_DB) as db:  # type: ignore[union-attr]
                await db.execute("PRAGMA foreign_keys = ON")
                db.row_factory = aiosqlite.Row  # type: ignore[attr-defined,union-attr]
                evolution_by_agent = await repo.list_agent_evolution(db)
        except Exception as e:
            logger.warning("agent evolution load failed: %s", e)

    lang = brief.language

    async def run_agent(agent, queue: asyncio.Queue):
        try:
            evo = evolution_by_agent.get(agent.name) if evolution_by_agent else None
            response = await agent.acontribute(
                raw_brief,
                dream=dream,
                language=lang,
                debate_mode=brief.mode,
                evolution_note=(evo.strip() if evo and evo.strip() else None),
            )
            words = response.split()
            buf: list[str] = []
            for w in words:
                buf.append(w)
                if len(buf) >= 4:
                    await queue.put((" ".join(buf) + " ", False))
                    buf = []
                    await asyncio.sleep(0.03)
            if buf:
                await queue.put((" ".join(buf), False))
            await queue.put((response, True))
        except Exception as e:
            await queue.put((f"[błąd: {e}]", True))

    for a in council:
        yield _sse("agent_start", {"agent": a.name})

    tasks = [asyncio.create_task(run_agent(a, agent_queues[a.name])) for a in council]
    done_agents: set[str] = set()
    while len(done_agents) < len(council):
        for a in council:
            if a.name in done_agents:
                continue
            q = agent_queues[a.name]
            try:
                text, is_final = q.get_nowait()
                if is_final:
                    done_agents.add(a.name)
                    full_voices[a.name] = text
                    yield _sse("agent_done", {"agent": a.name, "full_text": text})
                else:
                    yield _sse("agent_chunk", {"agent": a.name, "chunk": text})
            except asyncio.QueueEmpty:
                pass
        await asyncio.sleep(0.01)
    await asyncio.gather(*tasks)

    pairs: list[dict[str, Any]] = []
    if compute_live_pair_frictions is not None:
        try:
            pairs = compute_live_pair_frictions(council_names, full_voices)
        except Exception as e:
            logger.warning("live_tensions compute failed: %s", e)
    yield _sse("live_tensions", {"pairs": pairs})

    # ── Faza 2: Syez (z wymuszeniem completion_audit) ──────────────────────
    yield _sse(
        "synthesis_start",
        {"synthesizer": SYNTHESIZER.name},
    )

    bundle = "\n\n".join(f"[{name}]\n{voice}" for name, voice in full_voices.items())
    syez_payload = _build_syez_payload(raw_brief, bundle, dream, brief, live_pairs=pairs)

    try:
        synthesis = await SYNTHESIZER.acontribute(syez_payload, dream=dream, language=lang)
    except Exception as e:
        synthesis = f"[błąd syntezy: {e}]" if lang == "pl" else f"[synthesis error: {e}]"

    # Stream syntezy tekstowej
    for chunk in _chunk_words(synthesis, 5):
        yield _sse("synthesis_chunk", {"chunk": chunk})
        await asyncio.sleep(0.025)
    yield _sse("synthesis_done", {"full_text": synthesis})

    synthesis_final = synthesis
    parsed_final: Optional[dict[str, Any]] = _try_parse_synthesis_json(synthesis_final)

    audit_violation_payload: Optional[dict[str, Any]] = None
    audit_for_db: Optional[dict[str, Any]] = None

    if CORE_AVAILABLE and not (
        synthesis_final.startswith("[błąd syntezy")
        or synthesis_final.startswith("[synthesis error")
    ):
        try:
            if parsed_final is not None and isinstance(
                parsed_final.get("completion_audit"), dict
            ):
                audit_for_db = require_completion_audit(parsed_final)
            else:
                validate_syez_prose_completion_audit(synthesis_final)
                audit_for_db = extract_completion_audit_from_prose(synthesis_final)

            if DB_AVAILABLE and project_id is not None and debate_id is not None:
                from db.connection import aiosqlite, DB_PATH as _DB
                async with aiosqlite.connect(_DB) as db:  # type: ignore[union-attr]
                    await repo.save_completion_audit(db, project_id, debate_id, audit_for_db)
                    await db.commit()

            if parsed_final is not None:
                yield _sse("synthesis_structured", parsed_final)

        except CompletionViolation as cv:
            logger.warning("Syez audit violation, re-prompting: %s", cv)
            audit_violation_payload = cv.to_payload()
            if lang == "en":
                fix_prompt = (
                    "The previous synthesis does not satisfy AXIOM 2 (completion audit).\n"
                    "Rewrite IT ALL as PURE ENGLISH PROSE — no JSON; the only "
                    "permitted code block is ```mermaid … ``` (agent relation diagram).\n"
                    "Weave clearly three things: what remains in the functionality "
                    "checklist, what blocks the first outstanding item, and the "
                    "smallest concrete move (≈60 minutes).\n\n"
                    f"Previous version:\n---\n{synthesis_final}\n---"
                )
            else:
                fix_prompt = (
                    "Poprzednia synteza nie spełnia AKSJOMATU 2 (audyt domknięcia).\n"
                    "Przepisz CAŁOŚĆ jako CZYSTĄ POLSKĄ PROZĘ — bez JSON-a; jedyny "
                    "dozwolony blok kodu to ```mermaid … ``` (diagram relacji agentów).\n"
                    "Wpleć wyraźnie trzy rzeczy: co zostało z checklisty funkcjonalności, "
                    "co blokuje pierwszą zaległą pozycję, oraz najmniejszy konkretny ruch "
                    "(około 60 minut).\n\n"
                    f"Poprzednia wersja:\n---\n{synthesis_final}\n---"
                )
            try:
                fixed = await SYNTHESIZER.acontribute(
                    fix_prompt, dream=dream, language=lang, debate_mode=brief.mode
                )
                synthesis_final = fixed
                parsed_fix = _try_parse_synthesis_json(fixed)
                if parsed_fix is not None and isinstance(
                    parsed_fix.get("completion_audit"), dict
                ):
                    audit_for_db = require_completion_audit(parsed_fix)
                    parsed_final = parsed_fix
                else:
                    validate_syez_prose_completion_audit(fixed)
                    audit_for_db = extract_completion_audit_from_prose(fixed)
                    parsed_final = parsed_fix

                if DB_AVAILABLE and project_id is not None and debate_id is not None:
                    from db.connection import aiosqlite, DB_PATH as _DB
                    async with aiosqlite.connect(_DB) as db:  # type: ignore[union-attr]
                        await repo.save_completion_audit(db, project_id, debate_id, audit_for_db)
                        await db.commit()

                if parsed_final is not None:
                    yield _sse("synthesis_structured", parsed_final)
                audit_violation_payload = None
            except CompletionViolation as cv2:
                audit_violation_payload = cv2.to_payload()
            except Exception as e:
                logger.warning("Re-prompt audit failed: %s", e)

    if audit_violation_payload is not None:
        yield _sse("completion_audit_violation", audit_violation_payload)

    # Zapis pełnej syntezy + głosów
    if DB_AVAILABLE and debate_id is not None:
        try:
            from db.connection import aiosqlite, DB_PATH as _DB
            async with aiosqlite.connect(_DB) as db:  # type: ignore[union-attr]
                await db.execute("PRAGMA foreign_keys = ON")
                for name, voice in full_voices.items():
                    await repo.save_voice(db, debate_id, name, voice)
                if _agent_evolution_enabled():
                    for name, voice in full_voices.items():
                        await repo.merge_agent_evolution_snippet(db, name, voice)
                await repo.save_synthesis(db, debate_id, synthesis_final, parsed_final)
                await db.commit()
        except Exception as e:
            logger.warning("Persistence synthesis step failed: %s", e)

    # Faza 2 / AKSJOMAT 2: tryb `schematy` — automatyczne zobowiązanie z follow-up 72h (ton przygotowawczy; prefix Szowa dokleja maintenance po terminie).
    if (
        DB_AVAILABLE
        and debate_id is not None
        and brief.mode == "schematy"
        and project_id is not None
    ):
        try:
            from db.connection import aiosqlite, DB_PATH as _DB

            fu = (datetime.now(UTC) + timedelta(hours=72)).isoformat()
            body = _auto_72h_schematy_body(brief.language)
            async with aiosqlite.connect(_DB) as db:  # type: ignore[union-attr]
                await db.execute("PRAGMA foreign_keys = ON")
                cid = await repo.insert_commitment(
                    db,
                    text=body,
                    debate_id=debate_id,
                    project_id=project_id,
                    follow_up_at=fu,
                    trigger_type="auto_72h",
                )
                await repo.touch_project_last_progress(db, project_id)
                await db.commit()
            yield _sse(
                "commitment_created",
                {
                    "id": cid,
                    "debate_id": debate_id,
                    "project_id": project_id,
                    "follow_up_at": fu,
                    "trigger_type": "auto_72h",
                    "text": body,
                },
            )
        except Exception as e:
            logger.warning("auto 72h schematy commitment failed: %s", e)

    _debate_cost = round(_sum_cost_logged_today_utc() - _cost_start, 6)
    yield _sse(
        "debate_done",
        {
            "debate_id": debate_id,
            "agent_count": len(council),
            "synthesizer": SYNTHESIZER.name,
            "timestamp": datetime.now(UTC).isoformat(),
            "dream_id": dream.dream_id if dream is not None else None,
            "project_id": project_id,
            "continuation_parent_id": continuation_parent_id,
            "cost_usd": _debate_cost,
        },
    )


def _chunk_words(text: str, group: int = 5) -> AsyncIterator[str]:  # type: ignore[override]
    """Pomocniczy generator dzielący tekst na grupy słów (do streamingu)."""
    words = (text or "").split()
    buf: list[str] = []
    out: list[str] = []
    for w in words:
        buf.append(w)
        if len(buf) >= group:
            out.append(" ".join(buf) + " ")
            buf = []
    if buf:
        out.append(" ".join(buf))
    # zwracamy zwykłą listę — nasz konsument iteruje synchronicznie wewnątrz async gen
    return out  # type: ignore[return-value]


def _build_syez_payload(
    raw_brief: str,
    voices_bundle: str,
    dream: Optional[Any],
    brief: Brief,
    *,
    live_pairs: Optional[list[dict[str, Any]]] = None,
) -> str:
    lang = brief.language
    parts: list[str] = []
    if lang == "en":
        if dream is not None:
            parts.append("[DREAM ARCHITECTURE — top-level context]\n" + dream.for_syez())
        parts.append("[Council voices before synthesis]\n" + voices_bundle)
        parts.append("[Original brief]\n" + raw_brief)
        parts.append("Debate mode: " + brief.mode + " | Category: " + brief.category)
        if live_pairs:
            lines = [
                "[Tension monitor — lexical heuristic; higher value ≈ broader topical divergence between the pair]"
            ]
            for p in live_pairs[:14]:
                lines.append(f"  • {p['a']} ↔ {p['b']}: {p['intensity']}")
            parts.append("\n".join(lines))
        if CORE_AVAILABLE:
            from core.completion_enforcer import SYEZ_AKSJOMAT2_PROSE_APPEND

            parts.append(SYEZ_AKSJOMAT2_PROSE_APPEND)
        parts.append(
            "RESPONSE FORMAT — final contract:\n"
            "• Write ONLY fluent English prose + exactly one ```mermaid … ``` block "
            "showing the network of agent relations/tensions.\n"
            "• FORBIDDEN: JSON, ```json or any ``` other than ```mermaid, "
            "structures with keys like `insights_per_agent`, `completion_audit`, code tables.\n"
            "• No markdown headers (# / ##); paragraphs and short dash lists are fine.\n"
            "• Required: an interpretation of the tension monitor (conflicts between "
            "specific Council members), the Mermaid diagram, and a section of open "
            "questions for Patryk.\n"
            "• You are the mirror of the 9 voices + the Dream Architecture — you do "
            "not add a perspective beyond what emerges from them.\n"
            "• The AXIOM 2 completion audit MUST be readable INSIDE the prose."
        )
        if brief.mode == "codzienny":
            parts.append(
                "[DAILY MODE — compact synthesis]\n"
                "Keep total length modest (~650–900 words). Agents gave short replies — "
                "mirror that density.\n"
                "Still satisfy ALL format rules including tension monitor, one compact "
                "`mermaid` diagram (≤12 nodes), four short open questions, and "
                "completion audit woven into prose."
            )
        return "\n\n".join(parts)

    if dream is not None:
        parts.append("[ARCHITEKTURA MARZENIA — kontekst nadrzędny]\n" + dream.for_syez())
    parts.append("[Głosy Rady przed syntezą]\n" + voices_bundle)
    parts.append("[Oryginalny brief]\n" + raw_brief)
    parts.append("Tryb debaty: " + brief.mode + " | Kategoria: " + brief.category)
    if live_pairs:
        lines = [
            "[Monitor napięć — heurystyka leksykalna; wyższa wartość ≈ większe rozjechanie tematów między parami]"
        ]
        for p in live_pairs[:14]:
            lines.append(f"  • {p['a']} ↔ {p['b']}: {p['intensity']}")
        parts.append("\n".join(lines))
    if CORE_AVAILABLE:
        from core.completion_enforcer import SYEZ_AKSJOMAT2_PROSE_APPEND

        parts.append(SYEZ_AKSJOMAT2_PROSE_APPEND)
    parts.append(
        "FORMAT ODPOWIEDZI — kontrakt końcowy:\n"
        "• Piszesz WYŁĄCZNIE płynną polską prozą + dokładnie jeden blok "
        "```mermaid … ``` ukazujący sieć relacji/napięć między agentami.\n"
        "• ZAKAZ: JSON, bloki ```json lub jakiekolwiek ``` poza ```mermaid, "
        "struktury z kluczami typu `insights_per_agent`, `completion_audit`, "
        "tabele kodu.\n"
        "• Nie używaj nagłówków markdown (# / ##); akapity i krótkie listy "
        "myślnikiem są dozwolone.\n"
        "• Obowiązkowo: interpretacja monitoru napięć (konflikty między "
        "konkretnymi członkami Rady), diagram Mermaid, oraz sekcja pytań "
        "otwartych do Patryka.\n"
        "• Jesteś lustrem dziewięciu głosów + Architektury Marzenia — nie dodajesz "
        "osobnej perspektywy ponad to, co z nich wynika.\n"
        "• Audyt domknięcia z protokołu AKSJOMATU 2 musi być czytelny WEWNĄTRZ prozy."
    )
    if brief.mode == "codzienny":
        parts.append(
            "[Tryb codzienny — zwarta synteza]\n"
            "Utrzymaj skromną objętość (~650–900 słów). Agenci mieli krótkie głosy — "
            "lustruj to zwięźle.\n"
            "Nadal spełnij WSZYSTKIE zasady formatu: monitor napięć, jeden zwięzły "
            "diagram `mermaid` (≤12 węzłów), cztery krótkie pytania otwarte oraz "
            "audyt domknięcia wpisany w prozę."
        )
    return "\n\n".join(parts)


def _try_parse_synthesis_json(text: str) -> Optional[dict[str, Any]]:
    block = _extract_json_block(text)
    if not block:
        return None
    try:
        data = json.loads(block)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


# ==================== ENDPOINTY ====================


@app.post("/debate/stream")
@limiter.limit(_debate_rate_limit())
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

    if brief.category == "projekt" and CORE_AVAILABLE and DB_AVAILABLE:
        from db.connection import aiosqlite, DB_PATH as _DB

        async with aiosqlite.connect(_DB) as db:  # type: ignore[union-attr]
            await db.execute("PRAGMA foreign_keys = ON")
            db.row_factory = aiosqlite.Row  # type: ignore[attr-defined,union-attr]
            await _enforce_active_project_limit_for_brief(brief, db)

    return StreamingResponse(
        _stream_debate(brief),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/debate/continue/stream")
@limiter.limit(_debate_rate_limit())
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

    from db.connection import aiosqlite, DB_PATH as _DB

    async with aiosqlite.connect(_DB) as db:  # type: ignore[union-attr]
        await db.execute("PRAGMA foreign_keys = ON")
        db.row_factory = aiosqlite.Row  # type: ignore[attr-defined,union-attr]
        parent_row = await repo.get_debate_row(db, payload.previous_debate_id)
        if not parent_row:
            raise HTTPException(status_code=404, detail="Debata źródłowa nie istnieje")
        voices = await repo.list_voices_for_debate(db, payload.previous_debate_id)

    synthesis_prior = (parent_row.get("synthesis_text") or "").strip()
    lines = [
        f"--- Kontynuacja wątku po debacie #{payload.previous_debate_id} ---",
        f"Wcześniejszy brief:\n{parent_row['brief_description'][:900]}",
        "--- Poprzednia synteza Syeza (wycinamy środek jeśli długa) ---",
        synthesis_prior[:1600] if synthesis_prior else "(brak zapisanej syntezy)",
        "--- Skrót poprzednich głosów ---",
    ]
    for v in voices:
        raw_txt = (v.get("voice_text") or "").strip()
        snippet = raw_txt[:400] + ("…" if len(raw_txt) > 400 else "")
        lines.append(f"[{v.get('agent_name', '?')}]: {snippet}")
    extra_ctx = "\n".join(lines)[:2000]

    brief = Brief(
        description=payload.follow_up.strip(),
        category=parent_row["category"],  # type: ignore[arg-type]
        mode=parent_row["mode"],  # type: ignore[arg-type]
        intention=parent_row.get("intention"),
        extra_context=extra_ctx,
    )

    if brief.category == "projekt" and CORE_AVAILABLE and DB_AVAILABLE:
        async with aiosqlite.connect(_DB) as db2:  # type: ignore[union-attr]
            await db2.execute("PRAGMA foreign_keys = ON")
            db2.row_factory = aiosqlite.Row  # type: ignore[attr-defined,union-attr]
            await _enforce_active_project_limit_for_brief(brief, db2)

    return StreamingResponse(
        _stream_debate(brief, continuation_parent_id=payload.previous_debate_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def health():
    try:
        from config.llm_providers import effective_llm_backend

        llm_b = effective_llm_backend() if CORE_AVAILABLE else "none"
    except Exception:
        llm_b = "none"
    return {
        "status": "alive",
        "council_agents": len(COUNCIL) if RADA_AVAILABLE else 0,
        "synthesizer": SYNTHESIZER.name if RADA_AVAILABLE else None,
        "version": "3.2",
        "redis": "connected" if redis_client else "disconnected",
        "rada_status": "aktywna" if RADA_AVAILABLE else "niedostępna",
        "db_status": "aktywna" if DB_AVAILABLE else "niedostępna",
        "core_status": "aktywne" if CORE_AVAILABLE else "niedostępne",
        "max_active_projects": MAX_ACTIVE_PROJECTS if CORE_AVAILABLE else None,
        "llm_backend": llm_b,
        "sse_endpoint": "POST /debate/stream",
        "sse_continue_endpoint": "POST /debate/continue/stream",
        "history_endpoint": "GET /history",
        "debate_detail_endpoint": "GET /debate/{id}",
        "commitment_endpoint": "POST /commitment",
        "ready_endpoint": "GET /health/ready",
    }


@app.get("/health/ready")
async def health_ready(db=Depends(get_db)):
    """K8s/load balancer: SQLite musi odpowiadać (init_db w lifespan)."""
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="db niedostępna")
    await db.execute("SELECT 1")
    return {"ready": True}


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
    """Siła cienia: nie da się „zwolnić” zobowiązania bez uzasadnienia (AKSJOMAT 2)."""

    reason: str = Field(..., min_length=MIN_COMMITMENT_RELEASE_REASON_LEN, max_length=2000)


class CommitmentCompletePayload(BaseModel):
    evidence_note: Optional[str] = Field(default=None, max_length=1200)
    evidence_url: Optional[str] = Field(default=None, max_length=500)


@app.post("/commitment")
async def create_commitment(payload: CommitmentCreate, db=Depends(get_db)):
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    debate_row: Optional[dict[str, Any]] = None
    if payload.debate_id is not None:
        debate_row = await repo.get_debate_row_minimal(db, int(payload.debate_id))
        if debate_row is None:
            raise HTTPException(status_code=404, detail="debata nie istnieje")

    resolved_project = payload.project_id
    dream_id = (debate_row or {}).get("dream_id")
    if resolved_project is None and dream_id:
        resolved_project = await repo.project_id_for_dream(db, str(dream_id))

    mode = str((debate_row or {}).get("mode") or "pelna")
    follow_up = payload.follow_up_at
    if mode == "schematy" and not follow_up:
        follow_up = (datetime.now(UTC) + timedelta(hours=72)).isoformat()

    new_id = await repo.insert_commitment(
        db,
        text=payload.text.strip(),
        debate_id=payload.debate_id,
        project_id=resolved_project,
        due_at=payload.due_at,
        follow_up_at=follow_up,
        trigger_type="manual",
    )
    if resolved_project is not None:
        await repo.touch_project_last_progress(db, int(resolved_project))
    await db.commit()
    return {
        "id": new_id,
        "status": "open",
        "follow_up_at": follow_up,
        "trigger_type": "manual",
        "project_id": resolved_project,
    }


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
    Idempotentny „kopniak” Fazy 2: przeterminowane follow-upy + synchronizacja projektów.

    Gdy ustawiono `ARCHITEKT_ADMIN_TOKEN`, wymagany jest nagłówek
    `Authorization: Bearer <token>` (ochrona przed publicznym otwartym adminem).
    """
    admin_tok = (os.getenv("ARCHITEKT_ADMIN_TOKEN") or "").strip()
    if admin_tok:
        auth = (authorization or "").strip()
        if auth != f"Bearer {admin_tok}":
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing Authorization bearer for admin",
            )
    await _run_phase2_startup_tasks()
    return {"ok": True}


@app.post("/commitment/{commitment_id}/release")
async def release_commitment(
    commitment_id: int,
    payload: CommitmentReleasePayload,
    db=Depends(get_db),
):
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    row = await repo.get_commitment(db, commitment_id)
    if not row:
        raise HTTPException(status_code=404, detail="nie znaleziono")
    if str(row.get("status")) != "open":
        raise HTTPException(status_code=409, detail="zobowiązanie nie jest otwarte")
    ok = await repo.release_commitment(
        db, commitment_id, reason=payload.reason.strip()
    )
    if not ok:
        raise HTTPException(status_code=409, detail="nie udało się zwolnić")
    await db.commit()
    return {"ok": True, "id": commitment_id, "status": "released"}


@app.patch("/commitment/{commitment_id}/complete")
async def complete_commitment_endpoint(
    commitment_id: int,
    payload: CommitmentCompletePayload,
    db=Depends(get_db),
):
    """Odhaczenie zobowiązania + aktualizacja postępu projektu (AKSJOMAT 2)."""
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    row = await repo.get_commitment(db, commitment_id)
    if not row:
        raise HTTPException(status_code=404, detail="nie znaleziono")
    pid = row.get("project_id")
    ok = await repo.complete_commitment(
        db,
        commitment_id,
        evidence_note=payload.evidence_note,
        evidence_url=payload.evidence_url,
    )
    if not ok:
        raise HTTPException(status_code=409, detail="nie udało się odhaczyć")
    if pid is not None:
        await repo.touch_project_last_progress(db, int(pid))
    await db.commit()
    return {"ok": True, "id": commitment_id, "status": "completed"}


@app.delete("/commitment/{commitment_id}")
async def commitment_delete_forbidden(commitment_id: int):  # noqa: ARG001
    """
    Siła cienia: HTTP DELETE jest celowo zablokowany — AKSJOMAT 2 nie pozwala
    „znikać po cichu”. Świadome zwolnienie wymaga jawnego uzasadnienia.
    """
    raise HTTPException(
        status_code=422,
        detail={
            "kind": "shadow_no_silent_release",
            "message_pl": SHADOW_NO_SILENT_RELEASE_PL,
            "message_en": SHADOW_NO_SILENT_RELEASE_EN,
            "use_endpoint": f"POST /commitment/{commitment_id}/release",
            "min_reason_chars": MIN_COMMITMENT_RELEASE_REASON_LEN,
        },
    )


# ── Dreams / Projects API ──────────────────────────────────────────────────


@app.get("/dreams")
async def list_dreams(limit: int = 50, db=Depends(get_db)):
    """Lista wszystkich marzeń (pełne DreamArchitecture z metadanymi)."""
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    lim = max(1, min(limit, 100))
    cur = await db.execute(
        "SELECT * FROM dreams ORDER BY created_at DESC LIMIT ?", (lim,)
    )
    rows = await cur.fetchall()
    dreams = []
    for row in rows:
        r = dict(row)
        try:
            r["pillars"] = json.loads(r.get("pillars_json") or "[]")
            r["milestones"] = json.loads(r.get("milestones_json") or "[]")
            r["next_move"] = json.loads(r.get("next_move_json") or "{}")
            r["completion_criteria"] = json.loads(r.get("completion_criteria_json") or "[]")
            r["functionality_checklist"] = json.loads(r.get("functionality_checklist_json") or "[]")
        except json.JSONDecodeError:
            pass
        pid = await repo.project_id_for_dream(db, str(r["id"]))
        if pid is not None:
            full = await repo.get_project(db, pid)
            if full:
                r["project"] = full
                r["open_commitments_count"] = await repo.count_open_commitments_for_project(
                    db, pid
                )
                r["next_follow_up_at"] = await repo.next_open_followup_iso(db, pid)
                if CORE_AVAILABLE:
                    items = [FunctionalityItem(**f) for f in full["functionality"]]
                    pdom = Project(
                        id=int(full["id"]),
                        dream_id=str(full["dream_id"]),
                        status=ProjectStatus(full["status"]),
                        started_at=full.get("started_at"),
                        last_progress_at=full.get("last_progress_at"),
                        functionality=items,
                    )
                    r["days_since_progress"] = pdom.days_since_progress()
        dreams.append(r)
    return {"dreams": dreams}


@app.get("/dreams/{dream_id}")
async def get_dream_detail(dream_id: str, db=Depends(get_db)):
    """Pełne szczegóły marzenia: architektura, powiązane projekty, debaty."""
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    cur = await db.execute("SELECT * FROM dreams WHERE id = ?", (dream_id,))
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
    cur = await db.execute("SELECT * FROM projects WHERE dream_id = ?", (dream_id,))
    project_row = await cur.fetchone()
    project = dict(project_row) if project_row else None
    cur = await db.execute(
        "SELECT d.* FROM debates d JOIN dream_debate_link l ON l.debate_id = d.id WHERE l.dream_id = ? ORDER BY d.created_at DESC LIMIT 10",
        (dream_id,)
    )
    debate_rows = await cur.fetchall()
    debates = [dict(d) for d in debate_rows]
    return {"dream": dream, "project": project, "related_debates": debates}


@app.get("/projects")
async def list_projects(db=Depends(get_db)):
    """Lista aktywnych projektów + agregat completion_ratio + dni bez postępu."""
    if not (CORE_AVAILABLE and DB_AVAILABLE):
        raise HTTPException(status_code=503, detail="core lub db niedostępne")
    rows = await repo.list_active_projects(db)
    out: list[dict[str, Any]] = []
    for r in rows:
        full = await repo.get_project(db, int(r["id"]))
        if not full:
            continue
        items = [FunctionalityItem(**f) for f in full["functionality"]]
        proj = Project(
            id=int(full["id"]),
            dream_id=str(full["dream_id"]),
            status=ProjectStatus(full["status"]),
            started_at=full.get("started_at"),
            last_progress_at=full.get("last_progress_at"),
            functionality=items,
        )
        out.append(
            {
                "id": proj.id,
                "dream_id": proj.dream_id,
                "core_dream": r.get("core_dream"),
                "status": proj.status.value,
                "completion_ratio": round(proj.completion_ratio(), 3),
                "days_since_progress": proj.days_since_progress(),
                "remaining": [f.description for f in proj.remaining_items()],
                "total_items": len(proj.functionality),
            }
        )
    return {"projects": out, "limit": MAX_ACTIVE_PROJECTS}


@app.get("/projects/{project_id}")
async def get_project_detail(project_id: int, db=Depends(get_db)):
    if not (CORE_AVAILABLE and DB_AVAILABLE):
        raise HTTPException(status_code=503, detail="core lub db niedostępne")
    proj = await repo.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Projekt nie znaleziony")
    return proj


@app.get("/projects/{project_id}/commitments")
async def list_project_commitments(project_id: int, db=Depends(get_db)):
    """Chronologiczna oś zobowiązań projektu (UI: CommitmentsTimeline)."""
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="baza niedostępna")
    row = await repo.get_project(db, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Projekt nie znaleziony")
    rows = await repo.list_commitments_for_project(db, project_id, limit=80)
    return {"commitments": rows}


class FunctionalityCheckPayload(BaseModel):
    evidence_url: Optional[str] = Field(default=None, max_length=500)


@app.patch("/projects/{project_id}/functionality/{item_id}")
async def check_functionality_item(
    project_id: int,
    item_id: int,
    payload: FunctionalityCheckPayload,
    db=Depends(get_db),
):
    """Odhacza pozycję functionality_checklist (z opcjonalnym dowodem)."""
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="db niedostępne")
    affected_project = await repo.mark_functionality_done(
        db, item_id, evidence_url=payload.evidence_url
    )
    if affected_project is None:
        raise HTTPException(status_code=404, detail="Pozycja nie znaleziona")
    if affected_project != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Pozycja {item_id} nie należy do projektu {project_id}",
        )
    await db.commit()
    proj = await repo.get_project(db, project_id)
    return {"ok": True, "project": proj}


@app.post("/projects/{project_id}/complete")
async def complete_project(project_id: int, db=Depends(get_db)):
    """
    Oznacza projekt jako COMPLETED — TYLKO gdy `functionality_checklist` jest 100% ✓.
    Inaczej HTTP 422 z konkretną listą pozycji do zrealizowania.
    """
    if not (CORE_AVAILABLE and DB_AVAILABLE):
        raise HTTPException(status_code=503, detail="core lub db niedostępne")
    raw = await repo.get_project(db, project_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Projekt nie znaleziony")
    items = [FunctionalityItem(**f) for f in raw["functionality"]]
    project = Project(
        id=int(raw["id"]),
        dream_id=str(raw["dream_id"]),
        status=ProjectStatus(raw["status"]),
        functionality=items,
    )
    try:
        assert_full_functionality(project)
    except CompletionViolation as cv:
        raise HTTPException(status_code=422, detail=cv.to_payload()) from cv
    await repo.update_project_status(
        db,
        project_id,
        ProjectStatus.COMPLETED.value,
        completed_at=datetime.now(UTC).isoformat(),
    )
    await db.commit()
    return {"ok": True, "status": ProjectStatus.COMPLETED.value}


class ArchivePayload(BaseModel):
    reason: str = Field(
        ...,
        description="Świadome uzasadnienie odpuszczenia projektu (min. 50 znaków).",
    )


@app.post("/projects/{project_id}/archive")
async def archive_project(
    project_id: int,
    payload: ArchivePayload,
    db=Depends(get_db),
):
    """
    Archiwizuje projekt jako ARCHIVED_CONSCIOUSLY z wymogiem uzasadnienia
    (AKSJOMAT 2). Bez uzasadnienia HTTP 422.
    """
    if not (CORE_AVAILABLE and DB_AVAILABLE):
        raise HTTPException(status_code=503, detail="core lub db niedostępne")
    try:
        reason = validate_archive_reason(payload.reason)
    except CompletionViolation as cv:
        raise HTTPException(status_code=422, detail=cv.to_payload()) from cv
    proj = await repo.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Projekt nie znaleziony")
    await repo.update_project_status(
        db,
        project_id,
        ProjectStatus.ARCHIVED_CONSCIOUSLY.value,
        archived_reason=reason,
        archived_at=datetime.now(UTC).isoformat(),
    )
    await db.commit()
    return {"ok": True, "status": ProjectStatus.ARCHIVED_CONSCIOUSLY.value}


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
    Włącz: AW_SERVE_UI=1 oraz zbuduj `ui/dist` (`npm run build` w ui/).
    """
    if os.getenv("AW_SERVE_UI", "").strip().lower() not in ("1", "true", "yes"):
        return
    root = Path(os.getenv("AW_UI_DIST", Path(__file__).resolve().parent / "ui" / "dist"))
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
