"""Walidacja plików MP4 przez ffprobe — bez LLM, bez API."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _ffprobe_json(path: Path) -> dict | None:
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration:stream=width,height,codec_type",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _aspect_ok(width: int, height: int, expected: str) -> bool:
    """Sprawdź proporcje z tolerancją (xAI bywa nieidealne)."""
    try:
        ew, eh = (int(x) for x in expected.split(":"))
    except (ValueError, AttributeError):
        return True
    if width <= 0 or height <= 0 or ew <= 0 or eh <= 0:
        return False
    target = ew / eh
    actual = width / height
    return abs(actual - target) <= 0.06  # ~6% tolerancji


def validate_mp4(
    path: Path,
    *,
    min_duration: float = 1.0,
    expected_aspect: str | None = "9:16",
) -> list[str]:
    """Zwróć listę problemów (pusta = plik OK). Nie rzuca wyjątków sama z siebie."""
    problems: list[str] = []
    if not path.is_file():
        return [f"Plik nie istnieje: {path}"]
    if path.stat().st_size == 0:
        return [f"Plik ma zerowy rozmiar: {path}"]

    meta = _ffprobe_json(path)
    if meta is None:
        # Brak ffprobe lub nieczytelny plik — nie blokuj twardo, ale zgłoś.
        problems.append(f"Nie udało się odczytać metadanych (ffprobe niedostępne lub uszkodzony plik): {path}")
        return problems

    fmt = meta.get("format", {})
    try:
        duration = float(fmt.get("duration", 0.0))
    except (TypeError, ValueError):
        duration = 0.0
    if duration < min_duration:
        problems.append(f"Za krótkie wideo: {duration:.2f}s < {min_duration:.2f}s")

    streams = meta.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        problems.append("Brak strumienia wideo.")
    else:
        vs = video_streams[0]
        w = int(vs.get("width") or 0)
        h = int(vs.get("height") or 0)
        if w == 0 or h == 0:
            problems.append("Nieznane wymiary klatki.")
        elif expected_aspect and not _aspect_ok(w, h, expected_aspect):
            problems.append(
                f"Proporcje {w}x{h} odbiegają od oczekiwanych {expected_aspect}."
            )

    return problems
