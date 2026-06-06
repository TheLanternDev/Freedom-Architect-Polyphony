from __future__ import annotations

import subprocess
from pathlib import Path


def normalize_audio(input_path: Path, dest: Path | None = None) -> Path:
    """Loudnorm narracji/audio do bezpiecznych poziomów IG (peak ~ -1 dBTP).

    Działa na MP3 (narracja) lub MP4 (audio w wideo). Zwraca ścieżkę znormalizowaną.
    Parametry: I=-16 LUFS (typowe dla social), TP=-1.0 dBTP, LRA=11.
    """
    if not input_path.is_file():
        raise FileNotFoundError(f"Brak pliku audio: {input_path}")
    if dest is None:
        dest = input_path.with_name(f"{input_path.stem}-norm{input_path.suffix}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    loudnorm = "loudnorm=I=-16:TP=-1.0:LRA=11"
    is_video = input_path.suffix.lower() in (".mp4", ".mov", ".m4v")
    if is_video:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", loudnorm,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            str(dest),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", loudnorm,
            str(dest),
        ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "ffmpeg failed")[-800:]
        raise RuntimeError(f"ffmpeg loudnorm nie powiódł się:\n{err}")
    return dest


def mux_narration(
    video_path: Path,
    narration_path: Path,
    dest: Path,
    *,
    mix_ambient: bool = False,
    ambient_volume: float = 0.12,
) -> Path:
    """Połącz MP4 z narracją ElevenLabs. Domyślnie zastępuje ścieżkę wideo."""
    if not video_path.is_file():
        raise FileNotFoundError(f"Brak wideo: {video_path}")
    if not narration_path.is_file():
        raise FileNotFoundError(f"Brak narracji: {narration_path}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    if mix_ambient:
        filter_complex = (
            f"[0:a]volume={ambient_volume}[va];[1:a]volume=1[na];"
            "[va][na]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(narration_path),
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(dest),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(narration_path),
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(dest),
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "ffmpeg failed")[-800:]
        raise RuntimeError(f"ffmpeg mux nie powiódł się:\n{err}")
    return dest
