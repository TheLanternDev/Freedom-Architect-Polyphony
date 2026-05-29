"""
Faza 3: warstwa ucząca — personalizacja agentów per użytkownik.

Analizuje historię debat i buduje rolling notatki ewolucyjne per agent,
które następnie wpływają na zachowanie agenta (wstrzykiwane jako kontekst).

Mechanizm:
1. Po każdej debacie: `extract_evolution_snippet()` wyciąga kluczowe
   obserwacje z głosu agenta (kompresja do ~200 znaków).
2. Periodycznie: `rebuild_evolution_notes()` przebudowuje rolling notatkę
   z ostatnich N debat.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

MAX_EVOLUTION_NOTE_LEN = 2000
MAX_SNIPPETS_PER_AGENT = 20
SNIPPET_TARGET_LEN = 200


def extract_evolution_snippet(agent_name: str, voice_text: str) -> str:
    """
    Kompresuje głos agenta do krótkiego snippetu ewolucyjnego.
    Heurystyka: bierze pierwsze zdanie + ostatnie zdanie (jeśli inne).
    """
    text = (voice_text or "").strip()
    if len(text) < 30:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if not sentences:
        return ""

    first = sentences[0]
    last = sentences[-1] if len(sentences) > 1 else ""

    snippet = first
    if last and last != first:
        snippet = f"{first} (...) {last}"

    if len(snippet) > SNIPPET_TARGET_LEN:
        snippet = snippet[:SNIPPET_TARGET_LEN - 3] + "..."

    return snippet


def merge_evolution_notes(existing_note: str, new_snippet: str) -> str:
    """
    Łączy istniejącą rolling notatkę z nowym snippetem.
    Utrzymuje max MAX_SNIPPETS_PER_AGENT wpisów, FIFO.
    """
    if not new_snippet or not new_snippet.strip():
        return existing_note

    lines = [l for l in (existing_note or "").strip().split("\n") if l.strip()]
    lines.append(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d')}] {new_snippet.strip()}")

    if len(lines) > MAX_SNIPPETS_PER_AGENT:
        lines = lines[-MAX_SNIPPETS_PER_AGENT:]

    result = "\n".join(lines)
    if len(result) > MAX_EVOLUTION_NOTE_LEN:
        while len(result) > MAX_EVOLUTION_NOTE_LEN and len(lines) > 3:
            lines.pop(0)
            result = "\n".join(lines)

    return result


async def rebuild_evolution_for_agent(
    db: Any,
    agent_name: str,
    repo: Any,
    *,
    max_debates: int = 30,
) -> str:
    """
    Przebudowuje rolling notatkę z historii głosów.
    Wykorzystuje repo.list_agent_voices_recent (jeśli dostępne).
    """
    try:
        voices = await repo.list_recent_voices_for_agent(db, agent_name, limit=max_debates)
    except (AttributeError, Exception):
        logger.debug("list_recent_voices_for_agent niedostępne — skip rebuild dla %s", agent_name)
        return ""

    note = ""
    for v in voices:
        snippet = extract_evolution_snippet(agent_name, v.get("voice_text", ""))
        if snippet:
            note = merge_evolution_notes(note, snippet)

    return note



async def run_full_evolution_cycle(db: Any, repo: Any, agents: list[str]) -> dict[str, str]:
    """Przebudowuje notatki dla wszystkich agentów; zwraca dict agent→note."""
    results = {}
    for agent in agents:
        note = await rebuild_evolution_for_agent(db, agent, repo)
        if note:
            await repo.merge_agent_evolution_snippet(db, agent, f"[rebuild] {note[-200:]}")
            results[agent] = note
    return results
