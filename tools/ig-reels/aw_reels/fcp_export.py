"""Pakiet montażowy Final Cut Pro: klipy Ken Burns + FCPXML + media."""

from __future__ import annotations

import math
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import yaml

from .config import ROOT, get_elevenlabs_voice_id
from .council_assets import DEFAULT_MANIFEST
from .subtitles import _probe_duration

FCP_TIMELINE = ROOT / "brand" / "fcp_rada_timeline.yaml"
DEFAULT_SYEZ = ROOT / "assets" / "council" / "syez.yaml"


@dataclass(frozen=True)
class AgentSlot:
    index: int
    agent_id: str
    visual: str
    role: str
    tagline: str
    image_path: Path | None
    duration_s: float
    start_s: float


@dataclass(frozen=True)
class SyezEntry:
    agent_id: str
    role: str
    tagline: str
    narration: str
    image_path: Path | None


@dataclass(frozen=True)
class FcpTimelineSpec:
    title: str
    width: int
    height: int
    fps: int
    total_s: float
    opening_s: float
    opening_scale: str
    syez_s: float
    closing_s: float
    ambient_volume: float = 0.28
    ambient_sidechain_threshold: float = 0.02
    ambient_sidechain_ratio: float = 10.0
    ambient_attack_ms: int = 300
    ambient_release_ms: int = 900


def load_manifest_entries(manifest: Path | None = None) -> list[dict]:
    path = manifest or DEFAULT_MANIFEST
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data.get("order", []))


def load_syez_entry(
    path: Path | None = None,
    *,
    portraits_dir: Path | None = None,
) -> SyezEntry:
    p = path or DEFAULT_SYEZ
    if not p.is_file():
        return SyezEntry(
            agent_id="Syez",
            role="Syntetyzer i orkiestrator",
            tagline="Lustro dziewięciu głosów — bez własnej perspektywy",
            narration="",
            image_path=None,
        )
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    fname = data.get("file")
    img: Path | None = None
    if fname and portraits_dir is not None:
        candidate = portraits_dir / fname
        if candidate.is_file():
            img = candidate
    elif fname:
        council = p.parent / fname
        if council.is_file():
            img = council
    narration = str(data.get("narration", "")).strip()
    return SyezEntry(
        agent_id=str(data.get("id", "Syez")),
        role=str(data.get("role", "")),
        tagline=str(data.get("tagline", "")),
        narration=narration,
        image_path=img,
    )


def load_timeline_spec(path: Path | None = None) -> FcpTimelineSpec:
    p = path or FCP_TIMELINE
    if not p.is_file():
        return FcpTimelineSpec(
            title="Rada Polyphony — Moj Swiat",
            width=1080,
            height=1920,
            fps=30,
            total_s=24.5,
            opening_s=3.2,
            opening_scale="fit",
            syez_s=4.5,
            closing_s=3.0,
        )
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return FcpTimelineSpec(
        title=str(data.get("title", "Rada Polyphony")),
        width=int(data.get("width", 1080)),
        height=int(data.get("height", 1920)),
        fps=int(data.get("fps", 30)),
        total_s=float(data.get("total_s", 24.5)),
        opening_s=float(data.get("opening_s", 3.2)),
        opening_scale=str(data.get("opening_scale", "fit")),
        syez_s=float(data.get("syez_s", 4.5)),
        closing_s=float(data.get("closing_s", 3.0)),
        ambient_volume=float(data.get("ambient_volume", 0.28)),
        ambient_sidechain_threshold=float(data.get("ambient_sidechain_threshold", 0.02)),
        ambient_sidechain_ratio=float(data.get("ambient_sidechain_ratio", 10)),
        ambient_attack_ms=int(data.get("ambient_attack_ms", 300)),
        ambient_release_ms=int(data.get("ambient_release_ms", 900)),
    )


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "ffmpeg failed")[-1200:])


