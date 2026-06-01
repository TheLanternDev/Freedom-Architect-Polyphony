"""Komunikat SSE `debate_pending` — tryb rady × język."""

from __future__ import annotations

import pytest

from api.services.mode_helpers import _pending_msg


@pytest.mark.parametrize(
    ("council_mode", "language", "expected"),
    [
        (
            "personal",
            "pl",
            "Sprawdzam bezpieczeństwo i destyluję marzenie...",
        ),
        (
            "personal",
            "en",
            "Checking safety and distilling the dream...",
        ),
        (
            "fa2",
            "pl",
            "Sprawdzam bezpieczeństwo, przygotowuję analityków...",
        ),
        (
            "fa2",
            "en",
            "Checking safety, preparing analysts...",
        ),
    ],
)
def test_pending_msg_by_council_mode_and_language(
    council_mode: str, language: str, expected: str
):
    assert _pending_msg(council_mode, language) == expected


def test_pending_msg_defaults_to_polish_personal():
    assert _pending_msg("personal") == (
        "Sprawdzam bezpieczeństwo i destyluję marzenie..."
    )
