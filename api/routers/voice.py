"""Faza 5: backend Whisper transkrypcja dla środowisk bez Web Speech API (Tauri, offline)."""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB (limit Whisper API)


def _whisper_backend() -> str:
    return (os.getenv("AW_WHISPER_BACKEND") or "openai").strip().lower()


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: Optional[str] = "pl",
):
    """
    Transkrybuje plik audio na tekst.

    Backendy:
    - `openai` (domyślny): OpenAI Whisper API (wymaga OPENAI_API_KEY)
    - `local`: lokalny whisper (wymaga `pip install openai-whisper`)
    """
    data = await audio.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, f"Plik za duży (max {MAX_AUDIO_BYTES // 1024 // 1024} MB).")
    if len(data) < 1000:
        raise HTTPException(400, "Plik za mały — prawdopodobnie pusty.")

    backend = _whisper_backend()

    if backend == "openai":
        return await _transcribe_openai(data, audio.filename or "audio.webm", language or "pl")
    elif backend == "local":
        return await _transcribe_local(data, audio.filename or "audio.webm", language or "pl")
    else:
        raise HTTPException(500, f"Nieznany backend Whisper: {backend}")


async def _transcribe_openai(data: bytes, filename: str, language: str) -> dict:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(500, "OPENAI_API_KEY wymagany dla Whisper API.")

    import httpx

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, data)},
            data={"model": "whisper-1", "language": language[:2]},
        )
        if r.status_code != 200:
            raise HTTPException(502, f"Whisper API error: {r.status_code} {r.text[:300]}")
        result = r.json()
    return {"text": result.get("text", ""), "language": language}


async def _transcribe_local(data: bytes, filename: str, language: str) -> dict:
    try:
        import whisper
    except ImportError:
        raise HTTPException(500, "pip install openai-whisper — wymagane dla backend=local.")

    import asyncio

    suffix = "." + (filename.rsplit(".", 1)[-1] if "." in filename else "webm")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        path = tmp.name

        def _run():
            model = whisper.load_model("base")
            result = model.transcribe(path, language=language[:2])
            return result.get("text", "")

        text = await asyncio.to_thread(_run)

    return {"text": text, "language": language}
