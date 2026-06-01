"""Destylacja marzenia: timeout per backend, quality= fallback, metryka Prometheus."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.dream_service import dream_architecture_sse
from core.dream_architect import adistill_dream

_VALID_LLM_PAYLOAD = {
    "core_dream": "Patryk chce doprowadzić testowy brief do końca w pełni.",
    "value_anchor": "Autentyczność i domknięcie projektu mają pierwszeństwo.",
    "pillars": ["filtr A", "filtr B", "filtr C"],
    "milestones": [
        {
            "title": "Pierwszy krok",
            "due": "2026-12-01",
            "why_it_matters": "Dowód że da się skończyć.",
        }
    ],
    "next_move": {
        "action": "Zapisać kryteria done",
        "when": "dziś",
        "smallest_form": "Jedno zdanie w notatniku.",
    },
    "completion_criteria": ["Mogę powiedzieć: skończone."],
    "functionality_checklist": ["Działa end-to-end w jednym scenariuszu."],
}


async def _wait_for_timeout(coro, timeout):
    del timeout
    if hasattr(coro, "close"):
        coro.close()
    raise asyncio.TimeoutError()


@pytest.mark.parametrize("backend", ["anthropic", "xai", "ollama"])
@pytest.mark.asyncio
async def test_adistill_dream_timeout_returns_fallback_quality(
    backend: str, monkeypatch
):
    """Każdy backend po timeout → deterministyczny fallback, quality=fallback."""
    monkeypatch.setattr(asyncio, "wait_for", _wait_for_timeout)
    monkeypatch.setattr("core.dream_architect.effective_llm_backend", lambda: backend)
    import core.dream_architect as da

    da._DREAM_CACHE.clear()

    if backend == "anthropic":
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    elif backend == "xai":
        monkeypatch.setenv("XAI_API_KEY", "test-key")
    else:
        monkeypatch.setenv("LLM_BACKEND", "ollama")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)

    dream = await adistill_dream("Brief timeout destylacji marzenia test.", language="pl")
    assert dream.distillation_quality == "fallback"


@pytest.mark.parametrize("backend", ["anthropic", "xai", "ollama"])
@pytest.mark.asyncio
async def test_adistill_dream_timeout_increments_metric(backend: str, monkeypatch):
    statuses: list[str] = []

    class _Counter:
        def inc(self) -> None:
            statuses.append(self._status)

    def fake_labels(**kwargs):
        c = _Counter()
        c._status = kwargs["status"]
        return c

    monkeypatch.setattr(
        "api._metrics.dream_distillation_total", MagicMock(labels=fake_labels)
    )
    monkeypatch.setattr(asyncio, "wait_for", _wait_for_timeout)
    monkeypatch.setattr("core.dream_architect.effective_llm_backend", lambda: backend)
    import core.dream_architect as da

    da._DREAM_CACHE.clear()

    if backend == "anthropic":
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    elif backend == "xai":
        monkeypatch.setenv("XAI_API_KEY", "test-key")
    else:
        monkeypatch.setenv("LLM_BACKEND", "ollama")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)

    await adistill_dream("Brief metryka timeout.", language="pl")
    assert "timeout" in statuses


@pytest.mark.asyncio
async def test_adistill_dream_llm_success_sets_quality_llm(monkeypatch):
    """Sukces LLM → distillation_quality=llm i quality=llm w SSE."""
    import core.dream_architect as da

    monkeypatch.setattr(da, "effective_llm_backend", lambda: "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    da._DREAM_CACHE.clear()

    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(_VALID_LLM_PAYLOAD))]
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    import anthropic

    monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda **kw: mock_client)

    dream = await adistill_dream("Brief sukces LLM destylacji.", language="pl")
    assert dream.distillation_quality == "llm"

    frame = dream_architecture_sse(dream)
    assert '"quality": "llm"' in frame or '"quality":"llm"' in frame.replace(" ", "")
