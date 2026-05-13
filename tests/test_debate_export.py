"""Unit: render_debate_markdown (P6)."""

from core.debate_export import render_debate_markdown


def test_render_minimal():
    md = render_debate_markdown(
        {
            "id": 1,
            "created_at": "2026-01-01",
            "category": "decyzja",
            "mode": "pelna",
            "dream_id": None,
            "brief_description": "X brief.",
        },
        [],
        [],
        "Synth line",
        None,
    )
    assert "# Architekt Wolności — debata #1" in md
    assert "Synth line" in md