def _agent_label_filters(width: int, height: int, *, name: str, role: str, tagline: str) -> str:
    """Napisy dolne — nie zasłaniają twarzy (dolna ćwiartka)."""
    gold = "0xE8D5A3"
    navy = "0x0A0D14"
    base = (
        f"fontsize=48:fontcolor={gold}:borderw=2:bordercolor={navy}@0.7:"
        f"box=1:boxcolor={navy}@0.45:boxborderw=12:x=(w-text_w)/2"
    )
    parts: list[str] = []
    if name:
        parts.append(
            f"drawtext=text='{_escape_drawtext(name)}':{base}:y={int(height * 0.78)}"
        )
    if role:
        parts.append(
            f"drawtext=text='{_escape_drawtext(role)}':fontsize=34:fontcolor={gold}:"
            f"borderw=1:bordercolor={navy}@0.6:box=1:boxcolor={navy}@0.4:boxborderw=8:"
            f"x=(w-text_w)/2:y={int(height * 0.84)}"
        )
    if tagline:
        parts.append(
            f"drawtext=text='{_escape_drawtext(tagline)}':fontsize=26:fontcolor={gold}:"
            f"borderw=1:bordercolor={navy}@0.5:box=1:boxcolor={navy}@0.35:boxborderw=6:"
            f"x=(w-text_w)/2:y={int(height * 0.89)}"
        )
    return ",".join(parts)


def _ken_burns_clip(
    src: Path,
    dest: Path,
    *,
    duration_s: float,
    width: int,
    height: int,
    fps: int,
    agent_name: str = "",
    role: str = "",
    tagline: str = "",
) -> None:
    """Statyczny portret → Ken Burns + imię i opis agenta u dołu."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    d = max(duration_s, 0.5)
    frames = max(1, int(round(d * fps)))
    tmp = dest.with_suffix(".kb.tmp.mp4")
    vf_kb = (
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width * 2}:{height * 2},"
        f"zoompan=z='min(1.0+0.0006*on,1.06)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps},"
        f"format=yuv420p"
    )
    _run([
        "ffmpeg", "-y", "-loop", "1", "-framerate", str(fps), "-i", str(src),
        "-vf", vf_kb,
        "-frames:v", str(frames),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-an", str(tmp),
    ])
    labels = _agent_label_filters(width, height, name=agent_name, role=role, tagline=tagline)
    if labels:
        _run([
            "ffmpeg", "-y", "-i", str(tmp),
            "-vf", labels,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-an", str(dest),
        ])
        tmp.unlink(missing_ok=True)
    else:
        tmp.replace(dest)


def _escape_drawtext(text: str) -> str:
    out = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")
    return out


def _mandala_closing_clip(
    portraits: list[Path],
    dest: Path,
    *,
    duration_s: float,
    width: int,
    height: int,
    fps: int,
) -> None:
    """Końcówka: 9 portretów w kole + złote CTA (Syez = audio w FCP, nie twarz)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    d = max(duration_s, 1.0)
    frames = max(1, int(round(d * fps)))
    thumb_w, thumb_h = 140, 200
    cx, cy = width // 2, int(height * 0.40)
    radius = int(width * 0.27)

    cmd: list[str] = ["ffmpeg", "-y"]
    cmd.extend(["-f", "lavfi", "-i", f"color=c=0x0A0D14:s={width}x{height}:d={d}:r={fps}"])
    for p in portraits:
        cmd.extend(["-loop", "1", "-framerate", str(fps), "-t", f"{d:.3f}", "-i", str(p)])

    parts: list[str] = []
    last = "[0:v]"
    n = min(len(portraits), 9)
    for i in range(n):
        inp = f"[{i + 1}:v]"
        tag = f"p{i}"
        out = f"v{i}"
        angle = (2 * math.pi * i / n) - math.pi / 2
        x = int(cx + radius * math.cos(angle) - thumb_w / 2)
        y = int(cy + radius * math.sin(angle) - thumb_h / 2)
        parts.append(
            f"{inp}scale={thumb_w}:{thumb_h}:force_original_aspect_ratio=decrease,"
            f"pad={thumb_w}:{thumb_h}:(ow-iw)/2:(oh-ih)/2[{tag}]"
        )
        parts.append(f"{last}[{tag}]overlay=x={x}:y={y}:format=auto[{out}]")
        last = f"[{out}]"

    texts = [
        (52, int(height * 0.68), "RADA NADZORCZA „MÓJ ŚWIAT”"),
        (40, int(height * 0.74), "9 Agentów. Jedna Polyfonia."),
        (36, int(height * 0.79), "Architekt Wolności"),
        (32, int(height * 0.84), "Twój system. Twoja wolność."),
        (24, int(height * 0.90), "Founders Cohort • 10 miejsc przy stole • link w bio"),
    ]
    dt_chain = last
    for j, (size, ypos, line) in enumerate(texts):
        esc = _escape_drawtext(line)
        nxt = f"[dt{j}]"
        parts.append(
            f"{dt_chain}drawtext=text='{esc}':fontsize={size}:fontcolor=0xE8D5A3:"
            f"borderw=2:bordercolor=0x0A0D14@0.6:"
            f"x=(w-text_w)/2:y={ypos}{nxt}"
        )
        dt_chain = nxt

    parts.append(
        f"{dt_chain}zoompan=z='min(1.0+0.00025*on,1.03)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps},format=yuv420p[outv]"
    )
    cmd.extend(["-filter_complex", ";".join(parts), "-map", "[outv]",
                "-frames:v", str(frames), "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-an", str(dest)])
    _run(cmd)


