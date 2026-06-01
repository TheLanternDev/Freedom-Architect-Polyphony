"""Orkiestracja debaty Rady: A0 → agenci → Syez → zapis — generator SSE."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Optional

from api.services._types import BriefLike, PhaseCouncilResult, PhaseSynthesisResult
from agents.base_agent import _LLM_TIMEOUT_ERRORS
from config.llm_providers import LLM_TIMEOUT_WAIT_SEC

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


def _log_orchestrator_issue(
    step: str,
    exc: BaseException,
    *,
    level: str = "warning",
    debate_id: Optional[int] = None,
    project_id: Optional[int] = None,
) -> None:
    """Log operacyjny bez PII — tylko metadane (tenant, debate_id, typ błędu)."""
    from db.tenant import current_tenant_id as _tid

    extra: dict[str, Any] = {
        "orchestrator_step": step,
        "error_type": type(exc).__name__,
        "tenant_id": _tid(),
    }
    if debate_id is not None:
        extra["debate_id"] = debate_id
    if project_id is not None:
        extra["project_id"] = project_id
    msg = f"{step} failed: {type(exc).__name__}"
    if level == "error":
        logger.error(msg, exc_info=exc, extra=extra)
    else:
        logger.warning(msg, exc_info=exc, extra=extra)

try:
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[assignment]

try:
    from agents import COUNCIL, SYNTHESIZER, afull_synthesis  # noqa: F401
    RADA_AVAILABLE = True
except ImportError:
    RADA_AVAILABLE = False
    COUNCIL: list = []  # type: ignore[assignment]
    SYNTHESIZER = None  # type: ignore[assignment]

try:
    from core import (
        AGENT_COMPLETION_POSTSCRIPT,  # noqa: F401
        CompletionViolation,
        DreamArchitecture,
        extract_completion_audit_from_prose,
        require_completion_audit,
        validate_syez_prose_completion_audit,
    )
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False

try:
    from core.live_tensions import compute_live_pair_frictions
except ImportError:
    compute_live_pair_frictions = None  # type: ignore[assignment,misc]

try:
    from core.safety import safety_check as _safety_check
    _SAFETY_AVAILABLE = True
except ImportError:
    _safety_check = None  # type: ignore[assignment]
    _SAFETY_AVAILABLE = False

try:
    from db import repo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    repo = None  # type: ignore[assignment]

try:
    from core.analytics import track_fire_and_forget as _track
except ImportError:  # pragma: no cover
    async def _track(event: str, tenant_id: str, **props: Any) -> None:  # type: ignore[misc]
        pass

from api.services.budget_guard import maybe_budget_warning_sse, spent_today_usd
from api.services.completion_service import auto_72h_schematy_body
from api.services.dream_service import (
    distill_dream,
    dream_architecture_sse,
    persist_dream_and_project,
)
from api.services.mode_helpers import (
    _pending_msg,
    build_audit_fix_prompt,
    mode_decorator_for_dream,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

from api.services._sse import sse as _sse


_LIGHT_MODE_AGENTS: tuple[str, ...] = ("Kogit", "Emojy", "Smaty", "Obver")


def select_council_for_mode(mode: str) -> list[Any]:
    """Zwraca listę agentów odpowiednią dla trybu debaty."""
    if not RADA_AVAILABLE:
        return []
    if mode == "codzienny":
        return [a for a in COUNCIL if a.name in _LIGHT_MODE_AGENTS]
    return list(COUNCIL)


def build_council_context(brief: BriefLike) -> str:
    """Buduje tekstowy kontekst briefu do przekazania agentom."""
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
    """Czy ewolucja agentów jest włączona (env AW_AGENT_EVOLUTION, default=1)."""
    v = (os.getenv("AW_AGENT_EVOLUTION") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _extract_json_block(text: str) -> Optional[str]:
    """Wyciąga pierwszy kompletny blok JSON. Jedno źródło prawdy: core
    (balansowanie nawiasów). Naiwny find/rfind tylko jako ostateczny fallback,
    gdy core niedostępne — żeby uniknąć rozjazdu logiki (#2)."""
    try:
        from core.dream_architect import _extract_json_block as _core_extract
        return _core_extract(text)
    except ImportError:
        pass
    except ValueError:
        return None
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return t[start : end + 1]


def _try_parse_synthesis_json(text: str) -> Optional[dict[str, Any]]:
    """Parsuje JSON z tekstu syntezy; None jeśli brak lub niepoprawny."""
    block = _extract_json_block(text)
    if not block:
        return None
    try:
        data = json.loads(block)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def chunk_words(text: str, group: int = 5) -> list[str]:
    """Dzieli tekst na grupy słów (do streamingu SSE)."""
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
    return out


def _fa2_business_context_prefix(language: str) -> str:
    """Opcjonalny prefix kontekstu biznesowego FA2 (graceful fallback)."""
    try:
        from business_fa2.prompts.context import fa2_business_context_prefix
        return fa2_business_context_prefix(language)
    except ImportError:
        return ""


def build_syez_payload(
    raw_brief: str,
    voices_bundle: str,
    dream: Optional[Any],
    brief: BriefLike,
    *,
    live_pairs: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Składa payload dla Syeza: architektura + głosy + brief + format."""
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
            from core.completion_enforcer import SYEZ_AKSJOMAT2_PROSE_APPEND_EN
            parts.append(SYEZ_AKSJOMAT2_PROSE_APPEND_EN)
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


# ── Phase generators ────────────────────────────────────────────────────────


async def _phase_council(
    council: list[Any],
    raw_brief: str,
    dream: Optional[Any],
    brief: BriefLike,
    db: Any,
    council_mode: str,
) -> AsyncIterator[Any]:
    """Phase 1: parallel agent execution. Yields SSE strings, then a dict with full_voices."""
    agent_queues: dict[str, asyncio.Queue[tuple[str, bool]]] = {a.name: asyncio.Queue() for a in council}
    full_voices: dict[str, str] = {}

    evolution_by_agent: dict[str, str] = {}
    if db is not None and _agent_evolution_enabled():
        try:
            evolution_by_agent = await repo.list_agent_evolution(db, council_mode)
        except Exception as e:
            _log_orchestrator_issue("agent_evolution_load", e)

    lang = brief.language

    async def run_agent(agent: Any, queue: asyncio.Queue[tuple[str, bool]]) -> None:
        try:
            evo = evolution_by_agent.get(agent.name) if evolution_by_agent else None
            response = await agent.acontribute(
                raw_brief,
                dream=dream,
                language=lang,
                debate_mode=brief.mode,
                evolution_note=(evo.strip() if evo and evo.strip() else None),
                council_mode=council_mode,
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
        except _LLM_TIMEOUT_ERRORS:
            await queue.put(
                (
                    f"[timeout: agent {agent.name} przekroczył {LLM_TIMEOUT_WAIT_SEC}s]",
                    True,
                )
            )
        except Exception as e:
            await queue.put((f"[błąd: {e}]", True))

    def _is_error_voice(text: str) -> bool:
        return (
            text.startswith("[błąd")
            or text.startswith("[error")
            or text.startswith("[timeout:")
        )

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
                    if _is_error_voice(text):
                        # AKSJOMAT 1: integralność Rady. Uszkodzony głos NIE trafia
                        # do Syeza jako pełnoprawny — i degradacja jest WIDOCZNA (#3).
                        kind = "timeout" if text.startswith("[timeout:") else "error"
                        yield _sse(
                            "agent_error",
                            {"agent": a.name, "error": text, "kind": kind},
                        )
                    else:
                        full_voices[a.name] = text
                        yield _sse("agent_done", {"agent": a.name, "full_text": text})
                else:
                    yield _sse("agent_chunk", {"agent": a.name, "chunk": text})
            except asyncio.QueueEmpty:
                pass
        await asyncio.sleep(0.01)
    await asyncio.gather(*tasks)
    # Signal full_voices back via typed result
    yield PhaseCouncilResult(full_voices=full_voices)  # type: ignore[misc]


async def _attempt_completion_audit(
    synthesis: str,
    parsed: Optional[dict[str, Any]],
    dream: Optional[Any],
    brief: BriefLike,
    project_id: Optional[int],
    debate_id: Optional[int],
    db: Any,
    council_mode: str,
) -> tuple[str, Optional[dict[str, Any]], Optional[dict[str, Any]], list[str]]:
    """Waliduje completion_audit Syeza. W razie naruszenia wykonuje re-prompt.

    Returns:
        (synthesis_final, parsed_final, violation_payload, sse_events)
    """
    lang = brief.language
    synthesis_final = synthesis
    parsed_final = parsed
    events: list[str] = []

    if not CORE_AVAILABLE or (
        synthesis_final.startswith("[błąd syntezy") or synthesis_final.startswith("[synthesis error")
    ):
        return synthesis_final, parsed_final, None, events

    try:
        if parsed_final is not None and isinstance(parsed_final.get("completion_audit"), dict):
            audit_for_db = require_completion_audit(parsed_final)
        else:
            validate_syez_prose_completion_audit(synthesis_final)
            audit_for_db = extract_completion_audit_from_prose(synthesis_final)

        if db is not None and project_id is not None and debate_id is not None:
            await repo.save_completion_audit(db, project_id, debate_id, audit_for_db)
            await db.commit()

        if parsed_final is not None:
            events.append(_sse("synthesis_structured", parsed_final))

        return synthesis_final, parsed_final, None, events

    except CompletionViolation as cv:
        logger.warning("Syez audit violation, re-prompting: %s", cv)
        fix_prompt = build_audit_fix_prompt(lang, synthesis_final)
        try:
            fixed = await SYNTHESIZER.acontribute(
                fix_prompt, dream=dream, language=lang, debate_mode=brief.mode,
                council_mode=council_mode,
            )
            synthesis_final = fixed
            parsed_fix = _try_parse_synthesis_json(fixed)
            if parsed_fix is not None and isinstance(parsed_fix.get("completion_audit"), dict):
                audit_for_db = require_completion_audit(parsed_fix)
                parsed_final = parsed_fix
            else:
                validate_syez_prose_completion_audit(fixed)
                audit_for_db = extract_completion_audit_from_prose(fixed)
                parsed_final = parsed_fix

            if db is not None and project_id is not None and debate_id is not None:
                await repo.save_completion_audit(db, project_id, debate_id, audit_for_db)
                await db.commit()

            if parsed_final is not None:
                events.append(_sse("synthesis_structured", parsed_final))
            return synthesis_final, parsed_final, None, events
        except CompletionViolation as cv2:
            return synthesis_final, parsed_final, cv2.to_payload(), events
        except Exception as e:
            _log_orchestrator_issue("syez_audit_reprompt", e, debate_id=debate_id)
            return synthesis_final, parsed_final, cv.to_payload(), events


async def _phase_synthesis(
    raw_brief: str,
    full_voices: dict[str, str],
    dream: Optional[Any],
    brief: BriefLike,
    pairs: list[dict[str, Any]],
    db: Any,
    project_id: Optional[int],
    debate_id: Optional[int],
    council_mode: str,
) -> AsyncIterator[Any]:
    """Phase 2: Syez synthesis + completion audit. Yields SSE, then result dict."""
    lang = brief.language
    yield _sse("synthesis_start", {"synthesizer": SYNTHESIZER.name})

    bundle = "\n\n".join(f"[{name}]\n{voice}" for name, voice in full_voices.items())
    syez_payload = build_syez_payload(raw_brief, bundle, dream, brief, live_pairs=pairs)

    _syez_task = asyncio.create_task(
        SYNTHESIZER.acontribute(syez_payload, dream=dream, language=lang, council_mode=council_mode)
    )
    while not _syez_task.done():
        try:
            await asyncio.wait_for(asyncio.shield(_syez_task), timeout=8.0)
        except asyncio.TimeoutError:
            yield _sse("synthesis_heartbeat", {"status": "thinking"})

    try:
        synthesis = _syez_task.result()
    except Exception as e:
        synthesis = f"[błąd syntezy: {e}]" if lang == "pl" else f"[synthesis error: {e}]"

    for chunk in chunk_words(synthesis, 5):
        yield _sse("synthesis_chunk", {"chunk": chunk})
        await asyncio.sleep(0.025)
    yield _sse("synthesis_done", {"full_text": synthesis})

    # ── Completion audit (AKSJOMAT 2) ────────────────────────────────────
    parsed = _try_parse_synthesis_json(synthesis)
    synthesis_final, parsed_final, violation, audit_events = await _attempt_completion_audit(
        synthesis, parsed, dream, brief, project_id, debate_id, db, council_mode
    )
    for evt in audit_events:
        yield evt
    if violation is not None:
        yield _sse("completion_audit_violation", violation)

    # Signal results back
    yield PhaseSynthesisResult(synthesis_final=synthesis_final, parsed_final=parsed_final)  # type: ignore[misc]


async def _phase_commit_and_finalize(
    db: Any,
    debate_id: Optional[int],
    brief: BriefLike,
    full_voices: dict[str, str],
    synthesis_final: str,
    parsed_final: Optional[dict[str, Any]],
    project_id: Optional[int],
    dream: Optional[Any],
    council: list[Any],
    cost_start: float,
    continuation_parent_id: Optional[int],
    council_mode: str,
) -> AsyncIterator[str]:
    """Phase 3: persist voices/synthesis, auto-commitment, final event."""
    # ── Zapis głosów + syntezy ───────────────────────────────────────────
    if db is not None and debate_id is not None:
        try:
            for name, voice in full_voices.items():
                await repo.save_voice(db, debate_id, name, voice)
            if _agent_evolution_enabled():
                try:
                    from core.agent_learner import extract_evolution_snippet
                except ImportError:
                    extract_evolution_snippet = None  # type: ignore[assignment]
                for name, voice in full_voices.items():
                    # Kompresja zdaniowa (pierwsze + ostatnie zdanie, ~200 zn.)
                    # PRZED zapisem do repo — spójna z rebuild_evolution_for_agent.
                    # Bez tego repo.merge_agent_evolution_snippet obcinał surowy
                    # głos „twardo" na snippet_cap (380 zn.), często w połowie
                    # zdania. Repo nadal nakłada własny cap/dedup — to OK.
                    snippet = (
                        extract_evolution_snippet(name, voice)
                        if extract_evolution_snippet is not None
                        else voice
                    )
                    if snippet:
                        await repo.merge_agent_evolution_snippet(db, name, snippet, council_mode=council_mode)
            await repo.save_synthesis(db, debate_id, synthesis_final, parsed_final)
            await db.commit()
        except Exception as e:
            _log_orchestrator_issue(
                "persistence_synthesis",
                e,
                level="error",
                debate_id=debate_id,
                project_id=project_id,
            )

    # ── Auto-commitment (tryb schematy) ──────────────────────────────────
    if db is not None and debate_id is not None and brief.mode == "schematy" and project_id is not None:
        try:
            fu = (datetime.now(UTC) + timedelta(hours=72)).isoformat()
            body = auto_72h_schematy_body(brief.language)
            cid = await repo.insert_commitment(
                db, text=body, debate_id=debate_id, project_id=project_id,
                follow_up_at=fu, trigger_type="auto_72h",
            )
            await repo.touch_project_last_progress(db, project_id)
            await db.commit()
            yield _sse(
                "commitment_created",
                {
                    "id": cid, "debate_id": debate_id, "project_id": project_id,
                    "follow_up_at": fu, "trigger_type": "auto_72h", "text": body,
                },
            )
        except Exception as e:
            _log_orchestrator_issue(
                "auto_72h_commitment",
                e,
                debate_id=debate_id,
                project_id=project_id,
            )

    # ── Finał ────────────────────────────────────────────────────────────
    _debate_cost = round(spent_today_usd() - cost_start, 6)
    from db.tenant import current_tenant_id as _tid_analytics
    _t = asyncio.create_task(
        _track(
            "debate_done", _tid_analytics(),
            debate_id=debate_id, mode=brief.mode, category=brief.category,
            agent_count=len(council), cost_usd=_debate_cost,
            dream_id=dream.dream_id if dream is not None else None,
            project_id=project_id,
        )
    )
    _background_tasks.add(_t)
    _t.add_done_callback(_background_tasks.discard)
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


# ── Główny generator SSE ────────────────────────────────────────────────────


async def stream_debate(
    brief: BriefLike,
    *,
    continuation_parent_id: Optional[int] = None,
    council_mode: str = "personal",
) -> AsyncIterator[str]:
    """Generator SSE: safety-net wrapper (łapie wyjątki, emituje stream_error)."""
    try:
        async for evt in _stream_debate_inner(
            brief, continuation_parent_id, council_mode=council_mode
        ):
            yield evt
    except Exception as e:
        logger.exception("_stream_debate crashed: %s", e)
        yield _sse(
            "stream_error",
            {"message": "Strumień debaty pękł — sprawdź logi serwera.", "error": str(e)[:300]},
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
    brief: BriefLike,
    continuation_parent_id: Optional[int],
    *,
    council_mode: str = "personal",
) -> AsyncIterator[str]:
    """Właściwa orkiestracja: A0 → agenci → Syez → zapis."""

    # Wczesny sygnał do frontu + log do uvicorn: backend żyje, zaczyna pracę.
    # Bez logu nie wiadomo czy generator w ogóle startuje (uvicorn loguje
    # tylko HTTP status, nie ciało SSE).
    logger.info(
        "_stream_debate_inner: START (mode=%s, council_mode=%s, lang=%s, brief_len=%d)",
        brief.mode, council_mode, brief.language, len(brief.description or ""),
    )
    yield _sse(
        "debate_pending",
        {
            "status": "initializing",
            "council_mode": council_mode,
            "msg": _pending_msg(council_mode, brief.language),
        },
    )

    # ── Safety check ─────────────────────────────────────────────────────────
    if _SAFETY_AVAILABLE and _safety_check is not None:
        _combined = " ".join(filter(None, [brief.description, brief.intention, brief.extra_context]))
        _safe, _msg = _safety_check(_combined)
        if not _safe:
            yield _sse("safety_halt", {"message": _msg})
            return

    council = select_council_for_mode(brief.mode)
    council_names = [a.name for a in council]
    prefix = _fa2_business_context_prefix(brief.language) if council_mode == "fa2" else ""
    raw_brief = prefix + build_council_context(brief) + mode_decorator_for_dream(brief.mode, brief.language)
    _cost_start = spent_today_usd()

    # ── A0: Architektura Marzenia ────────────────────────────────────────────
    dream: Optional[Any] = None
    project_id: Optional[int] = None
    if CORE_AVAILABLE and council_mode != "fa2":
        try:
            dream = await distill_dream(raw_brief, brief.mode, brief.language)
            if dream is not None:
                yield dream_architecture_sse(dream)
        except Exception as e:
            _log_orchestrator_issue("a0_dream_distillation", e)
            yield _sse("dream_architecture_error", {"error": str(e)})

    # ── Zapis marzenia + projektu ────────────────────────────────────────────
    debate_id: Optional[int] = None
    from db.backend import optional_debate_db
    from db.connection import DB_PATH as _STREAM_DB_PATH

    async with optional_debate_db(_STREAM_DB_PATH, DB_AVAILABLE) as db:
        if db is not None and dream is not None:
            try:
                debate_id, project_id = await persist_dream_and_project(
                    db, dream, brief, continuation_parent_id=continuation_parent_id
                )
                if project_id is not None:
                    proj_row = await repo.get_project(db, project_id)
                    yield _sse("project_state", proj_row or {})
            except Exception as e:
                _log_orchestrator_issue(
                    "persistence_a0",
                    e,
                    level="error",
                    debate_id=debate_id,
                    project_id=project_id,
                )

        # ── Budget warning ───────────────────────────────────────────────────
        budget_evt = maybe_budget_warning_sse()
        if budget_evt:
            try:
                from core.cost_tracking import maybe_fire_cost_webhook as _fw
                _t = asyncio.create_task(_fw({"event": "budget_soft_warning_sse"}))
                _background_tasks.add(_t)
                _t.add_done_callback(_background_tasks.discard)
            except Exception:
                pass
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
            yield _sse("synthesis_done", {"full_text": "Rada niedostępna — brak pakietu agents/"})
            yield _sse(
                "debate_done",
                {"debate_id": debate_id, "agent_count": 0, "timestamp": datetime.now(UTC).isoformat()},
            )
            return

        # ── Phase 1: Council (parallel agents) ───────────────────────────────
        full_voices: dict[str, str] = {}
        async for evt in _phase_council(
            council, raw_brief, dream, brief, db, council_mode
        ):
            if isinstance(evt, PhaseCouncilResult):
                full_voices = evt.full_voices
            else:
                yield evt

        # ── Live tensions ────────────────────────────────────────────────────
        pairs: list[dict[str, Any]] = []
        if compute_live_pair_frictions is not None:
            try:
                pairs = compute_live_pair_frictions(council_names, full_voices)
            except Exception as e:
                _log_orchestrator_issue("live_tensions", e, debate_id=debate_id)
        yield _sse("live_tensions", {"pairs": pairs})

        # ── Phase 2: Synthesis (Syez + audit) ────────────────────────────────
        synthesis_final = ""
        parsed_final: Optional[dict[str, Any]] = None
        async for evt in _phase_synthesis(
            raw_brief, full_voices, dream, brief, pairs, db, project_id, debate_id, council_mode
        ):
            if isinstance(evt, PhaseSynthesisResult):
                synthesis_final = evt.synthesis_final
                parsed_final = evt.parsed_final
            else:
                yield evt

        # ── Phase 3: Commit and finalize ─────────────────────────────────────
        async for evt in _phase_commit_and_finalize(
            db, debate_id, brief, full_voices, synthesis_final, parsed_final,
            project_id, dream, council, _cost_start, continuation_parent_id, council_mode,
        ):
            yield evt
