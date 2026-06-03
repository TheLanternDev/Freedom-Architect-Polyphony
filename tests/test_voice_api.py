"""P1-C2: HTTP smoke dla /voice/transcribe."""

from __future__ import annotations


def test_voice_transcribe_400_too_small(client_no_redis):
    r = client_no_redis.post(
        "/voice/transcribe",
        files={"audio": ("tiny.webm", b"x" * 100, "audio/webm")},
    )
    assert r.status_code == 400
    assert "za mały" in r.json()["detail"].lower()


def test_voice_transcribe_500_without_openai_key(client_no_redis, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AW_WHISPER_BACKEND", "openai")
    payload = b"\x00" * 2000
    r = client_no_redis.post(
        "/voice/transcribe",
        files={"audio": ("clip.webm", payload, "audio/webm")},
    )
    assert r.status_code == 500
    assert "OPENAI_API_KEY" in r.json()["detail"]


def test_voice_transcribe_413_over_limit(client_no_redis):
    r = client_no_redis.post(
        "/voice/transcribe",
        files={"audio": ("huge.webm", b"x" * (26 * 1024 * 1024), "audio/webm")},
    )
    assert r.status_code == 413


def test_voice_requires_auth(client_no_auth_bypass):
    r = client_no_auth_bypass.post(
        "/voice/transcribe",
        files={"audio": ("clip.webm", b"\x00" * 2000, "audio/webm")},
    )
    assert r.status_code == 401
