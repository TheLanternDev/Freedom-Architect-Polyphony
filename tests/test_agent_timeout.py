"""Timeout agenta LLM: propagacja, metryki, integracja z `_phase_council`."""

from __future__ import annotations

import asyncio
import json
import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.base_agent import BaseAgent
from agents.kogit import Kogit
from config.llm_providers import LLM_TIMEOUT_WAIT_SEC


def _parse_sse_payload(sse_frame: str) -> dict:
    m = re.search(r"^data: (.+)$", sse_frame, re.MULTILINE)
    assert m, f"brak data: w {sse_frame!r}"
    return json.loads(m.group(1))


@pytest.mark.asyncio
async def test_call_llm_apitimeout_propagates_no_fallback(monkeypatch):
    """APITimeoutError z SDK Anthropic — jak asyncio.TimeoutError, bez fallbacku."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-for-timeout")
    monkeypatch.setattr(
        "config.llm_providers.effective_llm_backend", lambda: "anthropic"
    )

    from anthropic import APITimeoutError

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=APITimeoutError("request"))

    monkeypatch.setattr(BaseAgent, "_get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(BaseAgent, "_redis", None)

    agent = Kogit()
    with pytest.raises(APITimeoutError):
        await agent._call_llm("brief APITimeout", language="pl")


@pytest.mark.asyncio
async def test_call_llm_timeout_propagates_no_fallback(monkeypatch):
    """`asyncio.TimeoutError` z LLM → re-raise, bez `_fallback_contribute`."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-for-timeout")
    monkeypatch.setattr(
        "config.llm_providers.effective_llm_backend", lambda: "anthropic"
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=asyncio.TimeoutError())

    monkeypatch.setattr(BaseAgent, "_get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(BaseAgent, "_redis", None)

    agent = Kogit()
    with pytest.raises(asyncio.TimeoutError):
        await agent._call_llm("brief testowy timeout", language="pl")


@pytest.mark.asyncio
async def test_call_llm_timeout_increments_prometheus_counter(monkeypatch):
    inc_statuses: list[str] = []

    class _Counter:
        def inc(self) -> None:
            inc_statuses.append(self._status)

    def fake_labels(**kwargs):
        c = _Counter()
        c._status = kwargs["status"]
        return c

    monkeypatch.setattr(
        "api._metrics.llm_calls_total", MagicMock(labels=fake_labels)
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-for-timeout")
    monkeypatch.setattr(
        "config.llm_providers.effective_llm_backend", lambda: "anthropic"
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=asyncio.TimeoutError())

    monkeypatch.setattr(BaseAgent, "_get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(BaseAgent, "_redis", None)

    agent = Kogit()
    with pytest.raises(asyncio.TimeoutError):
        await agent._call_llm("brief", language="pl")

    assert "timeout" in inc_statuses


@pytest.mark.asyncio
async def test_phase_council_timeout_voice_and_agent_error_kind():
    """Timeout w `acontribute` → `[timeout:` voice, SSE `kind=timeout`, brak w Syez."""
    from api.services import debate_orchestrator as orch
    from api.services._types import PhaseCouncilResult

    class _TimeoutAgent:
        name = "Wolny"

        async def acontribute(self, *args, **kwargs):
            raise asyncio.TimeoutError()

    class _Brief:
        language = "pl"
        mode = "pelna"

    events: list[str] = []
    full_voices: dict[str, str] = {}
    async for evt in orch._phase_council(
        [_TimeoutAgent()], "brief", None, _Brief(), None, "personal"
    ):
        if isinstance(evt, PhaseCouncilResult):
            full_voices = evt.full_voices
        else:
            events.append(evt)

    assert "Wolny" not in full_voices
    err_frames = [e for e in events if e.startswith("event: agent_error")]
    assert len(err_frames) == 1
    payload = _parse_sse_payload(err_frames[0])
    assert payload["agent"] == "Wolny"
    assert payload["kind"] == "timeout"
    assert payload["error"].startswith(
        f"[timeout: agent Wolny przekroczył {LLM_TIMEOUT_WAIT_SEC}s]"
    )
