from __future__ import annotations

import subprocess
from pathlib import Path


def _probe_duration(path: Path) -> float | None:
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


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

    video_dur = _probe_duration(video_path)
    duration_flag: list[str] = []
    if video_dur and video_dur > 0:
        duration_flag = ["-t", f"{video_dur:.3f}"]

    if mix_ambient:
        # Pad ambient; sidechain ducking pod narrację; narracja do pełnej długości klipu.
        pad_dur = video_dur or 15.0
        filter_complex = (
            f"[0:a]apad=whole_dur={pad_dur:.3f}[va0];"
            f"[1:a]apad=whole_dur={pad_dur:.3f}[na0];"
            "[na0]asplit=2[sc][na];"
            "[va0][sc]sidechaincompress=threshold=0.015:ratio=10:attack=60:release=350"
            f":level_sc=1.0[vad];"
            f"[vad]volume={ambient_volume}[va];"
            "[va][na]amix=inputs=2:duration=longest:dropout_transition=0,"
            "alimiter=limit=0.98:attack=5:release=50[aout]"
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
            *duration_flag,
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
            *duration_flag,
            str(dest),
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "ffmpeg failed")[-800:]
        raise RuntimeError(f"ffmpeg mux nie powiódł się:\n{err}")
    return dest
