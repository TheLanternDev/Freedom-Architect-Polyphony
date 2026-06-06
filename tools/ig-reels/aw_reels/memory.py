from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import OUTPUT_DIR
from .session import Iteration, ReelSession, iteration_is_ready

MEMORY_PATH = OUTPUT_DIR / "memory.jsonl"


@dataclass(frozen=True)
class MemoryEntry:
    ts: str
    session_id: str
    iteration_id: str
    title: str
    hook: str
    concept_id: str | None
    prompt: str
    prompt_hash: str
    video_url: str | None
    local_path: str | None
    duration: float | None
    resolution: str
    kind: str
    status: str
    context_notes: str
    tags: tuple[str, ...]
    notes: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryEntry:
        return cls(
            ts=d["ts"],
            session_id=d["session_id"],
            iteration_id=d["iteration_id"],
            title=d.get("title", ""),
            hook=d.get("hook", ""),
            concept_id=d.get("concept_id"),
            prompt=d["prompt"],
            prompt_hash=d.get("prompt_hash", ""),
            video_url=d.get("video_url"),
            local_path=d.get("local_path"),
            duration=d.get("duration"),
            resolution=d.get("resolution", ""),
            kind=d.get("kind", ""),
            status=d.get("status", ""),
            context_notes=d.get("context_notes", ""),
            tags=tuple(d.get("tags") or ()),
            notes=d.get("notes", ""),
        )


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def append_entry(entry: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with MEMORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_iteration(
    session: ReelSession,
    it: Iteration,
    *,
    resolution: str,
) -> None:
    if not iteration_is_ready(it) and it.status != "done":
        return
    append_entry(
        {
            "ts": it.created_at,
            "session_id": session.id,
            "iteration_id": it.id,
            "title": session.title,
            "hook": session.hook,
            "concept_id": session.concept_id,
            "prompt": it.prompt,
            "prompt_hash": prompt_hash(it.prompt),
            "video_url": it.video_url,
            "local_path": it.local_path,
            "duration": it.duration,
            "resolution": resolution,
            "kind": it.kind.value,
            "status": it.status,
            "context_notes": session.context_notes,
            "tags": session.tags,
            "notes": it.notes,
        }
    )


def append_rating(
    session_id: str,
    iteration_id: str,
    score: int,
    note: str = "",
    *,
    prompt_hash_value: str = "",
) -> None:
    """Zapisz ocenę iteracji jako event 'rating' w memory.jsonl (nie psuje starych wpisów)."""
    append_entry(
        {
            "ts": _now_iso(),
            "event": "rating",
            "session_id": session_id,
            "iteration_id": iteration_id,
            "score": int(score),
            "note": note,
            "prompt_hash": prompt_hash_value,
        }
    )


def load_ratings(*, limit: int = 50) -> list[dict[str, Any]]:
    """Wczytaj eventy 'rating' (najnowsze pierwsze). Pomija stare wpisy generacji."""
    if not MEMORY_PATH.exists():
        return []
    lines = MEMORY_PATH.read_text(encoding="utf-8").strip().splitlines()
    out: list[dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("event") != "rating":
            continue
        out.append(d)
        if len(out) >= limit:
            break
    return out


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def load_entries(*, limit: int = 50, tag: str | None = None) -> list[MemoryEntry]:
    if not MEMORY_PATH.exists():
        return []
    lines = MEMORY_PATH.read_text(encoding="utf-8").strip().splitlines()
    entries: list[MemoryEntry] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            e = MemoryEntry.from_dict(json.loads(line))
        except (json.JSONDecodeError, KeyError):
            continue
        if tag and tag not in e.tags:
            continue
        entries.append(e)
        if len(entries) >= limit:
            break
    return entries


def find_by_iteration(session_id: str, iteration_id: str) -> MemoryEntry | None:
    for e in load_entries(limit=10_000):
        if e.session_id == session_id and e.iteration_id == iteration_id:
            return e
    return None


def context_brief(*, limit: int = 5) -> str:
    """Kompaktowy kontekst ostatnich generacji — zero kosztu API."""
    entries = load_entries(limit=limit)
    if not entries:
        return "Brak historii generacji."
    lines = ["Ostatnie generacje (Imagine):"]
    for e in entries:
        ctx = f" | ctx: {e.context_notes}" if e.context_notes else ""
        lines.append(
            f"- [{e.session_id}/{e.iteration_id}] {e.title} ({e.resolution}, {e.duration}s)"
            f"{ctx}\n  prompt_hash={e.prompt_hash} …{e.prompt[-120:]}"
        )
    return "\n".join(lines)


def duplicate_warning(text: str) -> str | None:
    h = prompt_hash(text)
    for e in load_entries(limit=200):
        if e.prompt_hash == h and e.status in ("done", "picked"):
            return f"Ten prompt był już generowany: {e.session_id}/{e.iteration_id}"
    return None
