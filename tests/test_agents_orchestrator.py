"""Testy modułu `agents/` (orchestrator Rady).

`adeliberate`, `deliberate`, `full_synthesis`, `afull_synthesis` i
`_build_syez_input` — pokrycie ścieżek sync i async, z dream i bez.
Mock'ujemy `contribute`/`acontribute`, żeby NIE wołać LLM-a.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import agents as ag


def _patch_all_agents(monkeypatch):
    """Każdy z 9 agentów zwraca deterministyczną wypowiedź; Syez też."""
    for a in ag.COUNCIL:
        monkeypatch.setattr(a, "contribute", lambda ctx, _name=a.name: f"{_name}-sync-ok")

        async def _async(ctx, dream=None, language="pl", debate_mode="pelna",
                         evolution_note=None, council_mode="personal",
                         _name=a.name, **_kw):
            return f"{_name}-async-ok"
        monkeypatch.setattr(a, "acontribute", _async)

    monkeypatch.setattr(ag.SYNTHESIZER, "contribute",
                        lambda ctx: "Syez sync synthesis prose")

    async def _syez_async(ctx, dream=None, language="pl", debate_mode="pelna",
                          council_mode="personal", **_kw):
        return "Syez async synthesis prose"
    monkeypatch.setattr(ag.SYNTHESIZER, "acontribute", _syez_async)


def test_get_council_returns_independent_copy():
    a = ag.get_council()
    b = ag.get_council()
    assert a is not b  # nowa lista
    assert [x.name for x in a] == [x.name for x in ag.COUNCIL]


def test_deliberate_collects_all_voices(monkeypatch):
    _patch_all_agents(monkeypatch)
    out = ag.deliberate("brief")
    assert len(out) == 9
    assert all(v.endswith("-sync-ok") for _n, v in out)


def test_adeliberate_collects_all_voices(monkeypatch):
    _patch_all_agents(monkeypatch)
    out = asyncio.run(ag.adeliberate("brief"))
    assert len(out) == 9
    assert all(v.endswith("-async-ok") for _n, v in out)


def test_full_synthesis_returns_header_voices_and_synthesis(monkeypatch):
    _patch_all_agents(monkeypatch)
    out = ag.full_synthesis("brief")
    assert "Rada Nadzorcza" in out
    # wszyscy 9 są wymienieni
    for a in ag.COUNCIL:
        assert a.name in out
    assert "SYNTEZA (Syez)" in out
    assert "Syez sync synthesis prose" in out


def test_afull_synthesis_default_language_pl(monkeypatch):
    _patch_all_agents(monkeypatch)
    out = asyncio.run(ag.afull_synthesis("brief"))
    assert "Rada Nadzorcza" in out
    assert "SYNTEZA (Syez)" in out
    assert "Syez async synthesis prose" in out


def test_afull_synthesis_english_header_and_footer(monkeypatch):
    _patch_all_agents(monkeypatch)
    out = asyncio.run(ag.afull_synthesis("brief", language="en"))
    assert "Supervisory Council" in out
    assert "SYNTHESIS (Syez)" in out


def test_build_syez_input_includes_dream_when_provided():
    dream = SimpleNamespace(for_syez=lambda: "DREAM-BODY")
    out = ag._build_syez_input("ctx-brief", "VOICES", dream)
    assert "ARCHITEKTURA MARZENIA" in out
    assert "DREAM-BODY" in out
    assert "ctx-brief" in out
    assert "VOICES" in out


def test_build_syez_input_swallows_dream_error():
    """Gdy `dream.for_syez()` rzuca — nie powinno wywalić syntezy."""
    bad = SimpleNamespace(for_syez=lambda: (_ for _ in ()).throw(RuntimeError("x")))
    out = ag._build_syez_input("ctx", "voices", bad)
    # Brak headera marzenia, ale reszta jest.
    assert "ARCHITEKTURA MARZENIA" not in out
    assert "voices" in out
    assert "ctx" in out


def test_build_syez_input_without_dream():
    out = ag._build_syez_input("only-ctx", "only-voices", None)
    assert "ARCHITEKTURA MARZENIA" not in out
    assert "only-ctx" in out
    assert "only-voices" in out
