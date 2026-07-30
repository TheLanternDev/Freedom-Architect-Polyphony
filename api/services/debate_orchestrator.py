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
from agents.base_agent import (
    InvalidLlmKeyError,
    MissingLlmKeyError,
    _LLM_TIMEOUT_ERRORS,
)
from config.llm_providers import LLM_TIMEOUT_WAIT_SEC, anthropic_api_key, effective_llm_backend

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
    insert_debate_for_stream,
    persist_dream_and_project,
)
from api.services.mode_helpers import (
    _pending_msg,
    build_audit_fix_prompt,
    mode_decorator_for_dream,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

from api.services._sse import sse as _sse


def select_council_for_mode(mode: str) -> list[Any]:
    """Zwraca listę agentów dla trybu debaty.

    Jedno źródło prawdy: `modes.MODE_AGENTS` (re-export z
    `business_fa2.config.modes`). Lista nazw → podzbiór Rady w kolejności
    COUNCIL; `None` lub nieznany tryb → pełna Rada (9).
    """
    if not RADA_AVAILABLE:
        return []
    from modes import MODE_AGENTS

    allowed = MODE_AGENTS.get(mode)
    if allowed is None:
        return list(COUNCIL)
    return [a for a in COUNCIL if a.name in allowed]


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


_TENSION_HIGH_THRESHOLD: float = 0.65  # powyżej tej wartości para jest eksponowana jako blok konfrontacyjny


def _build_tension_structured_bundle(
    full_voices: dict[str, str],
    live_pairs: list[dict[str, Any]],
    *,
    lang: str = "pl",
) -> str:
    """
    Buduje bundle głosów dla Syeza z eksponowaniem par wysokiego napięcia.

    Filozofia (Stage 2 / Polyphony): Syez dostaje pary w konflikcie RAZEM,
    jedna pod drugą, z jawnym nagłówkiem napięcia — zamiast płaskiej listy
    gdzie konflikty są ukryte. Wymusza to na Syezie dostrzeżenie napięcia
    strukturalnie, a nie wyłącznie przez monitor napięć na końcu payloadu.

    Bezpieczeństwo / izolacja: funkcja operuje wyłącznie na głosach z bieżącego
    żądania (in-memory dict). Żadnych cross-request flows; ContextVar tenant_id
    nie jest modyfikowany. Zgodne z izolacją multi-tenant Stage 1.

    Agenci eksponowani w parach nie są usuwani z "pozostałych głosów" —
    Syez widzi pełny zestaw, ale najpierw widzi konflikty. Każdy głos
    pojawia się raz w parze i jest pominięty w sekcji "Pozostałe głosy",
    żeby uniknąć duplikacji.
    """
    high_pairs = [p for p in live_pairs if float(p.get("intensity", 0)) >= _TENSION_HIGH_THRESHOLD]
    shown: set[str] = set()
    parts: list[str] = []

    if high_pairs:
        hdr = (
            "═══ GŁOSY RADY — PARY W NAPIĘCIU (intensity ≥ 0.65 — eksponowane razem) ═══"
            if lang == "pl"
            else "═══ COUNCIL VOICES — TENSION PAIRS (intensity ≥ 0.65 — shown together) ═══"
        )
        parts.append(hdr)
        for pair in high_pairs[:4]:  # maks. 4 pary, żeby nie zaburzyć proporcji payloadu
            a_name = pair["a"]
            b_name = pair["b"]
            a_voice = full_voices.get(a_name, "")
            b_voice = full_voices.get(b_name, "")
            if not a_voice or not b_voice:
                continue
            intensity = pair["intensity"]
            if lang == "pl":
                sep = f"── NAPIĘCIE: {a_name} ↔ {b_name}  ({intensity}) ──"
                call = (
                    f"Syez — tu jest realne napięcie między tymi głosami. "
                    f"Nie uśredniaj: nazwij je jednym zdaniem zaczynającym się od "
                    f"'{a_name} i {b_name} są w napięciu, ponieważ...'"
                )
            else:
                sep = f"── TENSION: {a_name} ↔ {b_name}  ({intensity}) ──"
                call = (
                    f"Syez — there is a real tension between these voices. "
                    f"Do not average: name it in one sentence starting with "
                    f"'{a_name} and {b_name} are in tension because...'"
                )
            parts.append(sep)
            parts.append(f"[{a_name}]\n{a_voice}")
            parts.append(f"[{b_name}]\n{b_voice}")
            parts.append(call)
            shown.add(a_name)
            shown.add(b_name)

    remaining = {k: v for k, v in full_voices.items() if k not in shown}
    if remaining:
        if high_pairs:
            rem_hdr = (
                "── Pozostałe głosy Rady ──"
                if lang == "pl"
                else "── Remaining Council voices ──"
            )
            parts.append(rem_hdr)
        for name, voice in remaining.items():
            parts.append(f"[{name}]\n{voice}")

    return "\n\n".join(parts)


# ── Zadanie 1: hierarchiczna oś napięć (TensionAxis) ────────────────────────
#
# Filozofia: structured payload Syeza prawie zawsze jest pusty (Syez ma ZAKAZ
# JSON — tylko proza + mermaid). Wiarygodnym, deterministycznym źródłem napięć
# jest monitor napięć (`live_pairs` z intensity) + mapowanie agentów na oś
# structural↔somatic↔shadow (z instrukcji syez.py) + zdania z prozy (mandat
# polifonii). Składamy to TUTAJ, obok Syeza — bez dodatkowego wywołania LLM
# (token-minimal) i bez dotykania kruchego parsera JSON. Operuje wyłącznie na
# danych bieżącego żądania (in-memory) — izolacja tenantów nietknięta.

_AGENT_AXIS_POLE: dict[str, str] = {
    "Kogit": "structural", "Tai": "structural", "Obver": "structural",
    "Relacjan": "structural",
    "Emojy": "somatic", "Smaty": "somatic", "Kidi": "somatic",
    "Szow": "shadow", "Deega": "shadow",
}
_POLE_PRIORITY: dict[str, int] = {"shadow": 3, "somatic": 2, "structural": 1}


def _axis_depth(intensity: float) -> int:
    """Głębia hierarchii z intensywności: silniejsze napięcie = głębszy korzeń."""
    if intensity >= 0.72:
        return 3
    if intensity >= 0.45:
        return 2
    return 1


def _pair_pole(a: str, b: str) -> str:
    """Pas kolizji pary = biegun o wyższym priorytecie (shadow > somatic > structural)."""
    pa = _AGENT_AXIS_POLE.get(a, "structural")
    pb = _AGENT_AXIS_POLE.get(b, "structural")
    return pa if _POLE_PRIORITY[pa] >= _POLE_PRIORITY[pb] else pb


_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    """Usuwa bloki ```…``` (m.in. ```mermaid) — etykiety węzłów zawierają imiona
    agentów i zatruwały `why`/`prose_anchor` surowym kodem diagramu (C1)."""
    if not text:
        return ""
    return _CODE_FENCE_RE.sub(" ", text)


def _clip(s: str, limit: int = 200) -> str:
    """Przycięcie po granicy słowa + „…" — zamiast twardego cięcia w połowie słowa (C3)."""
    s = s.strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    sp = cut.rfind(" ")
    if sp > limit * 0.6:  # nie ucinaj zbyt agresywnie gdy brak spacji blisko końca
        cut = cut[:sp]
    return cut.rstrip() + "…"


def _find_pair_sentence(prose: str, a: str, b: str) -> str:
    """Zdanie z prozy (BEZ bloków kodu) wymieniające oba imiona agentów."""
    if not prose:
        return ""
    for s in re.split(r"(?<=[.!?])\s+", prose):
        if a in s and b in s:
            return _clip(s, 200)
    return ""


# Trybo-zależny podpis osi (C4, wariant i): biegun = rejestr myślenia agenta,
# nie temat. W fa2 ten sam słownik biegunów, ale podpis sygnalizuje, że opisuje
# SPOSÓB rozumowania (nie „somatyczność" tematu biznesowego).
_AXIS_LABEL: dict[str, str] = {
    "personal": "structural ↔ somatic ↔ cień",
    "fa2": "rejestr myślenia: strukturalny ↔ somatyczny ↔ cień",
}


def build_tension_axis(
    full_voices: dict[str, str],
    live_pairs: list[dict[str, Any]],
    synthesis: str,
    council_mode: str = "personal",
) -> Optional[dict[str, Any]]:
    """Buduje hierarchiczny payload osi napięć. None → frontend wraca do Mermaida."""
    if not live_pairs:
        return None
    present = set(full_voices.keys())
    pairs = [p for p in live_pairs if p.get("a") in present and p.get("b") in present]
    if not pairs:
        return None
    pairs = sorted(pairs, key=lambda p: float(p.get("intensity", 0)), reverse=True)[:8]

    prose = _strip_code_fences(synthesis)

    tensions: list[dict[str, Any]] = []
    for p in pairs:
        a, b = p["a"], p["b"]
        inten = round(float(p.get("intensity", 0)), 3)
        pole = _pair_pole(a, b)
        sent = _find_pair_sentence(prose, a, b)
        tensions.append({
            "between": [a, b],
            # C2: gdy proza nie nazwała tej pary — deterministyczny fallback,
            # żeby mapa nigdy nie miała pustego `why`. Anchor zostaje null (brak
            # highlightu w prozie), ale to nie „garbage".
            "why": sent or f"Napięcie na osi {pole}: {a} ↔ {b}",
            "intensity": inten,
            "axis_pole": pole,
            "depth": _axis_depth(inten),
            "prose_anchor": sent or None,
        })

    ta, tb = pairs[0]["a"], pairs[0]["b"]
    core_sent = _find_pair_sentence(prose, ta, tb)
    central_axis = {
        "core": core_sent or f"{ta} ↔ {tb}",
        "poles": [ta, tb],
        "dominant_pole": _pair_pole(ta, tb),
    }
    return {
        "central_axis": central_axis,
        "tensions": tensions,
        "axis_label": _AXIS_LABEL.get(council_mode, _AXIS_LABEL["personal"]),
    }


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
            "• The AXIOM 2 completion audit MUST be readable INSIDE the prose.\n"
            "• POLYPHONY MANDATE (Stage 2): for every pair marked as TENSION "
            "in the Council voices section — write EXACTLY one sentence starting with "
            "both agents' names (e.g. 'Kogit and Szow are in tension because...'). "
            "FORBIDDEN: averaging the conflict into compromise — if two voices pull "
            "in opposite directions, the synthesis must show that, not hide it. "
            "Contradiction is information, not an error to be resolved.\n"
            "• CONSOLIDATION MANDATE (always): agents may have independently reached "
            "a similar move — consolidating it is YOUR job, not theirs. Do not repeat "
            "the same move nine times. Surface EXACTLY ONE closing move (≤60 min); if "
            "many voices converged on a variant of it, name that explicitly as a signal "
            "('most of the Council converged on X — not a coincidence, a strength'), "
            "then show the MAP OF DIFFERENT PATHS: who, from which pole (somatic / "
            "relational / structural / shadow), reached that move by a different route. "
            "Convergence of goal with divergence of reasoning is the strongest result."
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
        "• Audyt domknięcia z protokołu AKSJOMATU 2 musi być czytelny WEWNĄTRZ prozy.\n"
        "• MANDAT POLYPHONII (Stage 2): dla każdej pary oznaczonej jako NAPIĘCIE "
        "w sekcji głosów Rady — napisz DOKŁADNIE jedno zdanie zaczynające się od "
        "imion obu agentów (np. 'Kogit i Szow są w napięciu, ponieważ...'). "
        "ZAKAZ uśredniania tego konfliktu do kompromisu — jeśli dwa głosy ciągną "
        "w przeciwne strony, synteza musi to pokazać, nie ukrywać. "
        "Sprzeczność jest informacją, nie błędem do wyeliminowania.\n"
        "• MANDAT KONSOLIDACJI (zawsze): agenci mogli niezależnie dojść do "
        "podobnego ruchu — to Twoje zadanie, nie ich. Nie powtarzaj tego samego "
        "ruchu dziewięć razy. Wyłoń DOKŁADNIE JEDEN ruch domknięcia (≤60 min), a "
        "jeśli wiele głosów zbiegło się do jego wariantu — nazwij to wprost jako "
        "sygnał („większość Rady zeszła się do X — to nie przypadek, to siła”), "
        "po czym pokaż MAPĘ RÓŻNYCH DRÓG: kto i z jakiego bieguna (somatyczny / "
        "relacyjny / strukturalny / cień) doszedł do tego ruchu innym torem. "
        "Zbieżność celu przy rozbieżności uzasadnień jest najmocniejszym wynikiem."
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
        except MissingLlmKeyError:
            await queue.put(("__missing_llm_key__", True))
        except InvalidLlmKeyError:
            await queue.put(("__invalid_llm_key__", True))
        except Exception as e:
            await queue.put((f"[błąd: {e}]", True))

    def _is_error_voice(text: str) -> bool:
        return (
            text.startswith("[błąd")
            or text.startswith("[error")
            or text.startswith("[timeout:")
            or text == "__missing_llm_key__"
            or text == "__invalid_llm_key__"
        )

    for a in council:
        yield _sse("agent_start", {"agent": a.name})

    tasks = [asyncio.create_task(run_agent(a, agent_queues[a.name])) for a in council]
    try:
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
                        if text == "__missing_llm_key__":
                            yield _sse(
                                "stream_error",
                                {
                                    "message": (
                                        "Brak klucza LLM — dodaj swój klucz w Ustawieniach"
                                        if lang != "en"
                                        else "Missing LLM key — add your key in Settings"
                                    ),
                                    "error_type": "missing_llm_key",
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
                            return
                        if text == "__invalid_llm_key__":
                            yield _sse(
                                "stream_error",
                                {
                                    "message": (
                                        "Klucz Anthropic odrzucony — sprawdź i wpisz ponownie w Ustawieniach"
                                        if lang != "en"
                                        else "Anthropic key rejected — check and re-enter in Settings"
                                    ),
                                    "error_type": "invalid_llm_key",
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
                            return
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
    finally:
        # Stage 4 resilience: klient SSE może rozłączyć się podczas pracy agentów.
        # FastAPI cancelluje async generator → GeneratorExit przy następnym yield/await.
        # Cancelujemy aktywne task-i LLM, żeby nie palić tokenów Anthropic po rozłączeniu.
        #
        # Tech-debt fix: await gather(return_exceptions=True) — dajemy task-om chwilę
        # na obsługę CancelledError, co pozwala na czysty shutdown SDK Anthropic.
        # return_exceptions=True zapobiega re-raise CancelledError z gather.
        _pending = [_t for _t in tasks if not _t.done()]
        if _pending:
            for _t in _pending:
                _t.cancel()
            try:
                await asyncio.gather(*_pending, return_exceptions=True)
            except Exception:
                pass  # gather sam może zostać anulowany — ignorujemy


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
            # advisor_override=False: to mechaniczna naprawa formatu (audyt
            # domknięcia niekompletny/niewykryty), nie świeże rozumowanie —
            # Rada i marzenie się nie zmieniły. Advisor drugi raz na tej samej
            # treści to podwójny koszt/opóźnienie Opusa bez wartości.
            fixed = await SYNTHESIZER.acontribute(
                fix_prompt, dream=dream, language=lang, debate_mode=brief.mode,
                council_mode=council_mode,
                advisor_override=False,
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

    # Stage 2 / Polyphony: bundle z eksponowanymi parami wysokiego napięcia.
    # Syez widzi konflikty strukturalnie (razem, z nagłówkiem), a nie tylko
    # jako osobny monitor na końcu payloadu — zmniejsza ryzyko uśredniania.
    bundle = _build_tension_structured_bundle(full_voices, pairs, lang=lang)
    syez_payload = build_syez_payload(raw_brief, bundle, dream, brief, live_pairs=pairs)

    _syez_task = asyncio.create_task(
        SYNTHESIZER.acontribute(syez_payload, dream=dream, language=lang, council_mode=council_mode)
    )
    try:
        while not _syez_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(_syez_task), timeout=8.0)
            except asyncio.TimeoutError:
                yield _sse("synthesis_heartbeat", {"status": "thinking"})
    finally:
        # Stage 4 resilience: analogicznie do _phase_council — cancel Syez task
        # gdy klient SSE rozłączy się w trakcie syntezy.
        if not _syez_task.done():
            _syez_task.cancel()

    try:
        synthesis = _syez_task.result()
    except BaseException as e:
        # str(e) bywa puste (CancelledError, niektóre timeouty, anthropic errors bez body).
        # Bez typu wyjątku komunikat „[błąd syntezy: ]” jest nie do zdiagnozowania.
        logger.exception("Syez synthesis failed")
        etype = type(e).__name__
        emsg = str(e).strip() or "<brak treści wyjątku — sprawdź logi backendu>"
        synthesis = (
            f"[błąd syntezy: {etype}: {emsg}]" if lang == "pl"
            else f"[synthesis error: {etype}: {emsg}]"
        )

    for chunk in chunk_words(synthesis, 5):
        yield _sse("synthesis_chunk", {"chunk": chunk})
        await asyncio.sleep(0.025)
    yield _sse("synthesis_done", {"full_text": synthesis})

    # ── Zadanie 1: hierarchiczna oś napięć (fallback do Mermaida gdy None) ─
    _axis: Optional[dict[str, Any]] = None
    try:
        _axis = build_tension_axis(full_voices, pairs, synthesis, council_mode)
        if _axis is not None:
            yield _sse("tension_axis", _axis)
    except Exception as e:  # noqa: BLE001 — wizualizacja nie może wywrócić syntezy
        _log_orchestrator_issue("tension_axis_build", e, debate_id=debate_id)

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
    yield PhaseSynthesisResult(  # type: ignore[misc]
        synthesis_final=synthesis_final,
        parsed_final=parsed_final,
        tension_axis=_axis,
    )


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
    tension_axis: Optional[dict[str, Any]] = None,
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
            # Persystencja osi napięć (Zadanie 1): scalamy ją do full_synthesis_json,
            # żeby /debate/{id} i /thread zwracały ją jako synthesis_structured.tension_axis
            # bez zmian w main.py. Gdy parsed_final puste, zapisujemy sam axis.
            save_json = parsed_final
            if tension_axis is not None:
                save_json = dict(parsed_final or {})
                save_json["tension_axis"] = tension_axis
            await repo.save_synthesis(db, debate_id, synthesis_final, save_json)
            await db.commit()
        except Exception as e:
            # Audyt izolacji (ADR-001): świadomy fail-soft. Błąd zapisu (w tym
            # odrzucenie przez RLS — pg_wrap re-raisuje fail-closed PRZED commitem,
            # więc nic cross-tenant się nie zapisze) NIE crashuje streamu — user
            # dostaje wynik, ale synteza nie jest utrwalona. Sygnalizowane tylko
            # w logach (level=error), nie w odpowiedzi SSE. To akceptowalny tradeoff,
            # nie luka izolacji.
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
        # Nie przesyłamy str(e) do klienta — szczegóły są w logach serwera.
        # Klient dostaje tylko typ wyjątku (nie zawiera PII ani ścieżek wewnętrznych).
        yield _sse(
            "stream_error",
            {"message": "Strumień debaty pękł — sprawdź logi serwera.", "error_type": type(e).__name__},
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

    # BYOK fail-closed: prod/boxed bez klucza usera nie startujemy Rady.
    try:
        from api.settings import security_hardened

        if security_hardened() and effective_llm_backend() == "none" and not anthropic_api_key():
            _msg = (
                "Brak klucza LLM — dodaj swój klucz w Ustawieniach"
                if brief.language != "en"
                else "Missing LLM key — add your key in Settings"
            )
            yield _sse(
                "stream_error",
                {"message": _msg, "error_type": "missing_llm_key"},
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
            return
    except Exception as e:
        _log_orchestrator_issue("byok_precheck", e)

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
            # str(e) może zawierać ścieżki / fragmenty SQL — logujemy w _log_orchestrator_issue,
            # klient dostaje wyłącznie typ wyjątku.
            yield _sse("dream_architecture_error", {"error_type": type(e).__name__})

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

        # ── AKSJOMAT 1: Obraz Użytkownika → ContextVar wstrzykiwania ─────────
        # Tylko personal. Zawsze ustawiamy (None gdy brak/fa2), by nie odziedziczyć
        # wartości z poprzedniej debaty w ewentualnie współdzielonym Tasku.
        try:
            from core.obraz_uzytkownika import set_obraz_context

            _obraz_ctx_val: Optional[str] = None
            if db is not None and council_mode != "fa2" and CORE_AVAILABLE:
                from db.tenant import current_user_id as _cuid

                _obraz_row = await repo.get_user_obraz(db, user_subject=_cuid())
                if _obraz_row:
                    from core.obraz_uzytkownika import ObrazUzytkownika

                    _obraz = ObrazUzytkownika.model_validate_json(_obraz_row["obraz_json"])
                    _obraz_ctx_val = _obraz.as_agent_context() or None
            set_obraz_context(_obraz_ctx_val)
        except Exception as e:  # noqa: BLE001
            _log_orchestrator_issue("obraz_context_load", e, debate_id=debate_id)
            try:
                from core.obraz_uzytkownika import set_obraz_context as _soc
                _soc(None)
            except Exception:
                pass

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

        # ── Debate row (po Radzie — brak orphanów przy zerwaniu SSE) ─────────
        if db is not None and debate_id is None:
            try:
                debate_id = await insert_debate_for_stream(
                    db,
                    brief,
                    dream_id=dream.dream_id if dream is not None else None,
                    continuation_parent_id=continuation_parent_id,
                )
            except Exception as e:
                _log_orchestrator_issue(
                    "debate_insert_post_council",
                    e,
                    level="error",
                    project_id=project_id,
                )

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
        tension_axis: Optional[dict[str, Any]] = None
        async for evt in _phase_synthesis(
            raw_brief, full_voices, dream, brief, pairs, db, project_id, debate_id, council_mode
        ):
            if isinstance(evt, PhaseSynthesisResult):
                synthesis_final = evt.synthesis_final
                parsed_final = evt.parsed_final
                tension_axis = evt.tension_axis
            else:
                yield evt

        # ── Phase 3: Commit and finalize ─────────────────────────────────────
        async for evt in _phase_commit_and_finalize(
            db, debate_id, brief, full_voices, synthesis_final, parsed_final,
            project_id, dream, council, _cost_start, continuation_parent_id, council_mode,
            tension_axis,
        ):
            yield evt
