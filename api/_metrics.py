"""Prometheus metryki + endpoint /metrics.

Cztery rodziny metryk dobrane pod realne pytania:
  • debate_latency_seconds (Histogram, label: phase, council_mode)
        — P50/P95/P99 latencji debat. Phase: council|synthesis|audit.
  • llm_calls_total (Counter, label: agent, model, status)
        — surowa liczba wywołań LLM. Status: success|error|fallback.
  • llm_cache_hits_total / llm_cache_misses_total (Counter)
        — wyznacznik hit rate cache LLM (warunek opłacalności v8).
  • completion_violations_total (Counter, label: kind)
        — ile razy syntezy Syeza nie spełniły AKSJOMATU 2 i wymagały re-promptu.
  • rate_limit_hits_total (Counter, label: route)
        — ile razy slowapi odrzucił request.

Gdy `prometheus_client` nie jest zainstalowane (dev bez observability) —
moduł degraduje do no-op stubów. Endpoint /metrics zwraca wtedy 503.
"""

from __future__ import annotations

try:  # pragma: no cover
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    _PROM_OK = True
except Exception:  # pragma: no cover
    _PROM_OK = False
    CONTENT_TYPE_LATEST = "text/plain"

    class _Stub:  # type: ignore[no-redef]
        def __init__(self, *_a, **_kw): pass
        def labels(self, *_a, **_kw): return self
        def inc(self, *_a, **_kw): pass
        def observe(self, *_a, **_kw): pass
        def time(self):
            class _Ctx:
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *_): pass
            return _Ctx()
    Counter = Histogram = _Stub  # type: ignore[assignment,misc]

    def generate_latest():  # type: ignore[no-redef]
        return b""


debate_latency_seconds = Histogram(
    "architekt_debate_latency_seconds",
    "Czas trwania fazy debaty (s).",
    labelnames=("phase", "council_mode"),
    buckets=(0.5, 1, 2, 5, 10, 20, 40, 80, 160),
)

llm_calls_total = Counter(
    "architekt_llm_calls_total",
    "Liczba wywołań LLM per agent/model/status.",
    labelnames=("agent", "model", "status"),
)

llm_cache_hits_total = Counter(
    "architekt_llm_cache_hits_total",
    "Trafienia cache LLM (Redis v8).",
    labelnames=("agent",),
)

llm_cache_misses_total = Counter(
    "architekt_llm_cache_misses_total",
    "Brak trafienia cache LLM.",
    labelnames=("agent",),
)

completion_violations_total = Counter(
    "architekt_completion_violations_total",
    "Naruszenia AKSJOMATU 2 wykryte w syntezie Syeza.",
    labelnames=("kind",),
)

rate_limit_hits_total = Counter(
    "architekt_rate_limit_hits_total",
    "Liczba requestów odrzuconych przez slowapi.",
    labelnames=("route",),
)


def is_available() -> bool:
    return _PROM_OK


def render() -> bytes:
    """Renderuje wszystkie metryki w formacie Prometheus exposition."""
    return generate_latest()
