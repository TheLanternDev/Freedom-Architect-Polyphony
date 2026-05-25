"""Shared type protocols for service layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class BriefLike(Protocol):
    """Structural protocol for debate brief objects used across services."""

    language: str
    mode: str
    category: str
    description: str
    intention: Optional[str]
    extra_context: Optional[str]
    scale: Optional[str]
    budget: Optional[str]


# ── Typed phase results ──────────────────────────────────────────────────────


@dataclass
class PhaseCouncilResult:
    """Wynik fazy council — głosy agentów + eventy SSE."""

    full_voices: dict[str, str]
    events: list[str] = field(default_factory=list)


@dataclass
class PhaseSynthesisResult:
    """Wynik fazy synthesis — finalna synteza + opcjonalne naruszenie."""

    synthesis_final: str
    parsed_final: Optional[dict[str, Any]] = None
    violation_payload: Optional[dict[str, Any]] = None
    events: list[str] = field(default_factory=list)
