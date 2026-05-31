"""Testy `core.debate_export.render_debate_markdown` i `_structured_block`.

Funkcje pure — render → string. Łatwo testowalne bez DB.
"""

from __future__ import annotations

from core.debate_export import _structured_block, render_debate_markdown


def test_structured_block_handles_empty_dict():
    """Pusty dict → tylko sekcja `Full structured (JSON)`, bez nagłówków sekcji."""
    out = _structured_block({})
    assert "Full structured (JSON)" in out
    assert "{}" in out
    # Brak konkretnych sekcji bo żadne pole nie istnieje.
    assert "Perspectives overview" not in out
    assert "Tensions" not in out


def test_structured_block_renders_insights_per_agent():
    out = _structured_block({
        "insights_per_agent": [
            {"agent": "Kogit", "insight": "Założenie X jest odziedziczone."},
            {"agent": "Szow", "insight": "Wymówka."},
        ]
    })
    assert "Perspectives overview" in out
    assert "**Kogit**" in out
    assert "Założenie X" in out
    assert "**Szow**" in out


def test_structured_block_skips_non_dict_rows():
    """Niezgodne typy (str zamiast dict) muszą być przeskoczone bez błędu."""
    out = _structured_block({
        "insights_per_agent": ["broken", {"agent": "Kidi", "insight": "Pytanie."}],
    })
    assert "Kidi" in out


def test_structured_block_tensions_with_between_list():
    out = _structured_block({
        "tensions": [{"between": ["Kogit", "Szow"], "why": "konflikt założeń"}]
    })
    assert "Kogit ↔ Szow" in out
    assert "konflikt założeń" in out


def test_structured_block_tensions_fallback_when_between_missing():
    out = _structured_block({"tensions": [{"why": "x"}]})
    assert "?" in out and "x" in out


def test_structured_block_recommendations_open_questions_action_steps():
    out = _structured_block({
        "recommendations": ["zrób A", "zrób B"],
        "open_questions": ["co jeśli X?"],
        "action_steps": [
            {"step": "wyślij email", "due": "2026-06-01"},
            {"step": "brak due"},  # bez due
            "nie-dict",            # ignorowany
        ],
    })
    assert "Recommendations" in out
    assert "1. zrób A" in out
    assert "Open questions" in out
    assert "co jeśli X?" in out
    assert "Action steps" in out
    assert "wyślij email" in out
    assert "(due: 2026-06-01)" in out
    assert "brak due" in out


def test_structured_block_commitments_with_follow_up():
    out = _structured_block({
        "commitments": [
            {"text": "umów rozmowę", "follow_up_at": "2026-06-05"},
            {"text": "brak follow-up"},
            "ignored",
        ]
    })
    assert "Commitments (from the synthesis)" in out
    assert "umów rozmowę" in out
    assert "follow-up: 2026-06-05" in out
    assert "brak follow-up" in out


def test_structured_block_completion_audit_full():
    out = _structured_block({
        "completion_audit": {
            "functionality_checklist_remaining": ["pos. 3", "pos. 7"],
            "blocked_by": ["brak decyzji"],
            "smallest_next_functional_increment": "Napisz mail w 30 min",
        }
    })
    assert "Functionality audit" in out
    assert "pos. 3; pos. 7" in out
    assert "brak decyzji" in out
    assert "Napisz mail w 30 min" in out


def test_structured_block_completion_audit_fallback_when_lists_missing():
    out = _structured_block({"completion_audit": {}})
    assert "Functionality audit" in out
    assert "—" in out


# ── render_debate_markdown ──────────────────────────────────────────────────


def test_render_returns_minimum_skeleton_with_no_voices_no_commitments():
    out = render_debate_markdown(
        debate={"id": 42, "created_at": "2026-05-01", "category": "personal",
                "mode": "pelna", "brief_description": "brief X"},
        voices=[],
        commitments=[],
        synthesis_text="",
        structured=None,
    )
    assert "# Architekt Wolności — debata #42" in out
    assert "brief X" in out
    assert "_(brak zapisanych głosów)_" in out
    assert "_(brak)_" in out  # pusta synteza
    assert "## Synteza — struktura" not in out  # brak structured


def test_render_includes_voices_and_commitments_and_structured():
    out = render_debate_markdown(
        debate={
            "id": 7, "created_at": "2026-05-01", "category": "personal",
            "mode": "pelna", "brief_description": "B", "intention": "I",
            "extra_context": "C", "dream_id": "d-1",
        },
        voices=[
            {"agent_name": "Kogit", "voice_text": "  observation  "},
            {"agent_name": "Szow", "voice_text": "konfrontacja"},
        ],
        commitments=[
            {"id": 1, "status": "open", "text": "umów rozmowę"},
            {"id": 2, "status": "done", "text": "zapisz brief"},
        ],
        synthesis_text="  prozaiczna synteza  ",
        structured={"recommendations": ["zrób X"]},
    )
    assert "**dream_id:** d-1" in out
    assert "### Intencja" in out
    assert "### Dodatkowy kontekst" in out
    assert "### Kogit" in out and "observation" in out  # strip
    assert "### Szow" in out
    assert "[open] #1 — umów rozmowę" in out
    assert "[done] #2 — zapisz brief" in out
    assert "prozaiczna synteza" in out
    assert "## Synteza — struktura" in out
    assert "1. zrób X" in out


def test_render_handles_missing_dream_id_with_dash():
    out = render_debate_markdown(
        debate={"id": 1, "brief_description": "b"},
        voices=[], commitments=[], synthesis_text="", structured=None,
    )
    assert "**dream_id:** —" in out
