"""Wielogłosowa narracja Rady — ElevenLabs per agent + timeline (ffmpeg)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import yaml

from .config import BRAND_DIR
from .elevenlabs_client import list_voices, synthesize_speech
from .script_reason import normalize_for_tts

DEFAULT_VOICES = BRAND_DIR / "agent_voices.yaml"
DEFAULT_TIMELINE = BRAND_DIR / "reel3_brief_narration.yaml"

# LUFS per rola — szept równy między agentami, Syez wyraźniejszy, CTA najgłośniejszy.
ROLE_LUFS: dict[str, float] = {
    "whisper": -20.0,
    "lead": -15.5,
    "cta": -12.5,
}


def load_agent_voices(path: Path | None = None) -> dict:
    p = path or DEFAULT_VOICES
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def load_narration_timeline(path: Path | None = None) -> dict:
    p = path or DEFAULT_TIMELINE
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _resolve_voice_id(agent: str, voices_cfg: dict, account_voices: list[dict] | None) -> tuple[str, float]:
    agents = voices_cfg.get("agents") or {}
    if agent not in agents:
        raise KeyError(f"Brak głosu dla agenta '{agent}' w agent_voices.yaml")
    entry = agents[agent]
    speed = float(entry.get("speed", 1.0))
    vid = str(entry.get("voice_id", "")).strip()
    name = str(entry.get("voice_name", "")).strip().lower()
    if account_voices and name:
        for v in account_voices:
            if str(v.get("name", "")).strip().lower() == name:
                vid = str(v.get("voice_id", vid))
                break
    if not vid:
        raise RuntimeError(f"Brak voice_id dla agenta {agent}")
    return vid, speed


def _role_voice_settings(role: str) -> dict | None:
    if role == "cta":
        return {"stability": 0.62, "similarity_boost": 0.8, "style": 0.42, "use_speaker_boost": True}
    if role == "whisper":
        return {"stability": 0.58, "similarity_boost": 0.72, "style": 0.12, "use_speaker_boost": True}
    return None


def _loudnorm_clip(src: Path, dest: Path, *, target_lufs: float) -> Path:
    """Normalizuj pojedynczy klip do docelowego LUFS."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    loudnorm = f"loudnorm=I={target_lufs}:TP=-1.0:LRA=8"
    cmd = ["ffmpeg", "-y", "-i", str(src), "-af", loudnorm, str(dest)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "loudnorm failed")[-800:])
    return dest


def _atempo_chain(ratio: float) -> str:
    """ffmpeg atempo akceptuje 0.5–2.0; łańcz przy większych przyspieszeniach."""
    filters: list[str] = []
    remaining = ratio
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")
    return ",".join(filters)


def _probe_duration(path: Path) -> float | None:
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
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def build_council_narration(
    dest: Path,
    *,
    timeline_path: Path | None = None,
    voices_path: Path | None = None,
    resolve_names: bool = True,
) -> Path:
    """Zbuduj jeden MP3 z segmentów mowy na osi czasu (wielu agentów)."""
    timeline = load_narration_timeline(timeline_path)
    voices_cfg = load_agent_voices(voices_path)
    duration = float(timeline.get("reel_duration_s", 15))
    segments = sorted(timeline.get("segments") or [], key=lambda s: float(s["start_s"]))

    if not segments:
        raise ValueError("Pusty timeline narracji")

    account = list_voices() if resolve_names else None
    model_id = voices_cfg.get("model_id")

    with tempfile.TemporaryDirectory(prefix="aw-council-vo-") as tmp:
        tmp_path = Path(tmp)
        inputs: list[str] = []
        filters: list[str] = []

        for i, seg in enumerate(segments):
            speaker = str(seg["speaker"])
            text = normalize_for_tts(str(seg["text"]))
            start_s = float(seg["start_s"])
            role = str(seg.get("role", "lead"))
            target_lufs = ROLE_LUFS.get(role, ROLE_LUFS["lead"])
            vid, agent_speed = _resolve_voice_id(speaker, voices_cfg, account)
            speed = float(seg["speed"]) if seg.get("speed") is not None else agent_speed
            voice_settings = _role_voice_settings(role)

            raw_mp3 = tmp_path / f"{i:02d}-{speaker}-raw.mp3"
            norm_mp3 = tmp_path / f"{i:02d}-{speaker}.mp3"
            raw_mp3.write_bytes(
                synthesize_speech(
                    text,
                    voice_id=vid,
                    model_id=model_id,
                    speed=speed,
                    voice_settings=voice_settings,
                )
            )
            _loudnorm_clip(raw_mp3, norm_mp3, target_lufs=target_lufs)

            clip_dur = _probe_duration(norm_mp3) or 0.0
            budget_s = max(0.25, duration - start_s - 0.08)
            if clip_dur > budget_s:
                tempo = min(clip_dur / budget_s, 1.4)
                sped = tmp_path / f"{i:02d}-{speaker}-sped.mp3"
                sped_filter = _atempo_chain(tempo)
                proc = subprocess.run(
                    [
                        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(norm_mp3), "-af", sped_filter, str(sped),
                    ],
                    capture_output=True,
                    text=True,
                )
                if proc.returncode != 0:
                    raise RuntimeError((proc.stderr or proc.stdout or "atempo failed")[-800:])
                norm_mp3 = sped
                clip_dur = _probe_duration(norm_mp3) or clip_dur / tempo
            end_s = start_s + clip_dur
            if end_s > duration + 0.05:
                raise ValueError(
                    f"Segment {speaker} @{start_s}s trwa {clip_dur:.2f}s → kończy się przy {end_s:.2f}s "
                    f"(limit {duration}s). Skróć tekst lub przesuń start."
                )

            inputs.extend(["-i", str(norm_mp3)])
            delay_ms = int(start_s * 1000)
            filters.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")

        mix_labels = "".join(f"[a{i}]" for i in range(len(segments)))
        filters.append(
            f"{mix_labels}amix=inputs={len(segments)}:duration=longest:"
            f"dropout_transition=0:normalize=0,apad=whole_dur={duration:.3f},"
            f"loudnorm=I=-14:TP=-0.8:LRA=9[out]"
        )

        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]", str(dest)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "ffmpeg mix failed")[-1200:])

    return dest


def timeline_to_voiceover_script(timeline_path: Path | None = None) -> str:
    """Pełny skrypt Syeza (lead + CTA) — fallback dla publish/script-plan."""
    timeline = load_narration_timeline(timeline_path)
    parts: list[str] = []
    for seg in timeline.get("segments") or []:
        if str(seg.get("speaker")) == "Syez":
            parts.append(str(seg["text"]).strip())
    return " ".join(parts)
