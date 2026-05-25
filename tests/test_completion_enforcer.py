"""
Testy AKSJOMATU 2 — Doprowadzanie Projektów Do Końca.

Sprawdzają:
1. assert_full_functionality: 422 gdy choć 1 pozycja niezahaczona.
2. assert_full_functionality: passuje gdy 100%.
3. enforce_active_project_limit: blokuje przy limit reached.
4. enforce_active_project_limit: pozwala gdy attempting_new_project=False.
5. validate_archive_reason: 422 gdy < MIN_ARCHIVE_REASON_LEN.
6. validate_archive_reason: passuje gdy reason dostatecznie długi.
7. classify_stale_status: prawidłowa klasyfikacja AT_RISK / STUCK.
8. require_completion_audit: 422 gdy brak / niepełne; passuje gdy OK.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.completion_enforcer import (
    AGENT_COMPLETION_POSTSCRIPT,
    CompletionViolation,
    FunctionalityItem,
    MAX_ACTIVE_PROJECTS,
    MIN_ARCHIVE_REASON_LEN,
    Project,
    ProjectStatus,
    STALE_DAYS_AT_RISK,
    STALE_DAYS_STUCK,
    assert_full_functionality,
    classify_stale_status,
    enforce_active_project_limit,
    extract_completion_audit_from_prose,
    require_completion_audit,
    validate_archive_reason,
    validate_syez_prose_completion_audit,
)


def _proj(items_done: list[bool], **kwargs) -> Project:
    return Project(
        id=kwargs.get("id", 1),
        dream_id=kwargs.get("dream_id", "dream-1"),
        status=kwargs.get("status", ProjectStatus.IN_PROGRESS),
        started_at=kwargs.get("started_at"),
        last_progress_at=kwargs.get("last_progress_at"),
        functionality=[
            FunctionalityItem(description=f"item {i}", is_done=done)
            for i, done in enumerate(items_done)
        ],
    )


# ── assert_full_functionality ───────────────────────────────────────────────


def test_assert_full_functionality_blocks_when_incomplete():
    p = _proj([True, True, False])
    with pytest.raises(CompletionViolation) as exc:
        assert_full_functionality(p)
    assert exc.value.kind == "incomplete_functionality"
    assert "item 2" in str(exc.value.details["remaining"])


def test_assert_full_functionality_passes_when_complete():
    p = _proj([True, True, True])
    # nie powinno rzucić
    assert_full_functionality(p)


def test_assert_full_functionality_blocks_empty_checklist():
    p = Project(id=1, dream_id="d", status=ProjectStatus.IN_PROGRESS, functionality=[])
    with pytest.raises(CompletionViolation) as exc:
        assert_full_functionality(p)
    assert exc.value.kind == "empty_functionality_checklist"


# ── enforce_active_project_limit ────────────────────────────────────────────


def test_active_project_limit_blocks_when_at_limit():
    active = [
        Project(id=i, dream_id=f"d{i}", status=ProjectStatus.IN_PROGRESS)
        for i in range(MAX_ACTIVE_PROJECTS)
    ]
    with pytest.raises(CompletionViolation) as exc:
        enforce_active_project_limit(active, attempting_new_project=True)
    assert exc.value.kind == "active_project_limit"
    assert len(exc.value.details["active_projects"]) == MAX_ACTIVE_PROJECTS


def test_active_project_limit_allows_when_below():
    active = [
        Project(id=1, dream_id="d1", status=ProjectStatus.IN_PROGRESS),
    ]
    enforce_active_project_limit(active, attempting_new_project=True, limit=3)


def test_active_project_limit_allows_when_not_attempting_new():
    active = [
        Project(id=i, dream_id=f"d{i}", status=ProjectStatus.IN_PROGRESS)
        for i in range(MAX_ACTIVE_PROJECTS + 5)
    ]
    # gdy nie startujemy nowego — nie ma walidacji
    enforce_active_project_limit(active, attempting_new_project=False)


def test_terminal_projects_dont_count_to_limit():
    active = [
        Project(id=i, dream_id=f"d{i}", status=ProjectStatus.COMPLETED)
        for i in range(MAX_ACTIVE_PROJECTS + 2)
    ]
    enforce_active_project_limit(active, attempting_new_project=True)  # OK


# ── validate_archive_reason ─────────────────────────────────────────────────


def test_archive_reason_too_short_rejected():
    with pytest.raises(CompletionViolation) as exc:
        validate_archive_reason("za krótko")
    assert exc.value.kind == "archive_reason_too_short"


def test_archive_reason_passes_when_long_enough():
    reason = "x" * MIN_ARCHIVE_REASON_LEN
    assert validate_archive_reason(reason) == reason


# ── classify_stale_status ───────────────────────────────────────────────────


def _ago_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def test_classify_in_progress_recent():
    p = _proj([False], status=ProjectStatus.IN_PROGRESS, last_progress_at=_ago_iso(2))
    assert classify_stale_status(p) == ProjectStatus.IN_PROGRESS


def test_classify_at_risk_after_threshold():
    p = _proj(
        [False],
        status=ProjectStatus.IN_PROGRESS,
        last_progress_at=_ago_iso(STALE_DAYS_AT_RISK + 1),
    )
    assert classify_stale_status(p) == ProjectStatus.AT_RISK


def test_classify_stuck_after_long_threshold():
    p = _proj(
        [False],
        status=ProjectStatus.AT_RISK,
        last_progress_at=_ago_iso(STALE_DAYS_STUCK + 1),
    )
    assert classify_stale_status(p) == ProjectStatus.STUCK


def test_classify_terminal_unchanged():
    p = _proj([True], status=ProjectStatus.COMPLETED, last_progress_at=_ago_iso(999))
    assert classify_stale_status(p) == ProjectStatus.COMPLETED


# ── require_completion_audit ────────────────────────────────────────────────


def test_require_audit_missing_block():
    with pytest.raises(CompletionViolation) as exc:
        require_completion_audit({"recommendations": ["x"]})
    assert exc.value.kind == "missing_completion_audit"


def test_require_audit_incomplete_keys():
    payload = {
        "completion_audit": {
            "functionality_checklist_remaining": ["a"],
            "blocked_by": [],
            # brak smallest_next_functional_increment
        }
    }
    with pytest.raises(CompletionViolation) as exc:
        require_completion_audit(payload)
    assert exc.value.kind == "incomplete_completion_audit"


def test_require_audit_empty_next_increment():
    payload = {
        "completion_audit": {
            "functionality_checklist_remaining": ["a"],
            "blocked_by": ["b"],
            "smallest_next_functional_increment": "",
        }
    }
    with pytest.raises(CompletionViolation) as exc:
        require_completion_audit(payload)
    assert exc.value.kind == "empty_next_increment"


def test_require_audit_passes_when_complete():
    payload = {
        "completion_audit": {
            "functionality_checklist_remaining": ["pozostała pozycja 1"],
            "blocked_by": ["brak konkretnego next move"],
            "smallest_next_functional_increment": (
                "Zapisz pierwsze 3 zdania do README projektu w 15 minut."
            ),
        }
    }
    audit = require_completion_audit(payload)
    assert audit["smallest_next_functional_increment"].startswith("Zapisz")


def test_validate_prose_audit_passes_with_signals():
    text = (
        "Krótka synteza. Na checklistie funkcjonalności zostały jeszcze dwie pozycje. "
        "Pierwszą blokuje brak decyzji o kolorystyce. Najmniejszy konkretny ruch "
        "na dziś to przygotować jeden szkic widoku w 45 minut. Domykamy audyt."
        " Co jest dla Ciebie najcięższe w tym kroku? Jak zmienia się priorytet?"
    )
    validate_syez_prose_completion_audit(text)


def test_validate_prose_audit_rejects_short():
    with pytest.raises(CompletionViolation) as exc:
        validate_syez_prose_completion_audit("za krótko")
    assert exc.value.kind == "prose_audit_too_short"


def test_validate_prose_audit_rejects_weak_signals():
    junk = ("Powtarzam neutralny akapit bez technicznych haczyków. ") * 12
    with pytest.raises(CompletionViolation) as exc:
        validate_syez_prose_completion_audit(junk)
    assert exc.value.kind == "prose_audit_signals_weak"


def test_extract_audit_from_prose_shapes_dict():
    t = (
        "Checklista nadal ma pozycję logowania użytkownika. Blokuje mnie brak kluczy API. "
        "Dziś zrobię w ciągu 60 min testowy endpoint health."
    )
    d = extract_completion_audit_from_prose(t)
    assert set(d.keys()) == {
        "functionality_checklist_remaining",
        "blocked_by",
        "smallest_next_functional_increment",
    }
def test_validate_prose_audit_passes_poetic_wording():
    text = (
        "Elementów domknięcia przybywa wolno: ścieżka zaproszeń wciąż stoi w kolejce. "
        "Napina się wewnętrzny opór przed pokazaniem półdziałającego panelu. "
        "Micro-krok na dziś — wyślij jeden szkic i poproś o jedno zdanie zwrotnej informacji. "
        "To nie sprint; to odblokowanie pierwszej pętli feedbacku. "
        "Jak oceniasz koszt emocjonalny pokazania niedoskonałości? Co by zmieniło Twoją decyzję?"
    )
    validate_syez_prose_completion_audit(text)


# ── Postscriptum jest niepuste i wbite do BaseAgent ────────────────────────


def test_postscript_non_empty_and_contains_principles():
    assert AGENT_COMPLETION_POSTSCRIPT
    p = AGENT_COMPLETION_POSTSCRIPT
    assert "ARCHITEKTA WOLNOŚCI" in p
    assert "functionality_checklist" in p
    assert "porzuc" in p.lower() or "porzucania" in p
