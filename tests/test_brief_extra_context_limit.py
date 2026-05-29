"""AKSJOMAT 2: brief z załącznikiem nie może po cichu wyciec (422).

Limit Brief.extra_context podniesiony do 8000 — walidacja granicy.
"""
import pytest
from pydantic import ValidationError

from main import Brief

_DESC = "To jest poprawny brief dla Rady z co najmniej pięcioma słowami."


def test_extra_context_accepts_8000():
    b = Brief(description=_DESC, extra_context="x" * 8000)
    assert len(b.extra_context) == 8000


def test_extra_context_rejects_over_8000():
    with pytest.raises(ValidationError):
        Brief(description=_DESC, extra_context="x" * 8001)


def test_extra_context_optional():
    b = Brief(description=_DESC)
    assert b.extra_context is None
