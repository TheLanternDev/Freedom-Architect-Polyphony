"""
Mapa modeli per agent — werdykt Rady „Mój Świat".

Filozofia modeli (iteracja „jednolity model", app v3.3):
  Sonnet 5 → wszyscy agenci + Syez (jednolity model — spójność jakości i kosztów)
"""

from __future__ import annotations

import os
from typing import TypedDict


class _ModelCfgOptional(TypedDict, total=False):
    # Per-agent override timeoutu LLM (sekundy) dla asyncio.wait_for.
    # Brak klucza → globalne AW_LLM_TIMEOUT_WAIT (55s). Potrzebne dla głosów
    # z wysokim max_tokens: non-streaming 5000 tok Sonneta to 60-120s.
    timeout_s: int


class ModelCfg(_ModelCfgOptional):
    model: str
    temperature: float
    max_tokens: int


# Feature flag — pozwala wrócić do trybu „one model for all"
# bez ruszania kodu agentów.
HYBRID_MODELS_ENABLED: bool = (
    os.getenv("HYBRID_MODELS_ENABLED", "true").lower() == "true"
)

# Alias modelu — jedno miejsce do podmiany przy zmianie wersji.
_SONNET  = os.getenv("MODEL_SONNET",  "claude-sonnet-5")

# ── Advisor tool (beta `advisor-tool-2026-03-01`) ───────────────────────────
# Executor = agent (Sonnet 5), advisor = model silniejszy konsultowany
# mid-generation. Zgodność par wg docs Anthropic: Sonnet 5 jako executor
# akceptuje jako advisora WYŁĄCZNIE Opus 4.8 / 4.7 / Fable 5 / Mythos 5
# (NIE Sonnet 4.6 ani Opus 4.6 — 400 invalid_request_error dla tamtych par).
#
# Domyślnie WYŁĄCZONE — to kosztowa dźwignia (advisor liczony osobno wg
# stawek modelu-advisora, BYOK płaci realny koszt), nie coś co ma się włączyć
# samo. Włącz świadomie: AW_ADVISOR_ENABLED=true.
ADVISOR_ENABLED: bool = os.getenv("AW_ADVISOR_ENABLED", "false").strip().lower() == "true"
ADVISOR_MODEL: str = os.getenv("AW_ADVISOR_MODEL", "claude-opus-4-8").strip() or "claude-opus-4-8"


