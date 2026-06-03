"""Mechanizm Autonomii Rady — rejestr in-memory (core/autonomy.py)."""

from __future__ import annotations

import pytest

from core.autonomy import (
    AutonomyRegistry,
    AutonomyStatus,
    MAX_AUTONOMOUS_PROCESSES,
)


@pytest.fixture
def registry() -> AutonomyRegistry:
    return AutonomyRegistry(limit=MAX_AUTONOMOUS_PROCESSES)


def test_open_process_appears_in_list(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Test autonomii", triggered_by="patryk")
    assert proc.status == AutonomyStatus.PENDING
    assert proc.title == "Test autonomii"
    assert registry.get(proc.id) is proc
    assert len(registry.list_all()) == 1


def test_open_respects_concurrent_limit(registry: AutonomyRegistry) -> None:
    for i in range(MAX_AUTONOMOUS_PROCESSES):
        registry.open(title=f"proc-{i}")
    with pytest.raises(RuntimeError, match="limit"):
        registry.open(title="one too many")


def test_attach_proposals_marks_ready(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Propozycje")
    updated = registry.attach_proposals(
        proc.id,
        [{"text": "Spokojny następny krok bez sprintu."}],
    )
    assert updated.status == AutonomyStatus.READY_FOR_PATRYK
    assert len(updated.proposals) == 1
    assert updated.proposals[0]["_compliance"]["passes"] is True


def test_attach_proposals_rejected_by_axiom_3(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Odrzucone")
    updated = registry.attach_proposals(
        proc.id,
        [{"text": "Po prostu zapomnij o sobie i rób cokolwiek."}],
    )
    assert updated.status == AutonomyStatus.REJECTED_BY_AXIOM_3
    assert updated.compliance_warnings


def test_attach_proposals_caps_at_three(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Max 3")
    props = [{"text": f"Propozycja {i}."} for i in range(5)]
    updated = registry.attach_proposals(proc.id, props)
    assert len(updated.proposals) == 3


def test_mark_done_keeps_chosen_proposal(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Wybór")
    registry.attach_proposals(
        proc.id,
        [{"text": "A"}, {"text": "B"}],
    )
    done = registry.mark_done(proc.id, chosen_index=1)
    assert done.status == AutonomyStatus.DONE
    assert len(done.proposals) == 1
    assert done.proposals[0]["text"] == "B"


def test_mark_done_wrong_status_raises(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Za wcześnie")
    with pytest.raises(RuntimeError, match="nie jest gotowy"):
        registry.mark_done(proc.id, chosen_index=0)


def test_mark_done_invalid_index_raises(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Index")
    registry.attach_proposals(proc.id, [{"text": "Jedyna"}])
    with pytest.raises(ValueError, match="poza zakresem"):
        registry.mark_done(proc.id, chosen_index=3)


def test_abandon_requires_long_reason(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Porzucenie")
    with pytest.raises(ValueError, match="≥50"):
        registry.abandon(proc.id, reason="za krótko")


def test_abandon_success(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Porzucenie OK")
    reason = "x" * 50
    abandoned = registry.abandon(proc.id, reason=reason)
    assert abandoned.status == AutonomyStatus.ABANDONED
    assert abandoned.abandon_reason == reason


def test_get_unknown_raises(registry: AutonomyRegistry) -> None:
    with pytest.raises(KeyError, match="nie znam procesu"):
        registry.attach_proposals("missing-id", [{"text": "x"}])


def test_list_active_excludes_done(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Aktywny")
    registry.attach_proposals(proc.id, [{"text": "OK"}])
    registry.mark_done(proc.id, chosen_index=0)
    assert registry.list_active() == []


def test_to_payload_roundtrip_fields(registry: AutonomyRegistry) -> None:
    proc = registry.open(title="Payload", triggered_by="ritual_daily")
    payload = proc.to_payload()
    assert payload["id"] == proc.id
    assert payload["triggered_by"] == "ritual_daily"
    assert payload["status"] == AutonomyStatus.PENDING.value
