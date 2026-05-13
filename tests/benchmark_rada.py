"""Benchmark wydajności full_synthesis() – Rada Nadzorcza v3.0."""

from __future__ import annotations

import pytest

from agents import full_synthesis

# Realistyczny kontekst zbliżony do produkcyjnego requestu
REALISTIC_CONTEXT = (
    "Użytkownik chce zbudować: platformę SaaS do zarządzania finansami osobistymi "
    "z funkcjami AI, budżetowaniem, kategoryzacją wydatków, prognozami i społecznością. "
    "Skala: startup | Budżet: medium"
)


def test_full_synthesis_benchmark(benchmark):
    """Mierzy czas full_synthesis() z realistycznym kontekstem."""
    result = benchmark(full_synthesis, REALISTIC_CONTEXT)
    assert "Rada Nadzorcza" in result
    assert "SYNTHEZA (Syez)" in result


def test_full_synthesis_under_50ms(benchmark):
    """Soft assertion: średni czas < 50 ms."""
    benchmark(full_synthesis, REALISTIC_CONTEXT)
    # benchmark.stats.stats.mean w sekundach
    mean_ms = benchmark.stats.stats.mean * 1000
    assert mean_ms < 50, f"Średni czas {mean_ms:.2f} ms przekracza 50 ms"
