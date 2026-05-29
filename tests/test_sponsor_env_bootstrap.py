"""Integracja: BETA_SPONSOR.marker + sponsor_payload → os.environ."""
from __future__ import annotations

import os
from pathlib import Path

from config.sponsor_runtime_loader import apply_sponsor_secrets_if_marked, encode_value


def test_apply_sponsor_secrets_if_marked(tmp_path, monkeypatch):
    salt = 42
    secret = "test-anthropic-key-beta"
    payload = tmp_path / "config" / "sponsor_payload.py"
    payload.parent.mkdir(parents=True)
    blob = encode_value(secret, salt)
    payload.write_text(
        f"SALT = {salt}\nBLOBS = {{'ANTHROPIC_API_KEY': '{blob}'}}\n",
        encoding="utf-8",
    )
    (tmp_path / "BETA_SPONSOR.marker").write_text("sponsor-beta\n", encoding="utf-8")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert apply_sponsor_secrets_if_marked(tmp_path) is True
    assert os.environ.get("ANTHROPIC_API_KEY") == secret


def test_apply_sponsor_secrets_skips_without_marker(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert apply_sponsor_secrets_if_marked(tmp_path) is False
    assert "ANTHROPIC_API_KEY" not in os.environ
