"""Observability: structured logger + Prometheus metryki.

Walidacja kontraktu modułów. Bez Prometheusa moduł degraduje do stubów —
test sprawdza obie ścieżki.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout

import pytest

from api import _log, _metrics


def test_slog_human_readable_when_log_format_unset(monkeypatch, caplog):
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    with caplog.at_level("INFO", logger="architekt"):
        _log.slog("test_event", a=1, b="x")
    # Tryb human → poszło do logger (caplog), NIE do stdout jako JSON.
    assert any("test_event" in r.getMessage() for r in caplog.records)


def test_slog_emits_json_when_log_format_json(monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "json")
    buf = io.StringIO()
    with redirect_stdout(buf):
        _log.slog("llm_call_completed", agent="Syez", model="claude-sonnet-4-6",
                  input_tokens=100, output_tokens=200, cost_usd=0.001)
    out = buf.getvalue().strip()
    parsed = json.loads(out)
    assert parsed["event"] == "llm_call_completed"
    assert parsed["agent"] == "Syez"
    assert parsed["input_tokens"] == 100
    assert "ts" in parsed


def test_metrics_module_loads_and_renders():
    """Bez prometheus_client → degradacja do stubów, render zwraca b'' nie crash."""
    out = _metrics.render()
    assert isinstance(out, (bytes, bytearray))


def test_metrics_counters_inc_does_not_raise():
    """Wszystkie counters muszą wytrzymać .labels(...).inc() — zarówno na realnym
    prometheus_client jak i na stubach (gdy biblioteka nieobecna)."""
    _metrics.llm_calls_total.labels(agent="Syez", model="claude-sonnet-4-6", status="success").inc()
    _metrics.llm_cache_hits_total.labels(agent="Syez").inc()
    _metrics.llm_cache_misses_total.labels(agent="Kogit").inc()
    _metrics.completion_violations_total.labels(kind="prose_audit_signals_weak").inc()
    _metrics.rate_limit_hits_total.labels(route="/debate/stream").inc()


def test_histogram_observes_without_error():
    _metrics.debate_latency_seconds.labels(phase="council", council_mode="personal").observe(2.5)