def _placeholder_clip(
    dest: Path,
    *,
    duration_s: float,
    width: int,
    height: int,
    fps: int,
    label: str,
) -> None:
    """Czarne tło + etykieta (brak PNG, np. Kidi)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    esc = label.replace(":", "\\:").replace("'", "’")
    _run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x0A0D14:s={width}x{height}:d={duration_s}:r={fps}",
        "-vf", f"drawtext=text='{esc}':fontsize=42:fontcolor=0xE8D5A3:"
               f"x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(dest),
    ])


def _file_uri(path: Path) -> str:
    return "file://" + quote(path.resolve().as_posix(), safe="/:")


def _clip_has_audio(path: Path) -> bool:
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return "audio" in (proc.stdout or "")
    except OSError:
        return False


def build_agent_slots(
    entries: list[dict],
    spec: FcpTimelineSpec,
    council_dir: Path,
) -> list[AgentSlot]:
    montage_s = spec.total_s - spec.opening_s - spec.syez_s - spec.closing_s
    n = len(entries)
    each = montage_s / n if n else montage_s
    slots: list[AgentSlot] = []
    t = spec.opening_s
    for i, entry in enumerate(entries, start=1):
        fname = entry.get("file")
        img = (council_dir / fname) if fname else None
        if img and not img.is_file():
            img = None
        slots.append(AgentSlot(
            index=i,
            agent_id=str(entry.get("id", f"agent{i}")),
            visual=str(entry.get("visual", "")),
            role=str(entry.get("role", "")),
            tagline=str(entry.get("tagline", "")),
            image_path=img if img and img.is_file() else None,
            duration_s=each,
            start_s=t,
        ))
        t += each
    return slots


def render_fcp_clips(
    slots: list[AgentSlot],
    clips_dir: Path,
    spec: FcpTimelineSpec,
) -> list[Path]:
    paths: list[Path] = []
    for slot in slots:
        name = f"{slot.index:02d}-{slot.agent_id}.mp4"
        dest = clips_dir / name
        if slot.image_path and slot.image_path.is_file():
            _ken_burns_clip(
                slot.image_path, dest,
                duration_s=slot.duration_s,
                width=spec.width, height=spec.height, fps=spec.fps,
                agent_name=slot.agent_id,
                role=slot.role,
                tagline=slot.tagline,
            )
        else:
            _placeholder_clip(
                dest,
                duration_s=slot.duration_s,
                width=spec.width, height=spec.height, fps=spec.fps,
                label=f"{slot.agent_id} — wygeneruj w FCP/Grok",
            )
        paths.append(dest)
    return paths


def _time_r(seconds: float, fps: int) -> str:
    frames = max(1, round(seconds * fps))
    return f"{frames}/{fps}s"


def render_syez_clip(
    entry: SyezEntry,
    dest: Path,
    spec: FcpTimelineSpec,
) -> Path:
    """Scena Syeza — portret Ken Burns + napisy (jak agenci)."""
    if entry.image_path and entry.image_path.is_file():
        _ken_burns_clip(
            entry.image_path,
            dest,
            duration_s=spec.syez_s,
            width=spec.width,
            height=spec.height,
            fps=spec.fps,
            agent_name=entry.agent_id,
            role=entry.role,
            tagline=entry.tagline,
        )
    else:
        _placeholder_clip(
            dest,
            duration_s=spec.syez_s,
            width=spec.width,
            height=spec.height,
            fps=spec.fps,
            label="Syez — dodaj Syez.png do Portraits/",
        )
    return dest


def syez_start_s(spec: FcpTimelineSpec, agent_count: int) -> float:
    montage_s = spec.total_s - spec.opening_s - spec.syez_s - spec.closing_s
    each = montage_s / agent_count if agent_count else 0.0
    return spec.opening_s + each * agent_count


def write_fcpxml(
    bundle_dir: Path,
    spec: FcpTimelineSpec,
    opening_clip: Path | None,
    agent_clips: list[tuple[AgentSlot, Path]],
    syez_clip: Path | None,
    closing_clip: Path | None,
    *,
    narration_clip: Path | None = None,
    ambient_clip: Path | None = None,
) -> Path:
    """FCPXML 1.10 zgodny z DTD: jeden format, asset + media-rep."""
    fps = spec.fps
    fd = f"100/{fps * 100}s"
    total_frames = max(1, round(spec.total_s * fps))

    resources = ET.Element("resources")
    ET.SubElement(resources, "format", {
        "id": "r1",
        "name": f"FFVideoFormat{spec.height}p{fps}",
        "frameDuration": fd,
        "width": str(spec.width),
        "height": str(spec.height),
        "colorSpace": "1-1-1 (Rec. 709)",
    })
    # Audio-only assety wymagają formatu bez channels/sampleRate (DTD FCP 1.10).
    ET.SubElement(resources, "format", {
        "id": "r2",
        "name": "FFVideoFormatRateUndefined",
    })

    spine_items: list[tuple[str, str, float]] = []  # (asset_id, display_name, duration_s)
    aid = 0
    syez_narration_id: str | None = None
    syez_narration_dur_s = spec.syez_s
    ambient_bed_id: str | None = None

    def add_asset(path: Path, duration_s: float, display_name: str | None = None) -> str:
        nonlocal aid
        aid += 1
        a_id = f"a{aid}"
        label = display_name or path.stem
        has_audio = _clip_has_audio(path)
        asset = ET.SubElement(resources, "asset", {
            "id": a_id,
            "name": label,
            "uid": label.replace(" ", "-"),
            "start": "0s",
            "duration": _time_r(duration_s, fps),
            "hasVideo": "1",
            "hasAudio": "1" if has_audio else "0",
            "format": "r1",
            "videoSources": "1",
            **({"audioSources": "1"} if has_audio else {}),
        })
        ET.SubElement(asset, "media-rep", {
            "kind": "original-media",
            "src": _file_uri(path),
        })
        spine_items.append((a_id, label, duration_s))
        return a_id

    def add_audio_asset(path: Path, duration_s: float, display_name: str) -> str:
        nonlocal aid
        aid += 1
        a_id = f"a{aid}"
        asset = ET.SubElement(resources, "asset", {
            "id": a_id,
            "name": display_name,
            "uid": display_name.replace(" ", "-"),
            "start": "0s",
            "duration": _time_r(duration_s, fps),
            "hasVideo": "0",
            "hasAudio": "1",
            "format": "r2",
            "audioSources": "1",
            "audioChannels": "2",
            "audioRate": "48000",
        })
        ET.SubElement(asset, "media-rep", {
            "kind": "original-media",
            "src": _file_uri(path),
        })
        return a_id

    if opening_clip and opening_clip.is_file():
        add_asset(opening_clip, spec.opening_s, "Opening")
    for slot, clip in agent_clips:
        label = slot.agent_id
        if slot.role:
            label = f"{slot.agent_id} — {slot.role}"
        add_asset(clip, slot.duration_s, label)
    if syez_clip and syez_clip.is_file():
        add_asset(syez_clip, spec.syez_s, "Syez — lustro Rady")
    if closing_clip and closing_clip.is_file():
        add_asset(closing_clip, spec.closing_s, "Closing Mandala")

    if narration_clip and narration_clip.is_file():
        syez_narration_dur_s = _probe_duration(narration_clip) or spec.syez_s
        syez_narration_id = add_audio_asset(
            narration_clip, syez_narration_dur_s, "Syez narration",
        )
    if ambient_clip and ambient_clip.is_file():
        ambient_bed_id = add_audio_asset(
            ambient_clip, spec.total_s, "Ambient bed (ducked)",
        )

    duration_label = f"{spec.total_s:g}s"
    lib = ET.Element("library")
    event = ET.SubElement(lib, "event", {"name": spec.title})
    project = ET.SubElement(event, "project", {"name": f"{spec.title} {duration_label}"})
    seq = ET.SubElement(project, "sequence", {
        "format": "r1",
        "duration": f"{total_frames}/{fps}s",
        "tcStart": "0s",
        "tcFormat": "NDF",
        "audioLayout": "stereo",
        "audioRate": "48k",
    })
    spine = ET.SubElement(seq, "spine")

    for i, (a_id, label, dur_s) in enumerate(spine_items):
        attrs = {
            "ref": a_id,
            "name": label,
            "duration": _time_r(dur_s, fps),
            "tcFormat": "NDF",
        }
        if i == 0:
            attrs["offset"] = "0s"
        clip_el = ET.SubElement(spine, "asset-clip", attrs)
        if i == 0 and ambient_bed_id:
            ET.SubElement(clip_el, "asset-clip", {
                "ref": ambient_bed_id,
                "lane": "-2",
                "offset": "0s",
                "name": "Ambient bed (ducked)",
                "duration": _time_r(spec.total_s, fps),
                "format": "r2",
                "audioRole": "music",
                "tcFormat": "NDF",
            })
        if syez_narration_id and label == "Syez — lustro Rady":
            ET.SubElement(clip_el, "asset-clip", {
                "ref": syez_narration_id,
                "lane": "-1",
                "offset": "0s",
                "name": "Syez narration",
                "duration": _time_r(syez_narration_dur_s, fps),
                "format": "r2",
                "audioRole": "dialogue",
                "tcFormat": "NDF",
            })

    root = ET.Element("fcpxml", {"version": "1.10"})
    root.append(resources)
    root.append(lib)

    out = bundle_dir / "Rada-Polyphony.fcpxml"
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    # DOCTYPE wymagany przez FCP do walidacji DTD
    xml_body = ET.tostring(root, encoding="unicode")
    out.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + xml_body + "\n",
        encoding="utf-8",
    )
    return out


def _build_ambient_bed(
    dest: Path,
    *,
    spec: FcpTimelineSpec,
    seed_video: Path | None,
    narration_clip: Path | None,
    syez_start_s: float,
) -> Path | None:
    """Pełny podkład ambient (24.5s) z duckingiem sidechain pod narrację Syeza."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = spec.total_s
    tmp_dir = dest.parent / ".ambient-tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    looped = tmp_dir / "ambient-loop.wav"
    sidechain = tmp_dir / "narration-pad.wav"

    if seed_video and seed_video.is_file() and _clip_has_audio(seed_video):
        _run([
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(seed_video),
            "-t", f"{total:.3f}",
            "-vn", "-ac", "2", "-ar", "48000",
            "-af", (
                f"volume={spec.ambient_volume},"
                "afade=t=in:st=0:d=0.6,"
                f"afade=t=out:st={max(0, total - 0.8):.3f}:d=0.8"
            ),
            str(looped),
        ])
    else:
        _run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"anoisesrc=color=pink:duration={total:.3f}:sample_rate=48000:amplitude=0.02",
            "-af", "lowpass=f=600,aecho=0.7:0.85:1200:0.3,"
                   f"volume={spec.ambient_volume * 0.6}",
            "-ac", "2", str(looped),
        ])

    sc_filter = (
        f"[0:a][1:a]sidechaincompress="
        f"threshold={spec.ambient_sidechain_threshold}:"
        f"ratio={spec.ambient_sidechain_ratio}:"
        f"attack={spec.ambient_attack_ms}:"
        f"release={spec.ambient_release_ms}:"
        f"level_sc=1[outa]"
    )

    if narration_clip and narration_clip.is_file():
        delay_ms = max(0, int(round(syez_start_s * 1000)))
        _run([
            "ffmpeg", "-y", "-i", str(narration_clip),
            "-af", f"adelay={delay_ms}|{delay_ms},apad=whole_dur={int(total * 1000)}",
            "-t", f"{total:.3f}",
            "-ac", "2", "-ar", "48000",
            str(sidechain),
        ])
        _run([
            "ffmpeg", "-y", "-i", str(looped), "-i", str(sidechain),
            "-filter_complex", sc_filter,
            "-map", "[outa]", "-t", f"{total:.3f}",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(dest),
        ])
    else:
        _run([
            "ffmpeg", "-y", "-i", str(looped),
            "-t", f"{total:.3f}",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(dest),
        ])

    for f in tmp_dir.iterdir():
        f.unlink(missing_ok=True)
    tmp_dir.rmdir()
    return dest if dest.is_file() else None


