"""
Mapa modeli per agent — werdykt Rady „Mój Świat".

Filozofia:
  Opus 4.7  → Syez (synteza całości) + Szow (Cień — brutalnie szczery, bez autocenzury)
  Sonnet 4.6 → większość Rady (stabilna głębia + ekonomia)
  Haiku 4.6  → Kidi (spontaniczność) + Smaty (somatyczny instynkt)
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

# Aliasy modeli — jedno miejsce do podmiany, gdy Anthropic wypuści nowsze.
_OPUS    = os.getenv("MODEL_OPUS",    "claude-opus-4-7")
_SONNET  = os.getenv("MODEL_SONNET",  "claude-sonnet-4-6")
_HAIKU   = os.getenv("MODEL_HAIKU",   "claude-haiku-4-6")


AGENT_MODEL_CONFIG: dict[str, ModelCfg] = {
    # Stabilna baza (Sonnet) dla agentów nie wymienionych jawnie
    "default":  {"model": _SONNET, "temperature": 0.8, "max_tokens": 2000},

    # Sonnet 4.6 — Rada (głębia + ekonomia)
    "kogit":    {"model": _SONNET, "temperature": 0.7, "max_tokens": 4000},
    "tai":      {"model": _SONNET, "temperature": 0.6, "max_tokens": 4000},
    "deega":    {"model": _SONNET, "temperature": 0.0, "max_tokens": 2000},
    "relacjan": {"model": _SONNET, "temperature": 0.8, "max_tokens": 2000},
    "emojy":    {"model": _SONNET, "temperature": 0.8, "max_tokens": 2000},
    "obver":    {"model": _SONNET, "temperature": 0.8, "max_tokens": 2000},

    # Opus 4.7 — synteza i cień (miejsca gdzie liczy się absolutna jakość)
    "syez":     {"model": _OPUS,   "temperature": 0.5, "max_tokens": 3000},
    "szow":     {"model": _OPUS,   "temperature": 1.0, "max_tokens": 1500},

    # Haiku 4.6 — instynkt i spontaniczność
    "kidi":     {"model": _HAIKU,  "temperature": 1.0, "max_tokens": 1500},
    "smaty":    {"model": _HAIKU,  "temperature": 1.0, "max_tokens": 1500},
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


def get_model_config(agent_name: str) -> ModelCfg:
    """
    Zwraca config dla agenta po jego `name` (case-insensitive).
    Gdy HYBRID_MODELS_ENABLED=False — wszyscy lecą na default (Sonnet).
    """
    if not HYBRID_MODELS_ENABLED:
        return _validate(AGENT_MODEL_CONFIG["default"], "default")
    cfg = AGENT_MODEL_CONFIG.get(agent_name.lower(), AGENT_MODEL_CONFIG["default"])
    return _validate(cfg, agent_name)
