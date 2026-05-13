"""
Testy AKSJOMATU 1 — Architektura Marzenia.

Sprawdzają:
1. Fallback deterministyczny (bez LLM) zwraca pełny `DreamArchitecture`
   ze wszystkimi 7 wymaganymi polami i NIEPUSTĄ functionality_checklist.
2. Walidatory Pydantica odrzucają niespójne payloady (puste filary, pusty
   functionality_checklist, niepoprawne daty milestones).
3. `as_agent_context()` zawiera słowa-klucze niezbędne dla Rady (core_dream,
   functionality_checklist, AKSJOMAT 2).
4. `for_syez()` to poprawny JSON parsowalny z powrotem.
"""

import json

import pytest

from core.dream_architect import (
    DreamArchitecture,
    Milestone,
    NextMove,
    _balanced_json_object_slice,
    _parse_llm_json_object,
    distill_dream,
)


def test_fallback_dream_has_all_required_fields():
    brief = "Chcę dokończyć aplikację SoberSteps i wydać ją w App Store w 6 tygodni."
    dream = distill_dream(brief)

    assert dream.dream_id, "dream_id musi być wypełnione"
    assert dream.core_dream, "core_dream musi być wypełnione"
    assert dream.value_anchor, "value_anchor musi być wypełnione"
    assert 3 <= len(dream.pillars) <= 7, "pillars 3–7"
    assert dream.milestones, "milestones nie może być puste"
    assert dream.next_move.action
    assert dream.completion_criteria
    assert dream.functionality_checklist, (
        "AKSJOMAT 2: functionality_checklist nie może być pusta"
    )


def test_fallback_dream_is_cached_per_brief():
    brief = "Drugi test — identyczny brief musi zwrócić identyczny dream_id."
    d1 = distill_dream(brief)
    d2 = distill_dream(brief)
    assert d1.dream_id == d2.dream_id


_VALID_NEXT_MOVE = NextMove(action="zrób pierwszy krok", when="dziś wieczorem")
_VALID_PAYLOAD = {
    "raw_brief": "brief",
    "core_dream": "rdzenne marzenie testowe",
    "value_anchor": "kotwica wartości testowa",
    "pillars": ["filar 1", "filar 2", "filar 3"],
    "next_move": _VALID_NEXT_MOVE,
    "completion_criteria": ["kryterium spełnienia"],
    "functionality_checklist": ["wymóg funkcjonalny"],
}


def test_pillars_below_minimum_rejected():
    payload = {**_VALID_PAYLOAD, "pillars": ["jeden", "dwa"]}
    with pytest.raises(ValueError, match="3–7 filarów"):
        DreamArchitecture(**payload)


def test_empty_functionality_checklist_rejected():
    payload = {**_VALID_PAYLOAD, "functionality_checklist": []}
    with pytest.raises(ValueError, match="functionality_checklist"):
        DreamArchitecture(**payload)


def test_empty_completion_criteria_rejected():
    payload = {**_VALID_PAYLOAD, "completion_criteria": []}
    with pytest.raises(ValueError, match="completion_criterion"):
        DreamArchitecture(**payload)


def test_milestone_invalid_due_rejected():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        Milestone(title="Punkt", due="jutro")


def test_as_agent_context_contains_aksjomat_keywords():
    dream = distill_dream("Brief testowy do sprawdzenia kontekstu agenta.")
    ctx = dream.as_agent_context()
    assert "ARCHITEKTURA MARZENIA" in ctx
    assert "Rdzenne marzenie" in ctx
    assert "AKSJOMAT 2" in ctx
    assert "functionality_checklist" in ctx or "DZIAŁAĆ" in ctx


def test_for_syez_is_valid_json():
    dream = distill_dream("Test serializacji dla Syeza w pełnej postaci.")
    payload = dream.for_syez()
    data = json.loads(payload)
    assert data["dream_id"] == dream.dream_id
    assert data["core_dream"] == dream.core_dream
    assert isinstance(data["functionality_checklist"], list)


def test_balanced_json_slice_keeps_brace_inside_string():
    s = r'{"core_dream": "Uwaga: znak } w cytacie", "n": 1}'
    assert _balanced_json_object_slice(s) == s


def test_balanced_json_slice_first_object_only():
    wrapped = 'Intro ```json\n{"a": 1}\n```\nextra'
    assert _balanced_json_object_slice(wrapped) == '{"a": 1}'


def test_parse_llm_json_trailing_comma_and_fence():
    blob = (
        '{"core_dream":"rdzen marzenia","value_anchor":"kotwica","pillars":["p1","p2","p3"],'
        '"milestones":[],"next_move":{"action":"pierwszy krok","when":"dziś","smallest_form":""},'
        '"completion_criteria":["spełnione"],"functionality_checklist":["działa"],}'
    )
    data = _parse_llm_json_object(f"Preambuła\n```json\n{blob}\n```\nKoniec")
    assert data["core_dream"] == "rdzen marzenia"
    assert len(data["pillars"]) == 3
