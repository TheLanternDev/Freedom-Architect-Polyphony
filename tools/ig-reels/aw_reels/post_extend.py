"""Hybrydowe wydłużenie reela: 15s Grok → ~20s (fps + hold outro) + napisy wieloliniowe."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .subtitles import GOLD, NAVY, _escape_drawtext, _probe_duration


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "ffmpeg failed")[-1200:])


def extend_reel_hybrid(
    src: Path,
    dest: Path,
    *,
    target_duration: float = 20.0,
    target_fps: int = 30,
    onscreen_lines: list[tuple[float, float, str, int]] | None = None,
) -> Path:
    """Przyspiesz do target_fps, dopełnij ostatnią klatką do target_duration, opcjonalnie napisy."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dur = _probe_duration(src) or 15.0
    pad = max(0.0, target_duration - dur)
    vf_parts = [
        f"fps={target_fps}",
        "scale=1080:1920:force_original_aspect_ratio=decrease",
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
    ]
    if pad > 0.05:
        vf_parts.append(f"tpad=stop_mode=clone:stop_duration={pad:.3f}")
    vf = ",".join(vf_parts)
    tmp = dest.with_suffix(".tmp.mp4")
    _run([
        "ffmpeg", "-y", "-i", str(src),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(tmp),
    ])
    out = tmp
    if onscreen_lines:
        filters: list[str] = []
        for start, end, text, size in onscreen_lines:
            esc = _escape_drawtext(text)
            filters.append(
                f"drawtext=text='{esc}':fontsize={size}:fontcolor={GOLD}:"
                f"borderw=2:bordercolor={NAVY}@0.55:"
                f"x=(w-text_w)/2:y=h*0.38:"
                f"enable='between(t,{start},{end})'"
            )
        _run([
            "ffmpeg", "-y", "-i", str(out),
            "-vf", ",".join(filters),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy",
            str(dest),
        ])
        out.unlink(missing_ok=True)
    else:
        tmp.rename(dest)
    return dest