def _int_env(name: str, default: int, *, lo: int, hi: int) -> int:
    """Int z ENV z twardym zakresem. Śmieciowa wartość NIE wywala importu
    (a więc całej appki) — warning + default.

    Wartość POZA zakresem też dostaje warning (review 2026-07-30): wcześniej
    `AW_ADVISOR_MAX_TOKENS=99999` było cicho przycinane do 16000, więc user
    ustawiał limit i dostawał inny, bez żadnego sygnału. Niespójne ze ścieżką
    „śmieciowy string", która warning miała."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    import sys

    try:
        parsed = int(raw)
    except ValueError:
        print(
            f"[agent_models] {name}={raw!r} nie jest liczbą — używam {default}",
            file=sys.stderr,
        )
        return default
    clamped = max(lo, min(parsed, hi))
    if clamped != parsed:
        print(
            f"[agent_models] {name}={parsed} poza dozwolonym zakresem "
            f"[{lo}, {hi}] — używam {clamped}",
            file=sys.stderr,
        )
    return clamped


# Rekomendacja z docs Anthropic (benchmark: ~7x mniej tokenów advisora,
# ~0% ucięć) — twardy strop per wywołanie advisora, min. 1024.
ADVISOR_MAX_TOKENS: int = _int_env("AW_ADVISOR_MAX_TOKENS", 2048, lo=1024, hi=16000)
# Per JEDNO wywołanie messages.create (nie per debata/konwersacja) — 1 wystarcza
# dla krótkiej, jednorazowej wypowiedzi agenta (nie jest to pętla agentowa).
ADVISOR_MAX_USES: int = _int_env("AW_ADVISOR_MAX_USES", 1, lo=1, hi=5)
# Które tryby debaty dopuszczają advisora — domyślnie TYLKO pełna (nie
# `codzienny`, który i tak już tnie max_tokens dla oszczędności; advisor na
# Opusie w trybie tańszym byłby sprzeczny z jego własnym celem).
ADVISOR_DEBATE_MODES: set[str] = {
    m.strip().lower()
    for m in os.getenv("AW_ADVISOR_DEBATE_MODES", "pelna").split(",")
    if m.strip()
}
# Które głosy mają advisora — domyślnie TYLKO Syez (rewizja decyzji
# 2026-07-07 „wszyscy”): to u niego advisor jest najbardziej wart ceny
# (udokumentowany failure mode uśredniania konfliktów), a koszt Opusa na
# kluczu BYOK rośnie liniowo z liczbą objętych głosów. Rozszerzenie na całą
# Radę: AW_ADVISOR_SCOPE=all — świadomie, po obejrzeniu kosztów i tego, czy
# rada mid-generation nie spłaszcza Szowa/Kidi/Obvera.
ADVISOR_SCOPE: set[str] = {
    s.strip().lower()
    for s in os.getenv("AW_ADVISOR_SCOPE", "syez").split(",")
    if s.strip()
}  # "all" | nazwy agentów małymi literami (np. "syez,szow")


AGENT_MODEL_CONFIG: dict[str, ModelCfg] = {
    # Sonnet 5 — wszyscy agenci i Syez
    "default":  {"model": _SONNET, "temperature": 0.8, "max_tokens": 2000},
    "kogit":    {"model": _SONNET, "temperature": 0.7, "max_tokens": 4000},
    "tai":      {"model": _SONNET, "temperature": 0.6, "max_tokens": 4000},
    "deega":    {"model": _SONNET, "temperature": 0.0, "max_tokens": 3500},
    "relacjan": {"model": _SONNET, "temperature": 0.8, "max_tokens": 3500},
    "emojy":    {"model": _SONNET, "temperature": 0.8, "max_tokens": 3500},
    "obver":    {"model": _SONNET, "temperature": 0.8, "max_tokens": 3500},
    "syez":     {"model": _SONNET, "temperature": 0.5, "max_tokens": 5000, "timeout_s": 120},
    "szow":     {"model": _SONNET, "temperature": 1.0, "max_tokens": 2500},
    "kidi":     {"model": _SONNET, "temperature": 1.0, "max_tokens": 2500},
    "smaty":    {"model": _SONNET, "temperature": 1.0, "max_tokens": 2500},
}


def _validate(cfg: ModelCfg, agent_name: str) -> ModelCfg:
    """Fail fast: temperatura w API Anthropic musi mieścić się w [0, 1]."""
    t = cfg["temperature"]
    if not (0.0 <= t <= 1.0):
        raise ValueError(
            f"Agent '{agent_name}': temperature={t} poza zakresem Anthropic API (0..1). "
            f"Popraw config/agent_models.py."
        )
    return cfg


# FA2: Syez z podniesionym max_tokens dla dłuższej analizy biznesowej.
# timeout_s=150: 5000 tok non-streaming NIE mieści się w globalnych 55s —
# bez tego każda dłuższa synteza fa2 kończy się „[błąd syntezy: TimeoutError]".
# SSE pod 150s ciszy: ZWERYFIKOWANE — orchestrator emituje synthesis_heartbeat
# co 8s przez całą fazę syntezy (debate_orchestrator._phase_synthesis), a
# frontend (useDebate) nie ma własnego timeoutu odczytu streamu.
AGENT_MODEL_CONFIG_FA2: dict[str, ModelCfg] = {
    **AGENT_MODEL_CONFIG,
    "syez": {"model": _SONNET, "temperature": 0.6, "max_tokens": 5000, "timeout_s": 150},
}


def advisor_enabled_for(agent_name: str, debate_mode: str) -> bool:
    """Czy TEN agent w TYM trybie debaty ma wołać Advisor tool.

    Fail-closed: cokolwiek niejasnego → False (advisor to koszt na cudzym
    kluczu BYOK, nie coś do zgadywania)."""
    if not ADVISOR_ENABLED:
        return False
    if (debate_mode or "").strip().lower() not in ADVISOR_DEBATE_MODES:
        return False
    if "all" in ADVISOR_SCOPE:
        return True
    return (agent_name or "").strip().lower() in ADVISOR_SCOPE


def get_model_config(agent_name: str, council_mode: str = "personal") -> ModelCfg:
    """
    Zwraca config dla agenta po jego `name` (case-insensitive).
    Gdy HYBRID_MODELS_ENABLED=False — wszyscy lecą na default (Sonnet).
    FA2: Syez na Sonnet (unika timeout przy długiej syntezie).
    """
    if not HYBRID_MODELS_ENABLED:
        return _validate(AGENT_MODEL_CONFIG["default"], "default")
    table = AGENT_MODEL_CONFIG_FA2 if council_mode == "fa2" else AGENT_MODEL_CONFIG
    cfg = table.get(agent_name.lower(), AGENT_MODEL_CONFIG["default"])
    return _validate(cfg, agent_name)
