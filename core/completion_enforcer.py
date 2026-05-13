"""
AKSJOMAT 2 — Doprowadzanie Projektów Do Końca.

Drugi pierwotny sens Architekta Wolności: bezwzględnie kończyć projekty
w PEŁNI FUNKCJONALNYM stanie. „Zaczęte i porzucone” to choroba, którą
ten system ma leczyć.

Ten moduł NIE jest doradcą — to egzekutor. Jego rolą jest:
1. Wymuszać limit jednoczesnych aktywnych projektów (`MAX_ACTIVE_PROJECTS`).
2. Wymagać `functionality_checklist` 100% przed oznaczeniem projektu jako COMPLETED.
3. Wymuszać uzasadnienie archiwizacji (świadome odpuszczenie, nie porzucenie).
4. Wymuszać obecność audytu domknięcia w syntezie Syeza (historycznie pole
   JSON `completion_audit`; obecnie — ta sama treść logiczna wyrażona prozą).
5. Klasyfikować projekty jako AT_RISK / STUCK po przerwach w postępie.

Każda funkcja, która coś egzekwuje, podnosi `CompletionViolation` z czytelną
informacją — backend mapuje to na HTTP 409/422, a UI pokazuje konfrontację
w stylu „kończysz X / archiwizujesz świadomie X”.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ── Konfiguracja (env-driven, bo Patryk może chcieć tuningować) ─────────────


def _env_int(name: str, default: int) -> int:
    try:
        v = os.getenv(name)
        return int(v) if v is not None else default
    except ValueError:
        logger.warning("ENV %s ma nieliczbową wartość — używam default=%s", name, default)
        return default


MAX_ACTIVE_PROJECTS: int = _env_int("MAX_ACTIVE_PROJECTS", 3)
STALE_DAYS_AT_RISK: int = _env_int("STALE_DAYS_AT_RISK", 14)
STALE_DAYS_STUCK: int = _env_int("STALE_DAYS_STUCK", 30)
MIN_ARCHIVE_REASON_LEN: int = _env_int("MIN_ARCHIVE_REASON_LEN", 50)


# ── Maszyna stanów ──────────────────────────────────────────────────────────


class ProjectStatus(str, Enum):
    """
    Legalne stany projektu w Architekcie Wolności.

    UWAGA: stan ABANDONED (porzucony) NIE ISTNIEJE. Każde wyjście wymaga
    świadomej archiwizacji z uzasadnieniem.
    """

    DREAMING = "dreaming"
    IN_PROGRESS = "in_progress"
    AT_RISK = "at_risk"
    STUCK = "stuck"
    COMPLETED = "completed"
    ARCHIVED_CONSCIOUSLY = "archived_consciously"


ACTIVE_STATUSES: frozenset[ProjectStatus] = frozenset(
    {
        ProjectStatus.DREAMING,
        ProjectStatus.IN_PROGRESS,
        ProjectStatus.AT_RISK,
        ProjectStatus.STUCK,
    }
)

TERMINAL_STATUSES: frozenset[ProjectStatus] = frozenset(
    {ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED_CONSCIOUSLY}
)


def is_active(status: ProjectStatus | str) -> bool:
    if isinstance(status, str):
        status = ProjectStatus(status)
    return status in ACTIVE_STATUSES


# ── Modele domenowe ─────────────────────────────────────────────────────────


class FunctionalityItem(BaseModel):
    """Pojedyncza pozycja `functionality_checklist` z trackingiem ukończenia."""

    id: Optional[int] = None
    project_id: Optional[int] = None
    description: str = Field(..., min_length=3)
    is_done: bool = False
    done_at: Optional[str] = None  # ISO datetime
    evidence_url: Optional[str] = None


class Project(BaseModel):
    """Projekt — instancja realizacji marzenia."""

    id: Optional[int] = None
    dream_id: str
    status: ProjectStatus = ProjectStatus.DREAMING
    started_at: Optional[str] = None
    last_progress_at: Optional[str] = None
    completed_at: Optional[str] = None
    archived_reason: Optional[str] = None
    archived_at: Optional[str] = None
    functionality: list[FunctionalityItem] = Field(default_factory=list)

    def completion_ratio(self) -> float:
        if not self.functionality:
            return 0.0
        done = sum(1 for f in self.functionality if f.is_done)
        return done / len(self.functionality)

    def remaining_items(self) -> list[FunctionalityItem]:
        return [f for f in self.functionality if not f.is_done]

    def days_since_progress(self, *, now: Optional[datetime] = None) -> Optional[int]:
        ref = self.last_progress_at or self.started_at
        if not ref:
            return None
        now = now or datetime.now(timezone.utc)
        try:
            ref_dt = datetime.fromisoformat(ref.replace("Z", "+00:00"))
        except ValueError:
            return None
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=timezone.utc)
        return (now - ref_dt).days


class CompletionAudit(BaseModel):
    """
    Migawka audytu funkcjonalności wykonana przez Syeza w danej debacie.

    `remaining_json` zawiera słownik z polami:
      - functionality_checklist_remaining: list[str]
      - blocked_by: list[str]
      - smallest_next_functional_increment: str
    """

    id: Optional[int] = None
    project_id: int
    debate_id: Optional[int] = None
    remaining_json: dict[str, Any]
    audited_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Wyjątki ─────────────────────────────────────────────────────────────────


class CompletionViolation(Exception):
    """
    Naruszenie zasad AKSJOMATU 2.

    Atrybuty:
      kind: typ naruszenia (do mapowania na HTTP / UX)
      details: dict z kontekstem (zawiera dane potrzebne UI do podjęcia decyzji)
    """

    def __init__(self, kind: str, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.kind = kind
        self.details = details or {}

    def to_payload(self) -> dict[str, Any]:
        return {"kind": self.kind, "message": str(self), "details": self.details}


# ── Reguły egzekwujące ──────────────────────────────────────────────────────


def assert_full_functionality(project: Project) -> None:
    """
    Reguła „Funkcjonalność = warunek konieczny”.

    Pozwala oznaczyć projekt jako COMPLETED tylko wtedy, gdy KAŻDA pozycja
    `functionality_checklist` jest odhaczona. Inaczej → `CompletionViolation`.
    """
    if not project.functionality:
        raise CompletionViolation(
            kind="empty_functionality_checklist",
            message=(
                "AKSJOMAT 2: Projekt nie ma functionality_checklist. "
                "Bez definicji 'co musi działać' nie można uznać projektu za skończony."
            ),
            details={"project_id": project.id, "dream_id": project.dream_id},
        )
    remaining = project.remaining_items()
    if remaining:
        raise CompletionViolation(
            kind="incomplete_functionality",
            message=(
                f"AKSJOMAT 2: Pozostało {len(remaining)} pozycji do odhaczenia. "
                f"Projekt NIE może być oznaczony jako COMPLETED, dopóki "
                f"functionality_checklist nie jest 100%."
            ),
            details={
                "project_id": project.id,
                "remaining": [r.description for r in remaining],
                "ratio": project.completion_ratio(),
            },
        )


def enforce_active_project_limit(
    existing_projects: Iterable[Project],
    *,
    attempting_new_project: bool = True,
    limit: int = MAX_ACTIVE_PROJECTS,
) -> None:
    """
    Reguła „Najpierw kończ”.

    Jeśli próbujemy startować nowy projekt, a aktywnych jest już `limit` —
    `CompletionViolation` z listą aktywnych projektów. UI musi zmusić Patryka
    do decyzji „kończysz X / archiwizujesz świadomie X / wracasz”.
    """
    if not attempting_new_project:
        return
    active = [p for p in existing_projects if is_active(p.status)]
    if len(active) >= limit:
        raise CompletionViolation(
            kind="active_project_limit",
            message=(
                f"AKSJOMAT 2: masz już {len(active)} aktywnych projektów "
                f"(limit: {limit}). Najpierw skończ albo świadomie zarchiwizuj jeden."
            ),
            details={
                "limit": limit,
                "active_projects": [
                    {
                        "id": p.id,
                        "dream_id": p.dream_id,
                        "status": p.status.value,
                        "completion_ratio": round(p.completion_ratio(), 2),
                        "days_since_progress": p.days_since_progress(),
                    }
                    for p in active
                ],
            },
        )


def classify_stale_status(
    project: Project,
    *,
    now: Optional[datetime] = None,
) -> ProjectStatus:
    """
    Reguła „Brak ruchu = konfrontacja”.

    Mapuje projekt na status na podstawie dni od ostatniego postępu.
    Czysta funkcja — nie modyfikuje stanu, zwraca rekomendowany status.

    - 0–STALE_DAYS_AT_RISK dni: zachowuje istniejący aktywny status.
    - STALE_DAYS_AT_RISK..STALE_DAYS_STUCK dni: AT_RISK.
    - > STALE_DAYS_STUCK dni: STUCK.
    """
    if project.status in TERMINAL_STATUSES:
        return project.status
    days = project.days_since_progress(now=now)
    if days is None:
        return project.status
    if days >= STALE_DAYS_STUCK:
        return ProjectStatus.STUCK
    if days >= STALE_DAYS_AT_RISK:
        return ProjectStatus.AT_RISK
    return project.status if is_active(project.status) else ProjectStatus.IN_PROGRESS


def validate_archive_reason(reason: Optional[str]) -> str:
    """
    Reguła „Świadoma archiwizacja, nie ciche porzucenie”.

    Wymaga uzasadnienia o min. `MIN_ARCHIVE_REASON_LEN` znaków. Zwraca
    oczyszczone uzasadnienie lub podnosi `CompletionViolation`.
    """
    text = (reason or "").strip()
    if len(text) < MIN_ARCHIVE_REASON_LEN:
        raise CompletionViolation(
            kind="archive_reason_too_short",
            message=(
                f"AKSJOMAT 2: archiwizacja projektu wymaga uzasadnienia "
                f"min. {MIN_ARCHIVE_REASON_LEN} znaków. Świadomie odpuszczasz "
                f"— nie po cichu znikasz."
            ),
            details={"min_length": MIN_ARCHIVE_REASON_LEN, "got": len(text)},
        )
    return text


# ── Audyt domknięcia w syntezie Syeza (AKSJOMAT 2) ─────────────────────────


SYEZ_AKSJOMAT2_PROSE_APPEND: str = """
PROTOKÓŁ AKSJOMATU 2 (Doprowadzanie Projektów Do Końca):
W swojej syntezie ZAWSZE — naturalnym językiem, wplecionym w prozę — powiedz wprost:
  1) Co konkretnie zostało jeszcze do odhaczenia z functionality_checklist
     (jeśli marzenie ma checklistę).
  2) Co blokuje pierwszą zaległą pozycję.
  3) Jaki jest najmniejszy konkretny ruch (do 60 minut), po którym przybywa
     jedna odhaczona pozycja.
