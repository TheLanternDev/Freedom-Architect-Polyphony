from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile

import httpx

from pathlib import Path

from .config import get_elevenlabs_api_key, get_elevenlabs_model_id, get_elevenlabs_voice_id

API_BASE = "https://api.elevenlabs.io/v1"


def _headers(*, json_mode: bool = True) -> dict[str, str]:
    h = {"xi-api-key": get_elevenlabs_api_key()}
    if json_mode:
        h["Content-Type"] = "application/json"
        h["Accept"] = "application/json"
    else:
        h["Accept"] = "audio/mpeg"
    return h


def _voice_settings(*, speed: float | None = None) -> dict:
    settings = {
        "stability": 0.55,
        "similarity_boost": 0.75,
        "style": 0.2,
        "use_speaker_boost": True,
    }
    if speed is not None:
        settings["speed"] = speed
    return settings


def _tts_payload(
    text: str,
    *,
    model_id: str | None = None,
    speed: float | None = None,
    voice_settings: dict | None = None,
) -> dict:
    settings = dict(voice_settings) if voice_settings else _voice_settings(speed=speed)
    if speed is not None and "speed" not in settings:
        settings["speed"] = speed
    return {
        "text": text.strip(),
        "model_id": model_id or get_elevenlabs_model_id(),
        "language_code": "pl",
        "voice_settings": settings,
    }


def _client() -> httpx.Client:
    direct = os.getenv("AW_ELEVENLABS_DIRECT", "1").strip().lower() in ("1", "true", "yes")
    return httpx.Client(timeout=120.0, trust_env=not direct)


def _synthesize_via_curl(
    text: str,
    *,
    voice_id: str,
    model_id: str,
    speed: float | None = None,
) -> bytes:
    """Fallback gdy httpx trafia na proxy/DNS (curl --noproxy)."""
    key = get_elevenlabs_api_key()
    payload = _tts_payload(text, model_id=model_id, speed=speed)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        out = tmp.name
    cmd = [
        "curl", "-sfS", "--noproxy", "*",
        "-X", "POST",
        f"{API_BASE}/text-to-speech/{voice_id}",
        "-H", f"xi-api-key: {key}",
        "-H", "Content-Type: application/json",
        "-H", "Accept: audio/mpeg",
        "-d", json.dumps(payload, ensure_ascii=False),
        "-o", out,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "curl failed")[-500:]
        raise RuntimeError(f"ElevenLabs curl TTS: {err}")
    data = Path(out).read_bytes()
    Path(out).unlink(missing_ok=True)
    return data


def list_voices() -> list[dict]:
    """Lista głosów dostępnych na koncie (wymaga voices_read w kluczu API)."""
    try:
        with _client() as client:
            resp = client.get(f"{API_BASE}/voices", headers=_headers())
    except httpx.HTTPError as e:
        raise RuntimeError(f"Połączenie z ElevenLabs nie powiodło się: {e}") from e
    resp.raise_for_status()
    data = resp.json()
    voices = data.get("voices") if isinstance(data, dict) else data
    if not isinstance(voices, list):
        return []
    return voices


def synthesize_speech(
    text: str,
    *,
    voice_id: str | None = None,
    model_id: str | None = None,
    speed: float | None = None,
    voice_settings: dict | None = None,
) -> bytes:
    """Text-to-speech — zwraca bajty MP3."""
    vid = voice_id or get_elevenlabs_voice_id()
    payload = _tts_payload(text, model_id=model_id, speed=speed, voice_settings=voice_settings)
    url = f"{API_BASE}/text-to-speech/{vid}"
    try:
        with _client() as client:
            resp = client.post(url, headers=_headers(json_mode=False), json=payload)
        if resp.status_code >= 400:
            detail = resp.text[:500]
            raise RuntimeError(f"ElevenLabs TTS [{resp.status_code}]: {detail}")
        return resp.content
    except (httpx.HTTPError, RuntimeError):
        return _synthesize_via_curl(text, voice_id=vid, model_id=payload["model_id"], speed=speed)


def synthesize_with_timestamps(
    text: str,
    *,
    voice_id: str | None = None,
    model_id: str | None = None,
    speed: float | None = None,
) -> dict:
    """TTS + alignment — do rozumowania o długości skryptu (1 kredyt EL).

    Zwraca: audio_bytes, duration_s, alignment (character-level), normalized_alignment.
    """
    vid = voice_id or get_elevenlabs_voice_id()
    payload = _tts_payload(text, model_id=model_id, speed=speed)
    url = f"{API_BASE}/text-to-speech/{vid}/with-timestamps"
    try:
        with _client() as client:
            resp = client.post(url, headers=_headers(), json=payload)
    except httpx.HTTPError as e:
        raise RuntimeError(f"Połączenie z ElevenLabs nie powiodło się: {e}") from e
    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise RuntimeError(f"ElevenLabs TTS+timestamps [{resp.status_code}]: {detail}")

    data = resp.json()
    alignment = data.get("alignment") or data.get("normalized_alignment") or {}
    ends = alignment.get("character_end_times_seconds") or []
    duration_s = float(ends[-1]) if ends else 0.0
    audio_b64 = data.get("audio_base64") or ""
    audio_bytes = base64.b64decode(audio_b64) if audio_b64 else b""

    return {
        "audio_bytes": audio_bytes,
        "duration_s": duration_s,
        "alignment": alignment,
        "normalized_alignment": data.get("normalized_alignment"),
    }
