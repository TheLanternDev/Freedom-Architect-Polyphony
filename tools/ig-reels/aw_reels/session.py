from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .config import OUTPUT_DIR


class IterationKind(str, Enum):
    GENERATE = "generate"
    VARIANT = "variant"
    EDIT = "edit"
    REFERENCE = "reference"


@dataclass
class Iteration:
    id: str
    kind: IterationKind
    prompt: str
    status: str  # pending | done | failed | picked
    parent_id: str | None
    request_id: str | None = None
    video_url: str | None = None
    local_path: str | None = None
    duration: float | None = None
    error: str | None = None
    notes: str = ""
    narration_path: str | None = None
    muxed_path: str | None = None
    ready_path: str | None = None  # finalny plik gotowy do IG (publish)
    created_at: str = field(default_factory=lambda: _now())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Iteration:
        # Kompatybilność wsteczna i w przód: tnij do znanych pól, defaulty z dataclass.
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in known}
        data["kind"] = IterationKind(data["kind"])
        return cls(**data)


@dataclass
class ReelSession:
    id: str
    title: str
    hook: str
    concept_id: str | None
    base_prompt: str
    aspect_ratio: str
    resolution: str
    duration: int
    iterations: list[Iteration] = field(default_factory=list)
    picked_id: str | None = None
    user_prompt_raw: str | None = None
    context_notes: str = ""
    tags: list[str] = field(default_factory=list)
    estimated_credits_used: int = 0
    voiceover_script: str = ""
    narration_path: str | None = None
    elevenlabs_voice_id: str | None = None
    # draft → picked → voiced → muxed → published (string w JSON, kompatybilne wstecz)
    pipeline_stage: str = "draft"
    voiceover_analysis: dict | None = None  # ostatni script-plan (ElevenLabs + heurystyki)
    created_at: str = field(default_factory=lambda: _now())
    updated_at: str = field(default_factory=lambda: _now())

    @property
    def path(self) -> Path:
        return OUTPUT_DIR / self.id / "session.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "hook": self.hook,
            "concept_id": self.concept_id,
            "base_prompt": self.base_prompt,
            "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "duration": self.duration,
            "iterations": [i.to_dict() for i in self.iterations],
            "picked_id": self.picked_id,
            "user_prompt_raw": self.user_prompt_raw,
            "context_notes": self.context_notes,
            "tags": self.tags,
            "estimated_credits_used": self.estimated_credits_used,
            "voiceover_script": self.voiceover_script,
            "narration_path": self.narration_path,
            "elevenlabs_voice_id": self.elevenlabs_voice_id,
            "pipeline_stage": self.pipeline_stage,
            "voiceover_analysis": self.voiceover_analysis,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReelSession:
        iterations = [Iteration.from_dict(i) for i in data.get("iterations", [])]
        return cls(
            id=data["id"],
            title=data["title"],
            hook=data.get("hook", ""),
            concept_id=data.get("concept_id"),
            base_prompt=data["base_prompt"],
            aspect_ratio=data["aspect_ratio"],
            resolution=data["resolution"],
            duration=int(data["duration"]),
            iterations=iterations,
            picked_id=data.get("picked_id"),
            user_prompt_raw=data.get("user_prompt_raw"),
            context_notes=data.get("context_notes", ""),
            tags=list(data.get("tags") or []),
            estimated_credits_used=int(data.get("estimated_credits_used") or 0),
            voiceover_script=str(data.get("voiceover_script") or ""),
            narration_path=data.get("narration_path"),
            elevenlabs_voice_id=data.get("elevenlabs_voice_id"),
            pipeline_stage=str(data.get("pipeline_stage") or "draft"),
            voiceover_analysis=data.get("voiceover_analysis"),
            created_at=data.get("created_at", _now()),
            updated_at=data.get("updated_at", _now()),
        )

    def save(self) -> None:
        self.updated_at = _now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_iteration(
        self,
        kind: IterationKind,
        prompt: str,
        *,
        parent_id: str | None = None,
    ) -> Iteration:
        it = Iteration(
            id=str(uuid.uuid4())[:8],
            kind=kind,
            prompt=prompt,
            status="pending",
            parent_id=parent_id,
        )
        self.iterations.append(it)
        self.save()
        return it

    def get_iteration(self, iteration_id: str) -> Iteration:
        for it in self.iterations:
            if it.id == iteration_id:
                return it
        raise KeyError(f"Iteracja '{iteration_id}' nie istnieje w sesji {self.id}")

    def record_credit(self, count: int = 1) -> None:
        """1 kredyt = 1 udane wywołanie generate (niezależnie od rozdzielczości)."""
        self.estimated_credits_used += count
        self.save()

    def lineage(self, iteration_id: str) -> list[Iteration]:
        by_id = {i.id: i for i in self.iterations}
        chain: list[Iteration] = []
        current = by_id.get(iteration_id)
        while current:
            chain.append(current)
            current = by_id.get(current.parent_id) if current.parent_id else None
        return list(reversed(chain))


def has_successful_iterations(session: ReelSession) -> bool:
    return any(it.status in USABLE_STATUSES for it in session.iterations)


USABLE_STATUSES = frozenset({"done", "picked"})


def iteration_is_ready(it: Iteration) -> bool:
    """Iteracja ma wideo i może być źródłem finalize/edit."""
    local = it.local_path and Path(it.local_path).is_file()
    return it.status in USABLE_STATUSES and bool(it.video_url or local)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session_id() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"reel-{ts}-{str(uuid.uuid4())[:4]}"


def create_session(
    *,
    title: str,
    hook: str,
    base_prompt: str,
    concept_id: str | None,
    aspect_ratio: str,
    resolution: str,
    duration: int,
    user_prompt_raw: str | None = None,
    context_notes: str = "",
    tags: list[str] | None = None,
) -> ReelSession:
    session = ReelSession(
        id=new_session_id(),
        title=title,
        hook=hook,
        concept_id=concept_id,
        base_prompt=base_prompt,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        duration=duration,
        user_prompt_raw=user_prompt_raw,
        context_notes=context_notes,
        tags=tags or [],
    )
    session.save()
    return session


def load_session(session_id: str) -> ReelSession:
    path = OUTPUT_DIR / session_id / "session.json"
    if not path.exists():
        raise FileNotFoundError(f"Sesja '{session_id}' nie istnieje: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReelSession.from_dict(data)


def list_sessions() -> list[ReelSession]:
    if not OUTPUT_DIR.exists():
        return []
    sessions: list[ReelSession] = []
    for p in sorted(OUTPUT_DIR.glob("reel-*/session.json"), reverse=True):
        try:
            sessions.append(ReelSession.from_dict(json.loads(p.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, KeyError):
            continue
    return sessions
