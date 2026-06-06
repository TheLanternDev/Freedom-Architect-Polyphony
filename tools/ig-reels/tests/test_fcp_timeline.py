"""Weryfikacja matematyki timeline FCP (9 agentów + Syez + closing)."""

from __future__ import annotations

from pathlib import Path

from aw_reels.fcp_export import (
    FcpTimelineSpec,
    build_agent_slots,
    load_timeline_spec,
    syez_start_s,
)

FIXTURES = Path(__file__).resolve().parent


def _nine_agents() -> list[dict]:
    return [{"id": f"A{i}", "file": f"a{i}.png"} for i in range(1, 10)]


def test_timeline_spec_from_yaml() -> None:
    spec = load_timeline_spec()
    assert spec.total_s == 24.5
    assert spec.opening_s == 3.2
    assert spec.syez_s == 4.5
    assert spec.closing_s == 3.0


def test_agent_slot_duration_at_24_5s() -> None:
    spec = FcpTimelineSpec(
        title="test",
        width=1080,
        height=1920,
        fps=30,
        total_s=24.5,
        opening_s=3.2,
        syez_s=4.5,
        closing_s=3.0,
    )
    slots = build_agent_slots(_nine_agents(), spec, FIXTURES)
    assert len(slots) == 9
    expected_each = 13.8 / 9
    for slot in slots:
        assert abs(slot.duration_s - expected_each) < 0.001


def test_segment_sum_equals_total() -> None:
    spec = FcpTimelineSpec(
        title="test",
        width=1080,
        height=1920,
        fps=30,
        total_s=24.5,
        opening_s=3.2,
        syez_s=4.5,
        closing_s=3.0,
    )
    slots = build_agent_slots(_nine_agents(), spec, FIXTURES)
    agent_total = sum(s.duration_s for s in slots)
    total = spec.opening_s + agent_total + spec.syez_s + spec.closing_s
    assert abs(total - spec.total_s) < 0.01


def test_syez_start_after_all_agents() -> None:
    spec = FcpTimelineSpec(
        title="test",
        width=1080,
        height=1920,
        fps=30,
        total_s=24.5,
        opening_s=3.2,
        syez_s=4.5,
        closing_s=3.0,
    )
    slots = build_agent_slots(_nine_agents(), spec, FIXTURES)
    assert abs(syez_start_s(spec, len(slots)) - 17.0) < 0.01
    assert abs(slots[-1].start_s + slots[-1].duration_s - 17.0) < 0.01
