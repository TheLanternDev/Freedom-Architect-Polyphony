"""Tryby debaty FA2 i przypisanie agentów."""

from __future__ import annotations

VALID_MODES = ("pelna", "marzen", "schematy", "codzienny")

MODE_AGENTS: dict[str, list[str] | None] = {
    "pelna": None,  # None = all 9
    "marzen": None,
    "schematy": None,
    "codzienny": ["Kogit", "Emojy", "Smaty", "Obver"],
}
