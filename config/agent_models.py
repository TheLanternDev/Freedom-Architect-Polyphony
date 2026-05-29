"""
Mapa modeli per agent — werdykt Rady „Mój Świat".

Filozofia modeli (iteracja „jednolity model", app v3.3):
  Sonnet 4.6 → wszyscy agenci + Syez (jednolity model — spójność jakości i kosztów)
"""

from __future__ import annotations

import os
from typing import TypedDict


class ModelCfg(TypedDict):
    model: str
    temperature: float
    max_tokens: int


# Feature flag — pozwala wrócić do trybu „one model for all"
# bez ruszania kodu agentów.
HYBRID_MODELS_ENABLED: bool = (
    os.getenv("HYBRID_MODELS_ENABLED", "true").lower() == "true"
)

# Alias modelu — jedno miejsce do podmiany przy zmianie wersji.
_SONNET  = os.getenv("MODEL_SONNET",  "claude-sonnet-4-6")


AGENT_MODEL_CONFIG: dict[str, ModelCfg] = {
    # Sonnet 4.6 — wszyscy agenci i Syez
    "default":  {"model": _SONNET, "temperature": 0.8, "max_tokens": 2000},
    "kogit":    {"model": _SONNET, "temperature": 0.7, "max_tokens": 4000},
    "tai":      {"model": _SONNET, "temperature": 0.6, "max_tokens": 4000},
    "deega":    {"model": _SONNET, "temperature": 0.0, "max_tokens": 2000},
    "relacjan": {"model": _SONNET, "temperature": 0.8, "max_tokens": 2000},
    "emojy":    {"model": _SONNET, "temperature": 0.8, "max_tokens": 2000},
    "obver":    {"model": _SONNET, "temperature": 0.8, "max_tokens": 2000},
    "syez":     {"model": _SONNET, "temperature": 0.5, "max_tokens": 3000},
    "szow":     {"model": _SONNET, "temperature": 1.0, "max_tokens": 1500},
    "kidi":     {"model": _SONNET, "temperature": 1.0, "max_tokens": 1500},
    "smaty":    {"model": _SONNET, "temperature": 1.0, "max_tokens": 1500},
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
AGENT_MODEL_CONFIG_FA2: dict[str, ModelCfg] = {
    **AGENT_MODEL_CONFIG,
    "syez": {"model": _SONNET, "temperature": 0.6, "max_tokens": 5000},
}


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
