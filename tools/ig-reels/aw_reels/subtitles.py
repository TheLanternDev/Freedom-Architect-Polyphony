"""Wypalanie napisów na wideo przez ffmpeg drawtext — bez LLM, bez ASS plików.

Kolory marki: złoty tekst (#C5A46E) na półprzezroczystym granatowym tle (#0A0D14).
Domyślnie napisy pojawiają się w ostatnich `tail_seconds` (jeśli znamy czas trwania).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Kolory marki (style.yaml palette) — w formacie ffmpeg (0xRRGGBB).
GOLD = "0xC5A46E"
NAVY = "0x0A0D14"


def _escape_drawtext(text: str) -> str:
    """Escape znaków specjalnych ffmpeg drawtext (kolejność ma znaczenie)."""
    out = text.replace("\\", "\\\\")
    out = out.replace(":", "\\:")
    out = out.replace("'", "’")  # apostrof → typograficzny (unika łamania filtra)
    out = out.replace("%", "\\%")
    return out


def _probe_duration(path: Path) -> float | None:
    """Czas trwania wideo w sekundach (ffprobe). None gdy nieznany/brak ffprobe."""
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def burn_subtitles(
    video_path: Path,
    lines: list[str],
    dest: Path,
    *,
    duration: float | None = None,
    tail_seconds: float = 3.0,
    fontsize: int = 56,
) -> Path:
    """Wypal linie tekstu na wideo. Tekst widoczny w ostatnich `tail_seconds`.

    Re-enkoduje wideo (drawtext wymaga -c:v), audio kopiowane bez zmian.
    """
    if not video_path.is_file():
        raise FileNotFoundError(f"Brak wideo: {video_path}")
    clean = [l.strip() for l in lines if l and l.strip()]
    if not clean:
        raise RuntimeError("Brak linii tekstu do wypalenia.")
    dest.parent.mkdir(parents=True, exist_ok=True)

    dur = duration if duration is not None else _probe_duration(video_path)
    enable = ""
    if dur and dur > tail_seconds:
        start = max(0.0, dur - tail_seconds)
        enable = f":enable='gte(t,{start:.2f})'"

    # Każda linia jako osobny drawtext, ułożone pionowo wokół 72% wysokości.
    n = len(clean)
    base_y = "h*0.72"
    draws: list[str] = []
    for i, line in enumerate(clean):
        txt = _escape_drawtext(line)
        offset = (i - (n - 1) / 2) * (fontsize + 18)
        y = f"({base_y})+({offset:.0f})"
        draws.append(
            f"drawtext=text='{txt}':fontcolor={GOLD}:fontsize={fontsize}"
            f":x=(w-text_w)/2:y={y}"
            f":box=1:boxcolor={NAVY}@0.55:boxborderw=18"
            f":line_spacing=8{enable}"
        )
    vf = ",".join(draws)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "ffmpeg failed")[-800:]
        raise RuntimeError(f"ffmpeg drawtext (napisy) nie powiódł się:\n{err}")
    return dest