def _generate_syez_narration(
    bundle: Path,
    script: str,
    *,
    voice_id: str | None = None,
) -> Path | None:
    if not script.strip():
        return None
    from .audio_mux import normalize_audio
    from .elevenlabs_client import synthesize_speech

    audio_dir = bundle / "Audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    raw = audio_dir / "10-syez-narration-raw.mp3"
    out = audio_dir / "10-syez-narration.mp3"
    raw.write_bytes(synthesize_speech(script, voice_id=voice_id or get_elevenlabs_voice_id()))
    normalize_audio(raw, out)
    raw.unlink(missing_ok=True)
    return out


def build_fcp_bundle(
    dest: Path,
    *,
    manifest: Path | None = None,
    seed_video: Path | None = None,
    sync_icloud: bool = True,
    narrate_syez: bool = False,
    syez_config: Path | None = None,
    voice_id: str | None = None,
) -> Path:
    """Zbuduj folder bundle: Media/clips, FCPXML, README."""
    spec = load_timeline_spec()
    import shutil

    manifest_path = manifest or DEFAULT_MANIFEST
    entries = load_manifest_entries(manifest_path)
    bundle = dest.resolve()
    clips_dir = bundle / "Clips"
    portraits_dir = bundle / "Portraits"
    council_dir = manifest_path.parent
    bundle.mkdir(parents=True, exist_ok=True)
    if clips_dir.exists():
        for old in clips_dir.glob("*.mp4"):
            old.unlink()
    clips_dir.mkdir(parents=True, exist_ok=True)
    portraits_dir.mkdir(parents=True, exist_ok=True)

    # Kopiuj PNG do bundle — samowystarczalny pakiet dla FCP
    for entry in entries:
        fname = entry.get("file")
        if not fname:
            continue
        src_png = council_dir / fname
        if src_png.is_file():
            shutil.copy2(src_png, portraits_dir / fname)

    syez_yaml = syez_config or DEFAULT_SYEZ
    syez_src = yaml.safe_load(syez_yaml.read_text(encoding="utf-8")) if syez_yaml.is_file() else {}
    syez_fname = syez_src.get("file") if syez_src else None
    if syez_fname:
        syez_png = council_dir / syez_fname
        if syez_png.is_file():
            shutil.copy2(syez_png, portraits_dir / syez_fname)

    slots = build_agent_slots(entries, spec, portraits_dir)
    syez_entry = load_syez_entry(syez_yaml, portraits_dir=portraits_dir)
    agent_paths = render_fcp_clips(slots, clips_dir, spec)

    opening: Path | None = None
    if seed_video and seed_video.is_file():
        opening = clips_dir / "00-opening-seed.mp4"
        w, h, fps = spec.width, spec.height, spec.fps
        if spec.opening_scale == "fill":
            opening_vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},fps={fps}"
            )
        else:
            # fit: oddalenie — cała szerokość seeda widoczna, letterbox góra/dół
            opening_vf = (
                f"scale={w}:-2,"
                f"pad={w}:{h}:0:(oh-ih)/2:color=0x0A0D14,"
                f"fps={fps}"
            )
        _run([
            "ffmpeg", "-y", "-i", str(seed_video),
            "-t", f"{spec.opening_s:.3f}",
            "-map", "0:v:0",
            "-vf", opening_vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-an", "-pix_fmt", "yuv420p",
            str(opening),
        ])
    else:
        opening = clips_dir / "00-opening.mp4"
        _placeholder_clip(
            opening, duration_s=spec.opening_s,
            width=spec.width, height=spec.height, fps=spec.fps,
            label="Opening — neural web + tekst",
        )

    syez_clip = clips_dir / "10-Syez.mp4"
    render_syez_clip(syez_entry, syez_clip, spec)

    closing = clips_dir / "11-Closing.mp4"
    portrait_paths = [
        s.image_path for s in slots
        if s.image_path and s.image_path.is_file()
    ]
    if len(portrait_paths) >= 3:
        _mandala_closing_clip(
            portrait_paths[:9],
            closing,
            duration_s=spec.closing_s,
            width=spec.width, height=spec.height, fps=spec.fps,
        )
    else:
        _placeholder_clip(
            closing, duration_s=spec.closing_s,
            width=spec.width, height=spec.height, fps=spec.fps,
            label="Closing — brak portretów",
        )

    narration_path: Path | None = None
    stale_narration = bundle / "Audio" / "10-syez-narration.mp3"
    if narrate_syez and syez_entry.narration:
        try:
            narration_path = _generate_syez_narration(
                bundle, syez_entry.narration, voice_id=voice_id,
            )
        except Exception as exc:
            (bundle / "Audio" / "NARRATION_ERROR.txt").write_text(str(exc), encoding="utf-8")
            narration_path = None
    elif stale_narration.is_file():
        stale_narration.unlink()

    ambient_path: Path | None = bundle / "Audio" / "00-ambient-bed.mp3"
    try:
        _build_ambient_bed(
            ambient_path,
            spec=spec,
            seed_video=seed_video,
            narration_clip=narration_path,
            syez_start_s=syez_start_s(spec, len(slots)),
        )
    except Exception as exc:
        (bundle / "Audio" / "AMBIENT_ERROR.txt").write_text(str(exc), encoding="utf-8")
        ambient_path = None
    if ambient_path and not ambient_path.is_file():
        ambient_path = None

    pairs = list(zip(slots, agent_paths))
    xml_path = write_fcpxml(
        bundle, spec, opening, pairs, syez_clip, closing,
        narration_clip=narration_path,
        ambient_clip=ambient_path,
    )

    readme = bundle / "README-FCP.md"
    agents = "\n".join(
        f"| {s.index} | {s.agent_id} | {s.role} | {s.tagline} | {s.duration_s:.2f}s | "
        f"{'✓' if s.image_path else 'placeholder'} |"
        for s in slots
    )
    syez_start = syez_start_s(spec, len(slots))
    closing_start = syez_start + spec.syez_s
    agent_each = (spec.total_s - spec.opening_s - spec.syez_s - spec.closing_s) / max(len(slots), 1)
    ambient_note = (
        f"- **Ambient:** `{ambient_path.name}` na lane -2 (cały film, ducking pod Syeza).\n"
        if ambient_path and ambient_path.is_file()
        else ""
    )
    if narration_path and narration_path.is_file():
        audio_note = (
            f"{ambient_note}"
            f"- **Syez (narracja):** `{narration_path.name}` na lane -1 pod `{syez_clip.name}`.\n"
        )
    else:
        audio_note = (
            f"{ambient_note}"
            "- **Syez (audio):** `aw-reels fcp-bundle --narrate-syez` i przeimportuj XML.\n"
        )
    readme.write_text(
        f"""# Final Cut Pro — Rada Polyphony (9 agentów + Syez)

## Import timeline
1. Otwórz **Final Cut Pro** → **Plik → Importuj → XML…**
2. Wybierz: `{xml_path.name}`
3. FCP utworzy projekt **{spec.title} {spec.total_s:g}s** z klipami na osi czasu.

## Struktura osi ({spec.total_s:g}s)
| Segment | Klip | Start | Długość |
|---------|------|-------|---------|
| Opening | `00-opening-seed.mp4` | 0s | {spec.opening_s}s |
| Agenci 01–09 | `01-…` – `09-Kidi.mp4` | {spec.opening_s}s | {agent_each:.2f}s × 9 |
| **Syez** | `{syez_clip.name}` | {syez_start:.2f}s | {spec.syez_s}s |
| Closing CTA | `{closing.name}` | {closing_start:.2f}s | {spec.closing_s}s |

## Po imporcie (ręcznie w FCP)
- **Przejścia:** Cross Dissolve ~8–12 klatek między portretami i przed/po Syezie.
- **Opening (0–{spec.opening_s}s):** tekst serif złoty #E8D5A3 — „Za każdym ważnym wyborem…"
- **Syez ({syez_start:.1f}–{closing_start:.1f}s):** portret + napisy; Syez **nie** wchodzi do mandali 9 twarzy.
{audio_note}- **Closing ({closing_start:.1f}–{spec.total_s}s):** mandala 9 twarzy + CTA.
- **Brakujące PNG:** zamień placeholder w `Clips/` własnym klipem lub dodaj PNG do `Portraits/` i przebuduj bundle.

## Agenci (kolejność montażu)
| # | Agent | Rola | Opis | Długość | Media |
|---|-------|------|------|---------|-------|
{agents}
| 10 | Syez | {syez_entry.role} | {syez_entry.tagline} | {spec.syez_s:.2f}s | {'✓' if syez_entry.image_path else 'placeholder — dodaj Syez.png'} |

## Eksport IG
- 1080×1920, 30 fps, H.264, ~{spec.total_s:g} s
- **Plik → Udostępnij → Master File** lub Compressor

## xAI (opcjonalnie)
Grok służy tylko do materiałów B-roll / seed — **finalny montaż = FCP**.
""",
        encoding="utf-8",
    )

    if sync_icloud:
        icloud_root = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"
        if icloud_root.is_dir():
            icloud_dest = icloud_root / "Architekt Wolności" / "IG Reels" / "FCP" / bundle.name
            icloud_dest.parent.mkdir(parents=True, exist_ok=True)
            if icloud_dest.exists():
                import shutil
                shutil.rmtree(icloud_dest)
            import shutil
            shutil.copytree(bundle, icloud_dest)
            (bundle / "ICLOUD.txt").write_text(str(icloud_dest), encoding="utf-8")

    return bundle
