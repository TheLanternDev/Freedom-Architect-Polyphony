"""Testy debate_orchestrator: SSE eventy, helper functions, council selection."""

from __future__ import annotations

from unittest.mock import MagicMock

from api.services.debate_orchestrator import (
    _extract_json_block,
    _try_parse_synthesis_json,
    build_syez_payload,
    chunk_words,
    select_council_for_mode,
)


class TestExtractJsonBlock:
    def test_plain_json(self):
        assert _extract_json_block('{"key": "val"}') == '{"key": "val"}'

    def test_json_in_fenced_block(self):
        text = "```json\n{\"a\": 1}\n```"
        assert _extract_json_block(text) == '{"a": 1}'

    def test_no_json_returns_none(self):
        assert _extract_json_block("no json here") is None

    def test_nested_braces(self):
        text = 'prefix {"outer": {"inner": 42}} suffix'
        result = _extract_json_block(text)
        assert '"inner": 42' in result


class TestTryParseSynthesisJson:
    def test_valid_json_dict(self):
        result = _try_parse_synthesis_json('{"insights": [1,2,3]}')
        assert result == {"insights": [1, 2, 3]}

    def test_invalid_json_returns_none(self):
        assert _try_parse_synthesis_json("not json") is None

    def test_json_array_returns_none(self):
        """Oczekujemy dict, nie list."""
        assert _try_parse_synthesis_json("[1,2,3]") is None


class TestChunkWords:
    def test_basic_chunking(self):
        result = chunk_words("a b c d e f g h i j", group=5)
        assert len(result) == 2
        assert result[0].strip() == "a b c d e"
        assert result[1].strip() == "f g h i j"

    def test_empty_string(self):
        assert chunk_words("") == []

    def test_fewer_words_than_group(self):
        result = chunk_words("hello world", group=5)
        assert result == ["hello world"]


class TestSelectCouncilForMode:
    def test_codzienny_returns_light_agents(self):
        """Tryb codzienny → tylko 4 agentów (Kogit, Emojy, Smaty, Obver)."""
        council = select_council_for_mode("codzienny")
        names = {a.name for a in council}
        assert names <= {"Kogit", "Emojy", "Smaty", "Obver"}
        assert len(council) <= 4

    def test_pelna_returns_full_council(self):
        """Tryb pelna → 9 agentów."""
        council = select_council_for_mode("pelna")
        assert len(council) == 9

    def test_schematy_returns_full_council(self):
        """Tryb schematy → pełna Rada."""
        council = select_council_for_mode("schematy")
        assert len(council) == 9


class TestBuildSyezPayload:
    def test_contains_brief_and_voices(self):
        """Payload zawiera brief i głosy."""
        brief = MagicMock()
        brief.language = "pl"
        brief.mode = "pelna"
        brief.category = "decyzja"
        brief.intention = None
        brief.extra_context = None
        brief.scale = None
        brief.budget = None
        brief.description = "Test brief"

        result = build_syez_payload("oryginalny brief", "[Kogit] bla bla", None, brief)
        assert "oryginalny brief" in result
        assert "[Kogit] bla bla" in result

    def test_includes_dream_context_when_provided(self):
        """Z DreamArchitecture → payload zawiera kontekst marzenia."""
        brief = MagicMock()
        brief.language = "pl"
        brief.mode = "pelna"
        brief.category = "marzenie"
        brief.intention = None
        brief.extra_context = None
        brief.scale = None
        brief.budget = None
        brief.description = "Marzenie test"

        dream = MagicMock()
        dream.for_syez.return_value = "[DREAM] core dream text"

        result = build_syez_payload("brief", "voices", dream, brief)
        assert "[DREAM] core dream text" in result

    def test_aksjomat2_protocol_present(self):
        """Payload zawiera protokół AKSJOMATU 2."""
        brief = MagicMock()
        brief.language = "pl"
        brief.mode = "pelna"
        brief.category = "decyzja"
        brief.intention = None
        brief.extra_context = None
        brief.scale = None
        brief.budget = None
        brief.description = "Brief"

        result = build_syez_payload("brief", "voices", None, brief)
        assert "AKSJOMAT" in result or "domkni" in result.lower()


# ── Tests: build_audit_fix_prompt ────────────────────────────────────────────

from api.services.mode_helpers import build_audit_fix_prompt


class TestBuildAuditFixPrompt:
    def test_pl_contains_aksjomat(self):
        p = build_audit_fix_prompt("pl", "stara synteza")
        assert "AKSJOMATU 2" in p
        assert "stara synteza" in p

    def test_en_contains_axiom(self):
        p = build_audit_fix_prompt("en", "old synthesis")
        assert "AXIOM 2" in p
        assert "old synthesis" in p

    def test_pl_no_json_instruction(self):
        p = build_audit_fix_prompt("pl", "x")
        assert "bez JSON" in p

    def test_en_no_json_instruction(self):
        p = build_audit_fix_prompt("en", "x")
        assert "no JSON" in p


# ── Tests: PhaseCouncilResult / PhaseSynthesisResult ─────────────────────────

from api.services._types import PhaseCouncilResult, PhaseSynthesisResult


class TestPhaseResults:
    def test_council_result_defaults(self):
        r = PhaseCouncilResult(full_voices={"a": "voice"})
        assert r.full_voices == {"a": "voice"}
        assert r.events == []

    def test_synthesis_result_defaults(self):
        r = PhaseSynthesisResult(synthesis_final="done")
        assert r.parsed_final is None
        assert r.violation_payload is None
        assert r.events == []

    def test_synthesis_result_with_violation(self):
        r = PhaseSynthesisResult(
            synthesis_final="x",
            violation_payload={"kind": "test"},
        )
        assert r.violation_payload["kind"] == "test"