Te trzy rzeczy mają być POWIEDZIANE — nie wypisane jako JSON, nie ukryte
w bloku kodu. Bez nich synteza jest niekompletna.
""".strip()


# Legacy alias — treść identyczna z prozą (nie JSON).
SYEZ_COMPLETION_AUDIT_REQUIREMENT: str = SYEZ_AKSJOMAT2_PROSE_APPEND


PROSE_AUDIT_MIN_CHARS: int = 200

# Trzy klastry sygnałów audytu (proza, bez NLP). Celowo szerokie synonimy
# i literackie obejścia — Syez nie musi brzmieć jak backlog Jiry.
_CLUSTER_REM = (
    r"checklist|checklista|funkcjonaln|funkcjonal|"
    r"odhacz|odznacz|do\s+odhaczenia|"
    r"zosta[łl][oa]|pozosta[łl][oa]|"
    r"jeszcze\s+(?:trzeba|mamy|jest|widać|czeka|stoi)|"
    r"do\s+(?:zrobienia|dokończenia|wykonania|domknięcia|ukończenia)|"
    r"pozycj[eęąiu]|"
    r"punkt(?:y|ów)?\s+(?:checklisty|listy|z\s+listy)|"
    r"lista\s+zadań|element(?:ów|y)?\s+(?:do\s+)?(?:domknięcia|ukończenia)|"
    r"niedokończon|nie\s+domknięt|nie\s+zamknięt|nie\s+skończon|"
    r"brakuje\s+(?:nam\s+)?(?:jeszcze\s+)?"
    r"|czego[sś]\s+jeszcze\s+nie\s+ma"
    r"|co\s+jeszcze"
    r"|\btodo\b"
    r"|(?:stoi|czeka|wisi)\s+w\s+kolejce"
    r"|ścieżk[aęą]|moduł[uów]?"
)
_CLUSTER_BLK = (
    r"blokuj|blokuje|blokad|"
    r"hamuje|przeszkadz|nie\s+pozwal"
    r"|powstrzymuj|wstrzymuj"
    r"|(?:wewnętrzn|zewnętrzn)[ya]\s+opór"
    r"|napięci[eę]|napięty"
    r"|trudność|opór"
    r"|lęk|niepewność|obaw"
    r"|brak\s+(?:czasu|energii|decyzji|jasności|informacji|zdolności|zgody)"
    r"|nie\s+wiem\s+jak"
    r"|czego[sś]\s+si[eę]\s+boj[eę]"
    r"|paraliżuj"
    r"|utknął|utknięt|"
    r"zaci[nń]"
    r"|kręci\s+si[eę]\s+w\s+kole"
    r"|nie\s+(?:mogę|potrafię|chce\s+mi\s+si[eę])"
)
_CLUSTER_NEXT = (
    r"najmniejsz"
    r"|micro[-\s]?krok|mały\s+krok"
    r"|(?:60|45|30|20|15)\s*min"
    r"|pół\s+godzin"
    r"|(?:jedna|jeden|pół)\s+godzin"
    r"|\d+\s*min(?:ut)?"
    r"|konkretny\s+(?:ruch|krok)"
    r"|pierwsz(?:y|ą)\s+(?:krok|ruch|rzecz)"
    r"|następn(?:y|ym)|kolejn(?:y|ym)"
    r"|dziś|dzisiaj|jutro"
    r"|w\s+ciągu\s+(?:dnia|tygodnia|najbliższ)"
    r"|ten\s+ruch"
    r"|(?:zacznij|zrób|wykonaj|poświęć|ustaw|napisz|zadzwoń|wyślij|otwórz|"
    r"odeślij|umów)"
    r"|do\s+wieczora|rankiem"
    r"|na\s+start"
    r"|jako\s+pierwsze"
)
_CLUSTER_OPEN = (
    r"\?"
    r"|pytani[eę]|pytam"
    r"|\bczy\b[^\n]{0,120}\?"
    r"|co\s+(?:jeśli|by\s+było|wydaje\s+ci\s+si[eę])"
    r"|jak\s+(?:widzisz|czujesz|oceniasz|rozwiąz|nadajesz)"
    r"|zastanów\s+si[eę]|powiedz\s+sobie"
    r"|jakiego\s+odpowiedzi"
)


def validate_syez_prose_completion_audit(text: str) -> None:
    """
    Sprawdza, że proza Syeza zawiera wyraźne sygnały audytu domknięcia.
    Nie próbuje pełnego NLP — heurystyki pod egzekucję AKSJOMATU 2.
    """
    t = (text or "").strip()
    if len(t) < PROSE_AUDIT_MIN_CHARS:
        raise CompletionViolation(
            kind="prose_audit_too_short",
            message=(
                "AKSJOMAT 2: synteza prozą jest zbyt krótka, by zawierała "
                "pełny audyt domknięcia."
            ),
            details={"min_chars": PROSE_AUDIT_MIN_CHARS, "got": len(t)},
        )
    low = t.lower()
    hits_rem = bool(re.search(_CLUSTER_REM, low))
    hits_blk = bool(re.search(_CLUSTER_BLK, low))
    hits_nxt = bool(re.search(_CLUSTER_NEXT, low))
    hits_open = bool(re.search(_CLUSTER_OPEN, low))
    hits_ok = hits_rem + hits_blk + hits_nxt + hits_open
    if hits_ok < 4:
        raise CompletionViolation(
            kind="prose_audit_signals_weak",
            message=(
                "AKSJOMAT 2 / struktura syntezy: w prozie brakuje wyraźnych "
                "sygnałów audytu (checklista / blokada / następny ruch / "
                "pytania otwarte)."
            ),
            details={
                "clusters_matched": {
                    "remaining": hits_rem,
                    "blocked": hits_blk,
                    "next_move": hits_nxt,
                    "open_questions": hits_open,
                },
                "matched_ok_total": hits_ok,
                "needed_ok_total": 4,
            },
        )


def extract_completion_audit_from_prose(text: str) -> dict[str, Any]:
    """
    Buduje dict pod zapis `completion_audits` — treść pochodzi z prozy
    (zdania-trafienia), żeby SQLite pozostał spójny ze schematem.
    """
    raw = (text or "").strip()
    parts = re.split(r"(?<=[.!?])\s+", raw)
    parts = [p.strip() for p in parts if len(p.strip()) > 8]

    def _pick(pred: Callable[[str], bool]) -> str:
        for p in parts:
            if pred(p.lower()):
                return p
        return ""

    rem = _pick(lambda low: bool(re.search(_CLUSTER_REM, low)))
    blk = _pick(lambda low: bool(re.search(_CLUSTER_BLK, low)))
    inc = _pick(lambda low: bool(re.search(_CLUSTER_NEXT, low)))

    def _fill(val: str, fallback_phrase: str) -> list[str]:
        s = val.strip()
        if len(s) >= 8:
            return [s]
        return [fallback_phrase]

    snfi = inc.strip()
    if len(snfi) < 12:
        snfi = raw[:500].strip()
    if len(snfi) < 12:
        snfi = "(brak — patrz pełna synteza prozą)"

    return {
        "functionality_checklist_remaining": _fill(
            rem, "(szczegóły checklisty — patrz synteza prozą)"
        ),
        "blocked_by": _fill(blk, "(szczegóły blokady — patrz synteza prozą)"),
        "smallest_next_functional_increment": snfi[:1200],
    }

_REQUIRED_AUDIT_KEYS: frozenset[str] = frozenset(
    {
        "functionality_checklist_remaining",
        "blocked_by",
        "smallest_next_functional_increment",
    }
)


def require_completion_audit(synthesis_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Waliduje, że strukturyzowana synteza Syeza zawiera kompletne pole
    `completion_audit`. Zwraca to pole (do zapisu w `completion_audits`)
    albo podnosi `CompletionViolation` — orkiestrator wtedy re-promptuje Syeza.
    """
    audit = synthesis_payload.get("completion_audit")
    if not isinstance(audit, dict):
        raise CompletionViolation(
            kind="missing_completion_audit",
            message="AKSJOMAT 2: synteza Syeza nie zawiera pola `completion_audit`.",
            details={"received_keys": list(synthesis_payload.keys())},
        )
    missing = _REQUIRED_AUDIT_KEYS - set(audit.keys())
    if missing:
        raise CompletionViolation(
            kind="incomplete_completion_audit",
            message=f"AKSJOMAT 2: completion_audit ma brakujące pola: {sorted(missing)}.",
            details={"missing": sorted(missing), "got": list(audit.keys())},
        )
    # Sanity: smallest_next_functional_increment nie może być pusty / ogólnikowy.
    snfi = (audit.get("smallest_next_functional_increment") or "").strip()
    if len(snfi) < 10:
        raise CompletionViolation(
            kind="empty_next_increment",
            message=(
                "AKSJOMAT 2: `smallest_next_functional_increment` jest pusty albo "
                "zbyt ogólny — musi być konkretnym ruchem do 60 minut."
            ),
            details={"value": snfi},
        )
    return audit


