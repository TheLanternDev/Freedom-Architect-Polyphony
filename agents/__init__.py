"""
Rada Nadzorcza 'Moj Swiat' - 9 agentow + Syez jako orchestrator.

Molekularny silnik Architekta Wolnosci v3.2.
Kazdy agent reprezentuje jedna perspektywe procesu decyzyjnego.
Syez stoi POZA Rada - nie jest jednym z glosow, lecz facilitatorem
ktory czyta wszystkie 9 glosow i skleja je w spojna synteze.

v3.2: każda funkcja debaty przyjmuje opcjonalny `dream: DreamArchitecture`
(AKSJOMAT 1) — szkielet marzenia stojącego za briefem. Agenci dostają go
jako kontekst nadrzędny w swoich system promptach. Syez dodatkowo dostaje
serializację marzenia + audyt domknięcia (AKSJOMAT 2) wyłącznie jako proza.
"""

from __future__ import annotations

from typing import Any, Optional

from agents.base_agent import BaseAgent
from agents.relacjan import Relacjan
from agents.kogit import Kogit
from agents.emojy import Emojy
from agents.deega import Deega
from agents.syez import Syez
from agents.smaty import Smaty
from agents.szow import Szow
from agents.tai import Tai
from agents.obver import Obver
from agents.kidi import Kidi

from core.completion_enforcer import SYEZ_AKSJOMAT2_PROSE_APPEND

# 9 głosów Rady — Syez celowo poza listą
COUNCIL = [
    Relacjan(),
    Kogit(),
    Emojy(),
    Deega(),
    Smaty(),
    Szow(),
    Tai(),
    Obver(),
    Kidi(),
]

# Syez jako singleton-orchestrator, nie członek Rady
SYNTHESIZER = Syez()


def get_council() -> list[BaseAgent]:
    """Zwraca kopię listy 9 agentów Rady (bez Syeza)."""
    return list(COUNCIL)


def deliberate(context: str) -> list[tuple[str, str]]:
    """9 członków Rady zabiera głos — zwraca (imię, perspektywa)."""
    return [(agent.name, agent.contribute(context)) for agent in COUNCIL]


async def adeliberate(
    context: str,
    dream: Optional[Any] = None,
    *,
    language: str = "pl",
    debate_mode: str = "pelna",
) -> list[tuple[str, str]]:
    """Async + równolegle: 9 niezależnych wywołań LLM jednocześnie."""
    import asyncio
    voices = await asyncio.gather(
        *(
            a.acontribute(
                context, dream=dream, language=language, debate_mode=debate_mode
            )
            for a in COUNCIL
        )
    )
    return [(a.name, v) for a, v in zip(COUNCIL, voices)]


def _build_syez_input(context: str, voices_block: str, dream: Optional[Any]) -> str:
    """
    Składa wejście dla Syeza: marzenie (AKSJOMAT 1) + 9 głosów + brief
    + AKSJOMAT 2 w brzmieniu prozaicznym (bez JSON-a).
    """
    parts: list[str] = []
    if dream is not None:
        try:
            parts.append(
                "[ARCHITEKTURA MARZENIA — kontekst nadrzędny]\n" + dream.for_syez()
            )
        except Exception:
            pass
    parts.append("[Głosy Rady przed syntezą]\n" + voices_block)
    parts.append("[Oryginalny kontekst użytkownika]\n" + context)
    parts.append(SYEZ_AKSJOMAT2_PROSE_APPEND)
    return "\n\n".join(parts)


def full_synthesis(context: str, dream: Optional[Any] = None) -> str:
    """
    Pełna debata: 9 agentów komentuje kontekst, potem Syez (jako
    facilitator poza Radą) składa syntezę ich głosów.
    """
    voices = [a.contribute(context) for a in COUNCIL]
    bundle = "\n\n".join(
        f"[{a.name}]\n{v}" for a, v in zip(COUNCIL, voices)
    )
    syez_input = _build_syez_input(context, bundle, dream)
    synthesis = SYNTHESIZER.contribute(syez_input)
    header = "Rada Nadzorcza 'Moj Swiat' — debata wieloperspektywiczna\n\n"
    debate_block = "\n\n".join(
        f"── {a.name} ──\n{v}" for a, v in zip(COUNCIL, voices)
    )
    footer = "\n\n─── SYNTEZA (Syez) ───\n" + synthesis
    return header + debate_block + footer


async def afull_synthesis(
    context: str,
    dream: Optional[Any] = None,
    *,
    language: str = "pl",
    debate_mode: str = "pelna",
) -> str:
    """
    Async wersja: 9 agentów równolegle, potem Syez (orchestrator)
    syntezuje wszystkie ich głosy. Syez nie jest jednym z 9.
    """
    import asyncio
    voices = await asyncio.gather(
        *(
            a.acontribute(
                context, dream=dream, language=language, debate_mode=debate_mode
            )
            for a in COUNCIL
        )
    )
    bundle = "\n\n".join(
        f"[{a.name}]\n{v}" for a, v in zip(COUNCIL, voices)
    )
    syez_input = _build_syez_input(context, bundle, dream)
    synthesis = await SYNTHESIZER.acontribute(
        syez_input, dream=dream, language=language, debate_mode=debate_mode
    )
    if language == "en":
        header = "Supervisory Council 'My World' — multi-perspective debate\n\n"
        footer_label = "SYNTHESIS (Syez)"
    else:
        header = "Rada Nadzorcza 'Moj Swiat' — debata wieloperspektywiczna\n\n"
        footer_label = "SYNTEZA (Syez)"
    debate_block = "\n\n".join(
        f"── {a.name} ──\n{v}" for a, v in zip(COUNCIL, voices)
    )
    footer = f"\n\n─── {footer_label} ───\n" + synthesis
    return header + debate_block + footer


__all__ = [
    "BaseAgent",
    "Relacjan",
    "Kogit",
    "Emojy",
    "Deega",
    "Syez",
    "Smaty",
    "Szow",
    "Tai",
    "Obver",
    "Kidi",
    "COUNCIL",
    "SYNTHESIZER",
    "get_council",
    "deliberate",
    "adeliberate",
    "full_synthesis",
    "afull_synthesis",
]
