"""Prefix kontekstowy FA2 wstrzykiwany na poczatek raw_brief."""

from __future__ import annotations


def fa2_business_context_prefix(language: str = "pl") -> str:
    if (language or "").strip().lower() == "en":
        return (
            "\n\n[Freedom Architect -- BUSINESS FRAMING]\n"
            "Interpret the brief as a founder/operator decision: market, revenue, costs, runway, "
            "team, legal/IP, GTM, fundraising, execution risk. Prefer concrete business metrics "
            "and trade-offs over life-coaching or purely existential framing unless the brief demands it.\n\n"
        )
    return (
        "\n\n[Freedom Architect -- RAMOWANIE BIZNESOWE]\n"
        "Potraktuj brief jak decyzje founder/operatora: rynek, przychod, koszty, runway, zespol, "
        "prawo/IP, GTM, fundraising, ryzyko wykonania. Preferuj konkretne metryki i trade-offy "
        "zamiast wylacznie ram Moj Swiat, chyba ze brief tego wymaga.\n\n"
    )