# ── Postscriptum wstrzykiwane w prompt każdego agenta ───────────────────────


AGENT_COMPLETION_POSTSCRIPT: str = """

═══ ZASADA NADRZĘDNA ARCHITEKTA WOLNOŚCI (dotyczy KAŻDEGO agenta Rady) ═══

1. Pierwotnym sensem tego systemu jest tworzenie architektury do spełniania
   marzeń ORAZ bezwzględne doprowadzanie projektów do końca w pełni
   funkcjonalnym stanie.

2. Nigdy nie sugeruj „odłożenia na później” bez jawnego warunku powrotu
   (konkretna data + trigger). „Wrócimy do tego” bez warunku = porzucenie.

3. Każda Twoja sugestia ma albo (a) przybliżać do odhaczenia pozycji z
   functionality_checklist marzenia, albo (b) świadomie redefiniować, co
   znaczy „skończone” dla tego marzenia.

4. Jeśli widzisz w briefie wzorzec porzucania (chroniczne zaczynanie bez
   kończenia) — nazwij go wprost. Patryk świadomie zbudował ten system po to,
   żeby Rada nie była grzeczna w tej sprawie.

5. Nie produkuj długich list opcji bez priorytetyzacji. Lepiej jedno
   konkretne, najmniejsze możliwe „zrób X do Y”, niż dziesięć możliwości.
═══════════════════════════════════════════════════════════════════════════
"""
