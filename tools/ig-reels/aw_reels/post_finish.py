"""Post-produkcja gotowego MP4: naprawa audio (ElevenLabs) + outro blur/logo/CTA (ffmpeg)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .elevenlabs_client import synthesize_speech
from .audio_mux import normalize_audio
from .subtitles import GOLD, NAVY, _escape_drawtext, _probe_duration

# Domyślny skrypt Syeza (bez powtórzeń linii).
DEFAULT_VOICEOVER = (
    "Z Ciemności... z Pustki... budzi się Rada. "
    "Wszyscy moi Agenci schodzą się w Jedno Miejsce. "
    "Tu, gdzie jest Światło. "
    "Tu, gdzie wielogłosowość staje się Jednością."
)

CTA_LINE = "Zadaj pierwsze pytanie Rady → link w bio"
BRAND_LINE = "Architekt Wolności"
SUB_LINE = "Twoja Rada Nadzorcza"


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "ffmpeg failed")[-1200:])


def _generate_narration(dest: Path, script: str, *, voice_id: str | None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    audio = synthesize_speech(script, voice_id=voice_id)
    dest.write_bytes(audio)
    norm = dest.with_name(f"{dest.stem}-norm.mp3")
    normalize_audio(dest, norm)
    return norm


def _build_main_body(
    src: Path,
    dest: Path,
    *,
    cut_at: float,
    fade_out: float,
) -> Path:
    """Przytnij wideo przed outro + łagodne wygaszenie obrazu/dźwięku natywnego."""
    fade_start = max(0.0, cut_at - fade_out)
    vf = f"fade=t=out:st={fade_start}:d={fade_out}"
    af = f"afade=t=out:st={fade_start}:d={fade_out}"
    _run([
        "ffmpeg", "-y", "-i", str(src),
        "-t", f"{cut_at}",
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(dest),
    ])
    return dest


def _build_mixed_audio(
    src: Path,
    narration: Path,
    dest: Path,
    *,
    open_keep_s: float,
    skip_until_s: float,
    narr_delay_s: float,
    body_end_s: float,
) -> Path:
    """Audio: początek natywny → pominięcie powtórzenia → ambient → ElevenLabs od narr_delay_s."""
    body_len = body_end_s - open_keep_s
    amb_end = skip_until_s + body_len
    fc = (
        f"[0:a]atrim=0:{open_keep_s},asetpts=PTS-STARTPTS[a0];"
        f"[0:a]atrim={skip_until_s}:{amb_end},asetpts=PTS-STARTPTS,"
        f"highpass=f=180,lowpass=f=4500,volume=0.14[aamb];"
        f"[a0][aamb]concat=n=2:v=0:a=1[bed];"
        f"[1:a]adelay={int(narr_delay_s * 1000)}|{int(narr_delay_s * 1000)},"
        f"apad=whole_dur={body_end_s + 0.5}[vo];"
        f"[bed][vo]amix=inputs=2:duration=first:dropout_transition=2,volume=1.0[aout]"
    )
    _run([
        "ffmpeg", "-y",
        "-i", str(src),
        "-i", str(narration),
        "-filter_complex", fc,
        "-map", "[aout]",
        "-t", f"{body_end_s}",
        "-c:a", "aac", "-b:a", "192k",
        str(dest),
    ])
    return dest


def _mux_video_audio(video: Path, audio: Path, dest: Path) -> Path:
    _run([
        "ffmpeg", "-y",
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(dest),
    ])
    return dest


def _build_outro(
    src: Path,
    dest: Path,
    *,
    sample_at: float,
    duration: float,
) -> Path:
    """Rozmycie ostatniej klatki + czerń + logo (ring) + marka + CTA."""
    t_logo = 0.6
    t_brand = 1.0
    t_cta = 2.2
    brand = _escape_drawtext(BRAND_LINE)
    sub = _escape_drawtext(SUB_LINE)
    cta = _escape_drawtext(CTA_LINE)

    vf = (
        f"[0:v]scale=720:1280:force_original_aspect_ratio=decrease,"
        f"pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1,"
        f"boxblur=18:18:5:5,eq=brightness=-0.25:contrast=1.05,"
        f"fade=t=in:st=0:d=0.6,fade=t=out:st={duration - 0.8}:d=0.8,"
        f"drawtext=text='◎':fontsize=120:fontcolor={GOLD}@0.9:"
        f"x=(w-text_w)/2:y=h*0.38:borderw=0:enable='gte(t,{t_logo})',"
        f"drawtext=text='{brand}':fontsize=52:fontcolor={GOLD}:"
        f"x=(w-text_w)/2:y=h*0.48:borderw=3:bordercolor={NAVY}@0.85:"
        f"enable='gte(t,{t_brand})',"
        f"drawtext=text='{sub}':fontsize=36:fontcolor={GOLD}@0.95:"
        f"x=(w-text_w)/2:y=h*0.54:borderw=2:bordercolor={NAVY}@0.7:"
        f"enable='gte(t,{t_brand + 0.15})',"
        f"drawtext=text='{cta}':fontsize=30:fontcolor=white:"
        f"x=(w-text_w)/2:y=h*0.68:borderw=2:bordercolor={NAVY}@0.8:"
        f"enable='gte(t,{t_cta})'"
        f"[vout]"
    )
    _run([
        "ffmpeg", "-y",
        "-ss", f"{sample_at}",
        "-i", str(src),
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        "-filter_complex", vf,
        "-map", "[vout]", "-map", "1:a",
        "-t", f"{duration}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        str(dest),
    ])
    return dest


def _concat_videos(parts: list[Path], dest: Path) -> Path:
    list_file = dest.with_suffix(".concat.txt")
    lines = [f"file '{p.resolve()}'" for p in parts]
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(dest),
    ])
    return dest


def finish_reel(
    src_mp4: Path,
    dest_mp4: Path,
    *,
    voice_id: str | None = None,
    voiceover_script: str | None = None,
    narration_mp3: Path | None = None,
    skip_elevenlabs: bool = False,
    cut_at: float = 13.0,
    outro_seconds: float = 5.0,
    open_keep_s: float = 2.0,
    skip_until_s: float = 3.75,
    narr_delay_s: float = 8.0,
) -> Path:
    """Pełna naprawa: usuń powtórzenie audio, ElevenLabs narracja, outro blur+CTA."""
    work = dest_mp4.parent
    work.mkdir(parents=True, exist_ok=True)

    if narration_mp3 and narration_mp3.is_file():
        narr = narration_mp3
    elif skip_elevenlabs:
        narr = None
    else:
        narr_raw = work / "narration-finish.mp3"
        narr = _generate_narration(
            narr_raw,
            voiceover_script or DEFAULT_VOICEOVER,
            voice_id=voice_id,
        )

    body_end = cut_at
    main_v = work / "_main_v.mp4"
    main_mux = work / "_main_mux.mp4"

    _build_main_body(src_mp4, main_v, cut_at=body_end, fade_out=0.9)

    if narr is not None:
        main_a = work / "_main_a.m4a"
        _build_mixed_audio(
            src_mp4, narr, main_a,
            open_keep_s=open_keep_s,
            skip_until_s=skip_until_s,
            narr_delay_s=narr_delay_s,
            body_end_s=body_end,
        )
        _mux_video_audio(main_v, main_a, main_mux)
    else:
        # Tylko naprawa natywnego audio (wycięcie powtórzenia) + wygaszenie.
        main_a = work / "_main_a_fix.m4a"
        body_len = body_end - open_keep_s
        amb_end = skip_until_s + body_len
        fc = (
            f"[0:a]atrim=0:{open_keep_s},asetpts=PTS-STARTPTS[a0];"
            f"[0:a]atrim={skip_until_s}:{amb_end},asetpts=PTS-STARTPTS,"
            f"afade=t=out:st={body_end - open_keep_s - 0.9}:d=0.9[aamb];"
            f"[a0][aamb]concat=n=2:v=0:a=1[aout]"
        )
        _run([
            "ffmpeg", "-y", "-i", str(src_mp4),
            "-filter_complex", fc, "-map", "[aout]",
            "-t", f"{body_end}", "-c:a", "aac", "-b:a", "192k",
            str(main_a),
        ])
        _mux_video_audio(main_v, main_a, main_mux)

    sample_at = max(0.5, body_end - 0.35)
    outro = work / "_outro.mp4"
    _build_outro(src_mp4, outro, sample_at=sample_at, duration=outro_seconds)

    _concat_videos([main_mux, outro], dest_mp4)
    return dest_mp4
