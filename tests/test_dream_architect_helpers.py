"""Pure-function testy `core.dream_architect`: helpery JSON + fallback.

Cel: pokryć ścieżki które nie wymagają LLM ani DB — parsowanie surowych
odpowiedzi modeli, fallback deterministyczny, cache key, tenant scope.
"""

from __future__ import annotations

import pytest

from core import dream_architect as da
from core.dream_architect import (
    DreamArchitecture,
    _balanced_json_object_slice,
    _build_dream_from_payload,
    _cache_key,
    _extract_json_block,
    _fallback_dream,
    _parse_llm_json_object,
    _strip_trailing_commas_json,
    _tenant_scope,
    distill_dream,
)


# ── _balanced_json_object_slice ──────────────────────────────────────────────


def test_balanced_slice_returns_none_when_no_brace():
    assert _balanced_json_object_slice("no braces here") is None


def test_balanced_slice_simple_object():
    assert _balanced_json_object_slice('{"a": 1}') == '{"a": 1}'


def test_balanced_slice_nested_objects():
    s = '{"outer": {"inner": "x"}}'
    assert _balanced_json_object_slice(s) == s


def test_balanced_slice_handles_braces_inside_strings():
    s = 'preamble {"text": "to }nie kończy obiektu{"} suffix'
    out = _balanced_json_object_slice(s)
    assert out == '{"text": "to }nie kończy obiektu{"}'


def test_balanced_slice_returns_none_for_unclosed():
    assert _balanced_json_object_slice('{"open": "no close"') is None


# ── _strip_trailing_commas_json ──────────────────────────────────────────────


def test_strip_trailing_commas_in_object():
    assert _strip_trailing_commas_json('{"a": 1,}') == '{"a": 1}'


def test_strip_trailing_commas_in_array():
    assert _strip_trailing_commas_json('[1, 2,]') == '[1, 2]'


def test_strip_trailing_commas_handles_nested_and_multiple():
    raw = '{"a": [1, 2,], "b": {"c": 3,},}'
    out = _strip_trailing_commas_json(raw)
    assert out == '{"a": [1, 2], "b": {"c": 3}}'


def test_strip_trailing_commas_idempotent_on_clean_json():
    clean = '{"a": 1, "b": [2, 3]}'
    assert _strip_trailing_commas_json(clean) == clean


# ── _extract_json_block ──────────────────────────────────────────────────────


def test_extract_json_block_from_fenced():
    text = '```json\n{"core_dream": "x"}\n```'
    out = _extract_json_block(text)
    assert '"core_dream"' in out


def test_extract_json_block_with_preamble_and_postamble():
    text = 'Wstęp od modelu.\n{"a": 1}\nDopisek.'
    out = _extract_json_block(text)
    assert out == '{"a": 1}'


def test_extract_json_block_raises_when_no_braces():
    with pytest.raises(ValueError):
        _extract_json_block("no json here at all")


# ── _parse_llm_json_object ───────────────────────────────────────────────────


def test_parse_llm_json_object_happy_path():
    obj = _parse_llm_json_object('{"a": 1, "b": "x"}')
    assert obj == {"a": 1, "b": "x"}


def test_parse_llm_json_object_handles_trailing_commas():
    obj = _parse_llm_json_object('{"a": 1, "b": [2, 3,],}')
    assert obj == {"a": 1, "b": [2, 3]}


def test_parse_llm_json_object_unfencing():
    obj = _parse_llm_json_object('```json\n{"x": true}\n```')
    assert obj == {"x": True}


def test_parse_llm_json_object_raises_on_garbage():
    with pytest.raises(ValueError):
        _parse_llm_json_object("nope")


# ── _fallback_dream ──────────────────────────────────────────────────────────


def test_fallback_dream_pl_structure():
    d = _fallback_dream("brief raw test", language="pl")
    assert isinstance(d, DreamArchitecture)
    assert "Patryk chce doprowadzić do końca" in d.core_dream
    assert "Architekta Wolności" in d.value_anchor
    assert len(d.pillars) >= 3
    assert len(d.milestones) >= 1
    assert d.next_move.action  # niepuste
    assert len(d.functionality_checklist) >= 1


def test_fallback_dream_en_structure():
    d = _fallback_dream("brief raw test", language="en")
    assert isinstance(d, DreamArchitecture)
    assert "Freedom Architect" in d.value_anchor
    assert "drive this to completion" in d.core_dream


def test_fallback_dream_truncates_long_brief():
    long_brief = "x" * 500
    d = _fallback_dream(long_brief, language="pl")
    # core_dream zawiera obciętą wersję — nie pełne 500 znaków briefu.
    assert "..." in d.core_dream
    assert len(d.core_dream) < 200


# ── distill_dream (sync — używa fallbacku gdy brak LLM) ──────────────────────


def test_distill_dream_returns_dream_architecture_with_fallback(monkeypatch):
    """Bez ANTHROPIC_API_KEY `distill_dream` MUSI zwrócić fallback (offline ok)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("AW_LLM_BACKEND", "none")
    d = distill_dream("Pomysł na produkt B2B")
    assert isinstance(d, DreamArchitecture)
    assert d.raw_brief == "Pomysł na produkt B2B"


# ── _cache_key + _tenant_scope ───────────────────────────────────────────────


def test_cache_key_is_stable_for_same_brief():
    a = _cache_key("identical brief")
    b = _cache_key("identical brief")
    assert a == b


def test_cache_key_differs_for_different_briefs():
    assert _cache_key("brief A") != _cache_key("brief B")


def test_cache_key_is_hex_sha256():
    """Klucz to czysty hex hash — nie prefixowany."""
    out = _cache_key("x")
    assert len(out) == 64
    int(out, 16)  # nie rzuca jeśli to hex


def test_tenant_scope_is_string():
    out = _tenant_scope()
    assert isinstance(out, str) and len(out) > 0


# ── _build_dream_from_payload ────────────────────────────────────────────────


def test_build_dream_from_minimal_payload():
    """Payload spełnia min_length z Pydantic (5+ znaków na pola tekstowe)."""
    payload = {
        "core_dream": "core dream value",
        "value_anchor": "anchor value",
        "pillars": ["pillar one", "pillar two", "pillar three"],
        "milestones": [{"title": "milestone one", "due": "2026-06-01",
                        "why_it_matters": "matters because reasons"}],
        "next_move": {"action": "do X today within sixty minutes",
                      "when": "today", "smallest_form": "1 sentence"},
        "completion_criteria": ["I finished it for real."],
        "functionality_checklist": ["works for me"],
    }
    d = _build_dream_from_payload("raw brief", payload)
    assert d.core_dream == "core dream value"
    assert d.value_anchor == "anchor value"
    assert len(d.pillars) == 3
    assert d.milestones[0].title == "milestone one"
    assert "do X today" in d.next_move.action
