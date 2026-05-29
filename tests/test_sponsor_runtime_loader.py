"""Testy loadera sekretów paczki sponsorowanej (bez prawdziwych kluczy)."""
from __future__ import annotations

import os

from config.sponsor_runtime_loader import apply_payload, encode_value


def test_apply_payload_roundtrip(monkeypatch):
    salt = 0xA7
    monkeypatch.delenv("TEST_SPONSOR_KEY", raising=False)
    blob = encode_value("sekret-beta", salt)
    apply_payload({"TEST_SPONSOR_KEY": blob}, salt)
    assert os.environ["TEST_SPONSOR_KEY"] == "sekret-beta"
