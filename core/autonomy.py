"""
Mechanizm Autonomii Rady v1.2 — spec 15 maja 2026.

Rada może pracować samodzielnie między sesjami:
  - Analizować problemy z perspektywy wszystkich agentów
  - Opracowywać 1–3 zintegrowane propozycje
  - Przygotowywać materiały „gotowe do użycia"
  - Zawsze przechodzi Test Zgodności z Patrykiem (core.identity)
  - Zawsze wraca z pytaniem: „Którą wersję wybierasz?"

Limity (twarde, spec v1.0):
  - MAX_AUTONOMOUS_PROCESSES = 3 (jednocześnie)
  - Pełna transparentność (każdy proces w rejestrze, status czytelny)
  - Nigdy nie wykonuje akcji nieodwracalnych bez aprobaty Patryka

Ten moduł dostarcza **rejestr + cykl życia procesu**. Faktyczne uruchamianie
agentów (LLM calls, kolejki, scheduler) podpinasz osobno — to celowe,
żeby trzymać Aksjomaty oddzielone od I/O.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Optional

from core.identity import patryk_compliance_check

logger = logging.getLogger(__name__)

MAX_AUTONOMOUS_PROCESSES: int = 3


class AutonomyStatus(str, Enum):
    PENDING = "pending"          # Zgłoszony, czeka na slot
    RUNNING = "running"          # Rada pracuje
    READY_FOR_PATRYK = "ready"   # Propozycje gotowe, czekają na wybór
    REJECTED_BY_AXIOM_3 = "rejected_axiom_3"  # Test Zgodności odmówił
    DONE = "done"                # Patryk wybrał i zamknął
    ABANDONED = "abandoned"      # Świadomie porzucony (z uzasadnieniem ≥50 znaków)


@dataclass
class AutonomousProcess:
    id: str
    title: str
    triggered_by: str  # "patryk" | "system_observation" | "ritual_daily" | itp.
    created_at: datetime
    status: AutonomyStatus = AutonomyStatus.PENDING
    proposals: list[dict[str, Any]] = field(default_factory=list)  # max 3
    abandon_reason: Optional[str] = None
    compliance_warnings: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "triggered_by": self.triggered_by,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "proposals": list(self.proposals),
            "abandon_reason": self.abandon_reason,
            "compliance_warnings": list(self.compliance_warnings),
        }


class AutonomyRegistry:
    """In-memory rejestr (per-process). Persistencję podepnij do `db.connection`
    gdy będziesz gotowy — interfejs jest mały i stabilny."""

    def __init__(self, *, limit: int = MAX_AUTONOMOUS_PROCESSES) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, AutonomousProcess] = {}
        self._limit = limit

    # ── Cykl życia ──────────────────────────────────────────────────────

    def open(self, *, title: str, triggered_by: str = "patryk") -> AutonomousProcess:
        with self._lock:
            active = [p for p in self._items.values() if p.status in (AutonomyStatus.PENDING, AutonomyStatus.RUNNING)]
            if len(active) >= self._limit:
                raise RuntimeError(
                    f"Mechanizm Autonomii: limit {self._limit} jednoczesnych procesów osiągnięty. "
                    "Zamknij jeden lub poczekaj — spec v1.0 nie pozwala na więcej."
                )
            proc = AutonomousProcess(
                id=str(uuid.uuid4()),
                title=title.strip(),
                triggered_by=triggered_by,
                created_at=datetime.now(timezone.utc),
            )
            self._items[proc.id] = proc
            logger.info("autonomy: open %s '%s'", proc.id, proc.title)
            return proc

    def attach_proposals(self, proc_id: str, proposals: Iterable[dict[str, Any]]) -> AutonomousProcess:
        """Dołącz max 3 zintegrowane propozycje + automatyczny Test Zgodności.
        Jeśli Aksjomat 3 odmawia którejkolwiek — proces idzie do REJECTED."""
        with self._lock:
            proc = self._must_get(proc_id)
            props = list(proposals)[:3]  # twardo max 3, zgodnie ze spec
            all_warnings: list[str] = []
            for i, p in enumerate(props):
                verdict = patryk_compliance_check(str(p.get("text") or p.get("summary") or ""))
                p["_compliance"] = verdict.to_payload()
                all_warnings.extend(f"[{i+1}] {w}" for w in verdict.warnings)
                if not verdict.passes:
                    proc.status = AutonomyStatus.REJECTED_BY_AXIOM_3
                    proc.compliance_warnings = all_warnings
                    proc.proposals = props
                    logger.warning("autonomy: %s rejected by Axiom 3", proc_id)
                    return proc
            proc.proposals = props
            proc.compliance_warnings = all_warnings
            proc.status = AutonomyStatus.READY_FOR_PATRYK
            return proc

    def mark_done(self, proc_id: str, *, chosen_index: int) -> AutonomousProcess:
        with self._lock:
            proc = self._must_get(proc_id)
            if proc.status != AutonomyStatus.READY_FOR_PATRYK:
                raise RuntimeError(f"autonomy: {proc_id} nie jest gotowy do wyboru (status={proc.status.value})")
            if not (0 <= chosen_index < len(proc.proposals)):
                raise ValueError(f"autonomy: chosen_index poza zakresem (0..{len(proc.proposals)-1})")
            proc.proposals = [proc.proposals[chosen_index]]
            proc.status = AutonomyStatus.DONE
            return proc

    def abandon(self, proc_id: str, *, reason: str) -> AutonomousProcess:
        """Świadome porzucenie — wymaga ≥50 znaków uzasadnienia (parytet z
        validate_archive_reason w completion_enforcer)."""
        r = (reason or "").strip()
        if len(r) < 50:
            raise ValueError("autonomy: porzucenie wymaga ≥50 znaków uzasadnienia (Aksjomat 2).")
        with self._lock:
            proc = self._must_get(proc_id)
            proc.abandon_reason = r
            proc.status = AutonomyStatus.ABANDONED
            return proc

    # ── Read API ────────────────────────────────────────────────────────

    def list_all(self) -> list[AutonomousProcess]:
        with self._lock:
            return list(self._items.values())

    def list_active(self) -> list[AutonomousProcess]:
        with self._lock:
            return [
                p for p in self._items.values()
                if p.status in (AutonomyStatus.PENDING, AutonomyStatus.RUNNING, AutonomyStatus.READY_FOR_PATRYK)
            ]

    def get(self, proc_id: str) -> Optional[AutonomousProcess]:
        with self._lock:
            return self._items.get(proc_id)

    # ── helpers ─────────────────────────────────────────────────────────

    def _must_get(self, proc_id: str) -> AutonomousProcess:
        proc = self._items.get(proc_id)
        if proc is None:
            raise KeyError(f"autonomy: nie znam procesu {proc_id}")
        return proc


_registry_singleton: Optional[AutonomyRegistry] = None
_registry_lock = threading.Lock()


def get_autonomy_registry() -> AutonomyRegistry:
    """Singleton — jeden rejestr na proces serwera."""
    global _registry_singleton
    if _registry_singleton is None:
        with _registry_lock:
            if _registry_singleton is None:
                _registry_singleton = AutonomyRegistry()
    return _registry_singleton


__all__ = [
    "AutonomousProcess",
    "AutonomyRegistry",
    "AutonomyStatus",
    "MAX_AUTONOMOUS_PROCESSES",
    "get_autonomy_registry",
    "patryk_compliance_check",
]
