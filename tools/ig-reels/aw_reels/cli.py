from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .client import VideoClient, download_video, resolve_video_source
from .config import (
    OUTPUT_DIR,
    ROOT,
    get_api_key,
    get_default_concept,
    get_production_next_concept,
    get_elevenlabs_voice_id,
    load_brand_style,
    load_concepts,
)
from . import prompt_cache
from .elevenlabs_client import list_voices, synthesize_speech, synthesize_with_timestamps
from .audio_mux import mux_narration, normalize_audio
from .validate import validate_mp4
from .voiceover_parse import extract_onscreen_text, extract_voiceover
from .script_reason import (
    analyze_voiceover,
    apply_analysis_to_script,
    alignment_to_line_timings,
    normalize_for_tts,
)
from .post_finish import finish_reel, DEFAULT_VOICEOVER
from .post_extend import extend_reel_hybrid
from .council_assets import load_reference_paths, DEFAULT_MANIFEST
from .council_narration import (
    DEFAULT_TIMELINE as DEFAULT_COUNCIL_TIMELINE,
    build_council_narration,
    timeline_to_voiceover_script,
)
from .fcp_export import build_fcp_bundle
from .subtitles import burn_subtitles
from .prompt_lint import LintFinding, format_findings, lint_prompt
from .memory import (
    context_brief,
    duplicate_warning,
    find_by_iteration,
    load_entries,
    record_iteration,
)
from .strict_prompt import wrap_strict
from .prompts import (
    compile_concept_prompt,
    compile_custom_prompt,
    compile_raw_prompt,
    edit_prompt_suggestions,
    mutation_variants,
)
from .session import (
    IterationKind,
    ReelSession,
    create_session,
    has_successful_iterations,
    iteration_is_ready,
    load_session,
    list_sessions,
)

console = Console()


def _progress(msg: str) -> None:
    console.print(f"[dim]{msg}[/dim]")


def _read_prompt_text(prompt: str | None, file: str | None) -> str:
    if file:
        if file == "-":
            return sys.stdin.read().strip()
        p = Path(file)
        if not p.is_file():
            raise click.ClickException(
                f"Brak pliku: {file}\n"
                f"Użyj pełnej ścieżki, np. prompt.txt w katalogu ig-reels"
            )
        return p.read_text(encoding="utf-8").strip()
    if prompt:
        text = prompt.strip()
        if text in ("…", "...", "Twoja scena…", "Twoja scena..."):
            raise click.ClickException("To placeholder z README — wpisz własny prompt lub użyj -f prompt.txt")
        return text
    console.print("[dim]Edytor: vim → Esc :wq Enter  |  nano → Ctrl+O Enter Ctrl+X[/dim]")
    edited = click.edit()
    if not edited or not edited.strip():
        raise click.ClickException("Pusty prompt. Użyj: aw-reels new-prompt -f prompt.txt")
    return edited.strip()


    return edited.strip()


def _read_voiceover_text(text: str | None, file: str | None) -> str:
    if file:
        if file == "-":
            return sys.stdin.read().strip()
        p = Path(file)
        if not p.is_file():
            raise click.ClickException(f"Brak pliku voiceover: {file}")
        return p.read_text(encoding="utf-8").strip()
    if text:
        return text.strip()
    raise click.ClickException("Podaj tekst narracji (-t) lub plik (-f).")


def _iteration_video_file(session: ReelSession, it) -> Path:
    if it.local_path and Path(it.local_path).is_file():
        return Path(it.local_path)
    dest = OUTPUT_DIR / session.id / f"{it.id}.mp4"
    if dest.is_file():
        return dest
    raise click.ClickException(
        f"Brak lokalnego MP4 dla {it.id}. Uruchom: aw-reels fetch {session.id} {it.id}"
    )


def _load_session_id(session_id: str) -> ReelSession:
    if session_id.upper() == "SESSION":
        raise click.ClickException(
            "SESSION to placeholder z README. Użyj prawdziwego ID, np.:\n"
            "  aw-reels list"
        )
    try:
        return load_session(session_id)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e


def _record_ok(session: ReelSession, it, *, resolution: str) -> None:
    if it.status in ("done", "picked") and it.video_url:
        record_iteration(session, it, resolution=resolution)


def _auto_save(session: ReelSession, it) -> Path | None:
    """Pobierz MP4 od razu — URL xAI nie działa w przeglądarce (obcięty/niepubliczny)."""
    if not it.video_url:
        return None
    dest = OUTPUT_DIR / session.id / f"{it.id}.mp4"
    if dest.exists() and dest.stat().st_size > 10_000:
        it.local_path = str(dest)
        return dest
    try:
        download_video(it.video_url, dest, api_key=get_api_key(), on_progress=_progress)
        it.local_path = str(dest)
        return dest
    except Exception as e:
        console.print(f"[yellow]Nie pobrano {it.id}:[/yellow] {e}")
        return None


def _ensure_local(session: ReelSession, it, *, cached: bool = False) -> Path | None:
    """Upewnij się, że MP4 jest w folderze bieżącej sesji (cache może wskazywać inny path)."""
    dest = OUTPUT_DIR / session.id / f"{it.id}.mp4"
    if dest.exists() and dest.stat().st_size > 10_000:
        it.local_path = str(dest)
        return dest
    if cached and it.local_path:
        src = Path(it.local_path)
        if src.is_file() and src.resolve() != dest.resolve():
            import shutil
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            it.local_path = str(dest)
            return dest
    return _auto_save(session, it)


def _resolve_generate_prompt(session: ReelSession, override: str | None) -> str:
    return override.strip() if override else session.base_prompt


def _apply_cache_result(it, result: dict) -> None:
    if result.get("cached") and result.get("local_path"):
        it.local_path = result["local_path"]


def _update_cache_after_save(session: ReelSession, it, result: dict) -> None:
    cache_key = result.get("cache_key")
    if cache_key and it.video_url:
        prompt_cache.update_meta(
            cache_key,
            session_id=session.id,
            iteration_id=it.id,
            local_path=it.local_path,
        )


def _record_credit(session: ReelSession, result: dict) -> None:
    if not result.get("cached"):
        session.record_credit(1)


def _warn_parallel_cost(count: int, yes: bool) -> None:
    if count >= 3 and not yes:
        console.print(
            f"[yellow][cost] {count} parallel calls = {count} credits. "
            f"Add --yes to skip this warning.[/yellow]"
        )


def _confirm_preview(path: str, no_confirm: bool) -> bool:
    if no_confirm:
        return True
    console.print(f"[dim]Preview: {path}[/dim]")
    return click.confirm("Confirm full 720p generation?", default=False)


@click.group()
@click.version_option(package_name="aw-ig-reels")
def main() -> None:
    """Generator gotowych IG Reels — Architekt Wolności × grok-imagine-video."""


@main.command("concepts")
def concepts_cmd() -> None:
    concepts = load_concepts()
    default_id = get_default_concept()
    prod_id = get_production_next_concept()
    table = Table(title="Koncepcje Architekt Wolności")
    table.add_column("ID", style="cyan")
    table.add_column("Tytuł")
    table.add_column("Hook")
    table.add_column("s", justify="right")
    table.add_column("Flagi")
    for cid, c in concepts.items():
        flags: list[str] = []
        if cid == default_id or c.get("default"):
            flags.append("default")
        if cid == prod_id or c.get("production_next"):
            flags.append("prod")
        if c.get("locked"):
            flags.append("locked")
        table.add_row(
            cid,
            c.get("title", ""),
            c.get("hook", ""),
            str(c.get("duration", 15)),
            ", ".join(flags),
        )
    console.print(table)


@main.command("new-prompt")
@click.option("-p", "--prompt", default=None, help="Własny prompt (tekst)")
@click.option("-f", "--file", default=None, help="Plik z promptem; '-' = stdin")
@click.option("--title", default="Custom Reel")
@click.option("--hook", default="")
@click.option("--context", "context_notes", default="", help="Kontekst serii (pamięć lokalna)")
@click.option("--tags", default="", help="Tagi po przecinku")
@click.option("--voiceover-file", "voiceover_file", default=None, help="Plik z tekstem narracji PL (ElevenLabs)")
@click.option("--duration", type=int, default=15)
@click.option("--resolution", default=None)
@click.option("--raw", is_flag=True, help="Bez brand suffix (prompt 1:1)")
@click.option("--from-session", "from_session", default=None, help="Skopiuj prompt/kontekst z sesji")
@click.option("--from-iter", "from_iter", default=None, help="Z iteracji (wymaga --from-session)")
@click.option("--strict", is_flag=True, help="Owija prompt blokiem NON-NEGOTIABLE (anty-upraszczanie)")
def new_prompt_cmd(
    prompt: str | None,
    file: str | None,
    title: str,
    hook: str,
    context_notes: str,
    tags: str,
    voiceover_file: str | None,
    duration: int,
    resolution: str | None,
    raw: bool,
    from_session: str | None,
    from_iter: str | None,
    strict: bool,
) -> None:
    """Nowa sesja z własnym promptem (edytor / plik / -p)."""
    style = load_brand_style()
    user_raw = _read_prompt_text(prompt, file)

    if from_session:
        src = _load_session_id(from_session)
        if from_iter:
            user_raw = src.get_iteration(from_iter).prompt
        elif src.picked_id:
            user_raw = src.get_iteration(src.picked_id).prompt
        else:
            user_raw = src.base_prompt
        if not context_notes:
            context_notes = src.context_notes
        if not tags and src.tags:
            tags = ",".join(src.tags)
        if title == "Custom Reel":
            title = src.title

    dur = min(max(duration, 1), 15)
    res = resolution or style.ig_defaults.resolution
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    voiceover_script = ""
    if voiceover_file:
        voiceover_script = Path(voiceover_file).read_text(encoding="utf-8").strip()

    if strict and not from_session:
        compiled = compile_raw_prompt(
            wrap_strict(user_raw, duration=dur).text, style=style, with_brand=False
        )
    else:
        compiled = compile_raw_prompt(user_raw, style=style, with_brand=not raw)
    dup = duplicate_warning(compiled.text)
    if dup:
        console.print(f"[yellow]{dup}[/yellow]")

    session = create_session(
        title=title,
        hook=hook,
        base_prompt=compiled.text,
        concept_id=None,
        aspect_ratio=style.ig_defaults.aspect_ratio,
        resolution=res,
        duration=dur,
        user_prompt_raw=user_raw,
        context_notes=context_notes,
        tags=tag_list,
    )
    if voiceover_script:
        session.voiceover_script = voiceover_script
        session.save()
    _print_session_created(session)


@main.command("new")
@click.argument("concept_id", required=False, default=None)
@click.option("--duration", type=int, default=None)
@click.option("--resolution", default=None)
@click.option("--context", "context_notes", default="")
@click.option("--tags", default="")
def new_cmd(
    concept_id: str | None,
    duration: int | None,
    resolution: str | None,
    context_notes: str,
    tags: str,
) -> None:
    if not concept_id:
        concept_id = get_default_concept()
        console.print(f"[dim]Domyślny koncept (locked canon): {concept_id}[/dim]")
    style = load_brand_style()
    compiled = compile_concept_prompt(concept_id, style)
    concepts = load_concepts()
    concept_dur = int(float(concepts[concept_id].get("duration", style.ig_defaults.duration)))
    dur = min(max(duration or min(concept_dur, 15), 1), 15)
    res = resolution or style.ig_defaults.resolution
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if concept_dur > 15 and concepts[concept_id].get("assembly") == "fcp":
        console.print(
            f"[yellow]Koncept {concept_dur}s — generacja xAI max 15s; "
            f"pełny montaż: aw-reels fcp-bundle[/yellow]"
        )

    session = create_session(
        title=compiled.title,
        hook=compiled.hook,
        base_prompt=compiled.text,
        concept_id=concept_id,
        aspect_ratio=style.ig_defaults.aspect_ratio,
        resolution=res,
        duration=dur,
        context_notes=context_notes,
        tags=tag_list,
    )
    tier = str(concepts[concept_id].get("tier", "")).strip().lower()
    if tier == "hero":
        console.print(
            "[yellow]Koncept tier=hero — rozważ --strict przy własnych promptach "
            "(blok NON-NEGOTIABLE chroni złożoność sceny).[/yellow]"
        )
    _print_session_created(session)


@main.command("new-custom")
@click.option("--scene", required=True)
@click.option("--title", default="Custom Reel")
@click.option("--hook", default="")
@click.option("--audio", default="ambient cinematic score")
@click.option("--duration", type=int, default=15)
@click.option("--resolution", default=None)
@click.option("--context", "context_notes", default="")
def new_custom_cmd(
    scene: str, title: str, hook: str, audio: str, duration: int,
    resolution: str | None, context_notes: str,
) -> None:
    style = load_brand_style()
    compiled = compile_custom_prompt(scene, audio=audio, style=style)
    dur = min(max(duration, 1), 15)
    res = resolution or style.ig_defaults.resolution

    session = create_session(
        title=title,
        hook=hook,
        base_prompt=compiled.text,
        concept_id=None,
        aspect_ratio=style.ig_defaults.aspect_ratio,
        resolution=res,
        duration=dur,
        user_prompt_raw=scene,
        context_notes=context_notes,
    )
    _print_session_created(session)


@main.command("prompt-set")
@click.argument("session_id")
@click.option("-p", "--prompt", default=None)
@click.option("-f", "--file", default=None)
@click.option("--raw", is_flag=True, help="Bez brand suffix")
def prompt_set_cmd(session_id: str, prompt: str | None, file: str | None, raw: bool) -> None:
    """Zmień prompt sesji przed kolejną generacją."""
    session = _load_session_id(session_id)
    style = load_brand_style()
    user_raw = _read_prompt_text(prompt, file)
    compiled = compile_raw_prompt(user_raw, style=style, with_brand=not raw)
    session.user_prompt_raw = user_raw
    session.base_prompt = compiled.text
    session.save()
    console.print(f"[green]Prompt zaktualizowany[/green] w {session_id}")


@main.command("context-set")
@click.argument("session_id")
@click.argument("text")
def context_set_cmd(session_id: str, text: str) -> None:
    """Ustaw kontekst serii (pamięć lokalna, zero API)."""
    session = _load_session_id(session_id)
    session.context_notes = text
    session.save()
    console.print(f"[green]Kontekst zapisany[/green]")


    session.save()
    console.print(f"[green]Kontekst zapisany[/green]")


@main.command("voiceover-set")
@click.argument("session_id")
@click.option("-t", "--text", default=None, help="Tekst narracji (voiceover)")
@click.option("-f", "--file", default=None, help="Plik z narracją; '-' = stdin")
@click.option("--voice-id", default=None, help="ID głosu ElevenLabs (domyślny z env)")
def voiceover_set_cmd(
    session_id: str,
    text: str | None,
    file: str | None,
    voice_id: str | None,
) -> None:
    """Zapisz skrypt narracji do sesji (ElevenLabs TTS, bez kosztu xAI)."""
    session = _load_session_id(session_id)
    session.voiceover_script = _read_voiceover_text(text, file)
    if voice_id:
        session.elevenlabs_voice_id = voice_id.strip()
    session.save()
    console.print(
        f"[green]Voiceover zapisany[/green] ({len(session.voiceover_script)} znaków)\n"
        f"  aw-reels narrate {session_id}"
    )


@main.command("narrate-council")
@click.argument("session_id")
@click.option(
    "--timeline",
    "timeline_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="YAML z segmentami mowy (domyślnie brand/reel3_brief_narration.yaml)",
)
@click.option(
    "--voices",
    "voices_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="YAML mapowania agent → głos ElevenLabs",
)
@click.option("-o", "--output", default=None, help="MP3 wyjściowy (domyślnie output/SESSION/narration-council.mp3)")
def narrate_council_cmd(
    session_id: str,
    timeline_path: str | None,
    voices_path: str | None,
    output: str | None,
) -> None:
    """Wielogłosowa narracja Rady (ElevenLabs per agent + timeline)."""
    session = _load_session_id(session_id)
    dest = Path(output) if output else OUTPUT_DIR / session_id / "narration-council.mp3"
    tl = Path(timeline_path) if timeline_path else DEFAULT_COUNCIL_TIMELINE
    vp = Path(voices_path) if voices_path else None
    _progress("ElevenLabs — składanie narracji wielogłosowej…")
    try:
        build_council_narration(dest, timeline_path=tl, voices_path=vp)
    except (RuntimeError, KeyError, ValueError) as e:
        raise click.ClickException(str(e)) from e
    session.narration_path = str(dest)
    session.voiceover_script = timeline_to_voiceover_script(tl)
    session.pipeline_stage = "voiced"
    session.save()
    console.print(
        f"[green]Narracja Rady[/green] → {dest}\n"
        f"  aw-reels publish {session_id} <ITER> --mix-ambient --force-narrate"
    )


@main.command("narrate")
@click.argument("session_id")
@click.option("-t", "--text", default=None, help="Override tekstu (zamiast voiceover_script sesji)")
@click.option("-f", "--file", default=None, help="Plik z narracją")
@click.option("--voice-id", default=None, help="ID głosu ElevenLabs")
@click.option("-o", "--output", default=None, help="Ścieżka MP3 (domyślnie output/SESSION/narration.mp3)")
def narrate_cmd(
    session_id: str,
    text: str | None,
    file: str | None,
    voice_id: str | None,
    output: str | None,
) -> None:
    """Wygeneruj narrację MP3 przez ElevenLabs (osobny koszt — nie xAI)."""
    session = _load_session_id(session_id)
    if text or file:
        script = _read_voiceover_text(text, file)
    elif session.voiceover_script:
        script = session.voiceover_script
    else:
        raise click.ClickException(
            f"Brak voiceover w sesji. Użyj: aw-reels voiceover-set {session_id} -f script.txt"
        )

    vid = voice_id or session.elevenlabs_voice_id or get_elevenlabs_voice_id()
    script = normalize_for_tts(script)
    dest = Path(output) if output else OUTPUT_DIR / session_id / "narration.mp3"
    dest.parent.mkdir(parents=True, exist_ok=True)

    _progress(f"ElevenLabs TTS → {dest.name}…")
    try:
        audio = synthesize_speech(script, voice_id=vid)
        dest.write_bytes(audio)
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e

    session.narration_path = str(dest)
    session.save()
    console.print(Panel(
        f"Plik: [bold]{dest}[/bold]\n"
        f"Głos: {vid[:12]}…\n\n"
        f"aw-reels mux {session_id} <iter-id>",
        title="Narracja gotowa",
        border_style="green",
    ))


@main.command("mux")
@click.argument("session_id")
@click.argument("iteration_id")
@click.option("--narration", default=None, help="Ścieżka MP3 (domyślnie narration sesji)")
@click.option(
    "--mix-ambient",
    is_flag=True,
    help="Zmiksuj cichą ścieżkę z wideo z narracją (domyślnie: tylko narracja)",
)
@click.option("-o", "--output", default=None, help="Plik wyjściowy (domyślnie ITER-muxed.mp4)")
def mux_cmd(
    session_id: str,
    iteration_id: str,
    narration: str | None,
    mix_ambient: bool,
    output: str | None,
) -> None:
    """Nałóż narrację ElevenLabs na lokalny MP4 (ffmpeg, zero API)."""
    session = _load_session_id(session_id)
    it = session.get_iteration(iteration_id)
    if not iteration_is_ready(it):
        raise click.ClickException("Iteracja musi mieć done/picked + wideo.")

    narr_path = Path(narration) if narration else None
    if narr_path is None and session.narration_path:
        narr_path = Path(session.narration_path)
    if not narr_path or not narr_path.is_file():
        raise click.ClickException(
            f"Brak narracji. Uruchom: aw-reels narrate {session_id}"
        )

    video_path = _iteration_video_file(session, it)
    dest = Path(output) if output else OUTPUT_DIR / session_id / f"{iteration_id}-muxed.mp4"

    _progress(f"Mux → {dest.name}…")
    try:
        mux_narration(video_path, narr_path, dest, mix_ambient=mix_ambient)
    except (FileNotFoundError, RuntimeError) as e:
        raise click.ClickException(str(e)) from e

    it.muxed_path = str(dest)
    it.narration_path = str(narr_path)
    session.save()
    console.print(Panel(
        f"Plik: [bold]{dest}[/bold]\n\n"
        f"aw-reels open {session_id} {iteration_id}  # oryginał\n"
        f"open {dest}",
        title="Reel z narracją",
        border_style="green",
    ))


@main.command("voices")
@click.option("--limit", default=20, show_default=True)
def voices_cmd(limit: int) -> None:
    """Lista głosów ElevenLabs na koncie (do wyboru --voice-id)."""
    try:
        voices = list_voices()
    except Exception as e:
        raise click.ClickException(f"ElevenLabs: {e}") from e
    if not voices:
        console.print("Brak głosów lub brak uprawnienia voices_read na kluczu API.")
        return
    table = Table(title="ElevenLabs — głosy")
    table.add_column("ID", style="cyan")
    table.add_column("Nazwa")
    table.add_column("Kategoria")
    for v in voices[:limit]:
        table.add_row(
            str(v.get("voice_id", ""))[:24],
            str(v.get("name", "")),
            str(v.get("category", "")),
        )
    console.print(table)
    console.print(f"[dim]Domyślny głos: {get_elevenlabs_voice_id()[:16]}…[/dim]")


def _iteration_for_script(session: ReelSession, iteration_id: str | None):
    if iteration_id:
        return session.get_iteration(iteration_id)
    if session.picked_id:
        return session.get_iteration(session.picked_id)
    if session.iterations:
        return session.iterations[-1]

    class _PromptOnly:
        prompt = session.base_prompt

    return _PromptOnly()


def _print_script_analysis(analysis) -> None:
    icons = {"error": "✗", "warning": "⚠", "info": "ℹ"}
    lines = [f"{icons.get(f.level, '·')} [{f.level}] {f.message}" for f in analysis.findings]
    if analysis.suggestions:
        lines.append("")
        lines.append("Sugestie:")
        for s in analysis.suggestions:
            lines.append(f"  → {s}")
    if analysis.line_timings:
        lines.append("")
        lines.append("Timing linii (probe):")
        for text, start, end in analysis.line_timings[:8]:
            lines.append(f"  {start:5.2f}s–{end:5.2f}s  {text[:50]}")
    status = "[green]mieści się[/green]" if analysis.fits_in_window else "[red]za długi[/red]"
    console.print(Panel(
        "\n".join(lines),
        title=(
            f"script-plan · {analysis.word_count} słów · "
            f"{'probe' if analysis.measured_duration_s else 'szac.'} "
            f"{analysis.measured_duration_s or analysis.estimated_duration_s:.2f}s · {status}"
        ),
        border_style="green" if analysis.fits_in_window else "yellow",
    ))


@main.command("script-plan")
@click.argument("session_id")
@click.option("--iteration", "iteration_id", default=None, help="Prompt z iteracji (domyślnie picked / ostatnia)")
@click.option("--estimate", "estimate_only", is_flag=True, help="Tylko heurystyki — zero kosztu ElevenLabs")
@click.option("--probe", is_flag=True, help="Probe TTS z timestampami (1× kredyt ElevenLabs)")
@click.option("--apply", is_flag=True, help="Zapisz zoptymalizowany skrypt do voiceover_script")
@click.option("--save-probe", is_flag=True, help="Zapisz probe MP3 → output/SESSION/narration-probe.mp3")
def script_plan_cmd(
    session_id: str,
    iteration_id: str | None,
    estimate_only: bool,
    probe: bool,
    apply: bool,
    save_probe: bool,
) -> None:
    """Rozumowanie o skrypcie narracji (okno TIMELINE + długość mowy przez ElevenLabs)."""
    session = _load_session_id(session_id)
    it = _iteration_for_script(session, iteration_id)
    prompt = it.prompt
    script = _resolve_voiceover_for_session(session, it)
    if not script:
        raise click.ClickException(
            "Brak tekstu narracji. Dodaj voiceover-set lub sekcję VOICEOVER w promptcie."
        )

    measured: float | None = None
    line_timings: list = []
    do_probe = probe and not estimate_only

    if do_probe:
        vid = session.elevenlabs_voice_id or get_elevenlabs_voice_id()
        norm = normalize_for_tts(script)
        _progress("ElevenLabs probe (with-timestamps)…")
        try:
            result = synthesize_with_timestamps(norm, voice_id=vid)
        except RuntimeError as e:
            raise click.ClickException(str(e)) from e
        measured = result["duration_s"]
        line_timings = alignment_to_line_timings(norm, result.get("alignment") or {})
        if save_probe and result.get("audio_bytes"):
            probe_path = OUTPUT_DIR / session_id / "narration-probe.mp3"
            probe_path.parent.mkdir(parents=True, exist_ok=True)
            probe_path.write_bytes(result["audio_bytes"])
            console.print(f"[dim]Probe MP3: {probe_path}[/dim]")

    analysis = analyze_voiceover(
        script,
        reel_duration_s=float(session.duration),
        prompt=prompt,
        measured_duration_s=measured,
    )
    analysis.line_timings = line_timings
    session.voiceover_analysis = analysis.to_dict()
    session.save()

    _print_script_analysis(analysis)

    if apply:
        new_script = apply_analysis_to_script(analysis)
        session.voiceover_script = new_script
        session.save()
        console.print(
            f"[green]Zapisano voiceover_script[/green] ({len(new_script)} znaków)\n"
            f"  aw-reels narrate {session_id}"
        )
    elif not analysis.fits_in_window:
        console.print(f"[dim]Skróć skrypt: aw-reels script-plan {session_id} --apply[/dim]")


@main.command("finish")
@click.argument("session_id")
@click.argument("iteration_id")
@click.option("--video-only", is_flag=True, help="Bez ElevenLabs — tylko wycięcie powtórzenia + outro")
@click.option("--outro", "outro_seconds", default=5.0, show_default=True)
@click.option("-o", "--output", default=None, help="Plik wyjściowy (domyślnie ITER-ready.mp4)")
def finish_cmd(
    session_id: str,
    iteration_id: str,
    video_only: bool,
    outro_seconds: float,
    output: str | None,
) -> None:
    """Napraw reel: wycięcie powtórzenia na początku + ElevenLabs narracja + outro blur/CTA."""
    session = _load_session_id(session_id)
    it = session.get_iteration(iteration_id)
    src = _iteration_video_file(session, it)
    dest = Path(output) if output else OUTPUT_DIR / session_id / f"{iteration_id}-ready.mp4"
    vo_script = session.voiceover_script.strip() or extract_voiceover(it.prompt) or DEFAULT_VOICEOVER
    narr_path = Path(session.narration_path) if session.narration_path else None
    _progress("Post-produkcja (finish)…")
    try:
        finish_reel(
            src, dest,
            voice_id=session.elevenlabs_voice_id,
            voiceover_script=vo_script,
            narration_mp3=narr_path,
            skip_elevenlabs=video_only,
            outro_seconds=outro_seconds,
        )
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e
    it.ready_path = str(dest)
    it.muxed_path = str(dest)
    session.pipeline_stage = "published"
    session.save()
    console.print(Panel(
        f"Plik: [bold]{dest}[/bold]\n"
        f"~{13 + outro_seconds:.0f}s (body + outro)\n\n"
        f"open {dest}",
        title="Reel gotowy",
        border_style="green",
    ))


@main.command("generate")
@click.argument("session_id")
@click.option("--draft", is_flag=True)
@click.option("--no-draft-check", is_flag=True, help="Pomiń ostrzeżenie o braku draftu")
@click.option("--no-cache", is_flag=True, help="Wyłącz deduplikację promptów (domyślnie włączona)")
@click.option("-p", "--prompt", default=None, help="Jednorazowy override promptu")
@click.option(
    "--refs",
    "refs_manifest",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="manifest.yaml z portretami Rady (reference_image_urls)",
)
@click.option("--duration", "duration_override", type=int, default=None, help="Nadpisz długość (R2V max 10s)")
def generate_cmd(
    session_id: str,
    draft: bool,
    no_draft_check: bool,
    no_cache: bool,
    prompt: str | None,
    refs_manifest: str | None,
    duration_override: int | None,
) -> None:
    session = _load_session_id(session_id)
    if not draft and not no_draft_check and not has_successful_iterations(session):
        console.print(
            f"[yellow][cost] No draft yet — consider: aw-reels generate {session_id} --draft[/yellow]"
        )
    client = VideoClient()
    duration = duration_override or session.duration
    duration = min(max(duration, 1), 15)
    if draft:
        duration = min(duration, 8)
    resolution = "480p" if draft else session.resolution
    if draft:
        console.print(f"[dim]Draft: {duration}s · {resolution} (pełne {session.duration}s → finalize)[/dim]")
    text = _resolve_generate_prompt(session, prompt)

    dup = duplicate_warning(text)
    if dup:
        console.print(f"[yellow]{dup}[/yellow]")

    ref_paths = load_reference_paths(Path(refs_manifest)) if refs_manifest else None
    if ref_paths:
        if duration > 10:
            duration = 10
            console.print("[dim]R2V: długość obcięta do 10s (limit API przy --refs)[/dim]")
        console.print(f"[dim]Reference images: {len(ref_paths)}[/dim]")

    it = session.add_iteration(IterationKind.GENERATE, text)
    console.print(Panel(text[:800] + ("…" if len(text) > 800 else ""), title="Prompt"))

    try:
        result = client.generate_text_to_video(
            text, duration=duration, aspect_ratio=session.aspect_ratio,
            resolution=resolution, reference_image_paths=ref_paths,
            on_progress=_progress,
            use_cache=not no_cache,
        )
        it.status = "done"
        it.video_url = result["url"]
        it.duration = result.get("duration")
        _apply_cache_result(it, result)
        _ensure_local(session, it, cached=bool(result.get("cached")))
        session.save()
        _update_cache_after_save(session, it, result)
        _record_credit(session, result)
        _record_ok(session, it, resolution=resolution)
        _print_iteration_done(session, it)
    except RuntimeError as e:
        it.status = "failed"
        it.error = str(e)
        session.save()
        console.print(f"[red]{e}[/red]")


@main.command("variants")
@click.argument("session_id")
# 3 parallel calls = 3x cost; start with 2, use -n 3 explicitly if needed
@click.option("-n", "--count", default=2, show_default=True)
@click.option("--draft", is_flag=True)
@click.option("--yes", is_flag=True, help="Pomiń ostrzeżenie o koszcie równoległych wywołań")
@click.option("--no-cache", is_flag=True, help="Wyłącz deduplikację promptów")
@click.option("-p", "--prompt", default=None, help="Baza wariantów (domyślnie base_prompt sesji)")
def variants_cmd(
    session_id: str,
    count: int,
    draft: bool,
    yes: bool,
    no_cache: bool,
    prompt: str | None,
) -> None:
    _warn_parallel_cost(count, yes)
    session = _load_session_id(session_id)
    client = VideoClient()
    duration = min(session.duration, 8) if draft else session.duration
    resolution = "480p" if draft else session.resolution
    if draft:
        console.print(f"[dim]Draft: {duration}s · {resolution} (pełne {session.duration}s → finalize)[/dim]")
    base = _resolve_generate_prompt(session, prompt)
    prompts = mutation_variants(base, count=count)

    parent = session.iterations[-1] if session.iterations else None
    parent_id = parent.id if parent and iteration_is_ready(parent) else None
    iterations = [session.add_iteration(IterationKind.VARIANT, p, parent_id=parent_id) for p in prompts]

    results = client.generate_variants(
        prompts, duration=duration, aspect_ratio=session.aspect_ratio,
        resolution=resolution, on_progress=_progress,
        use_cache=not no_cache,
    )

    credits = 0
    for it, res in zip(iterations, results):
        if res.get("error"):
            it.status = "failed"
            it.error = res["error"]
        else:
            it.status = "done"
            it.video_url = res["url"]
            it.duration = res.get("duration")
            _apply_cache_result(it, res)
            if res.get("cached"):
                _progress("[cache hit] skipping API call")
            _ensure_local(session, it, cached=bool(res.get("cached")))
            if not res.get("cached"):
                credits += 1
            _update_cache_after_save(session, it, res)
            _record_ok(session, it, resolution=resolution)
    if credits:
        session.record_credit(credits)
    session.save()
    _print_variants_table(session, iterations)


@main.command("edit")
@click.argument("session_id")
@click.argument("iteration_id")
@click.option("--prompt", default=None)
@click.option("-f", "--file", "prompt_file", default=None, help="Plik z instrukcją edycji")
@click.option("--preset", type=int, default=None)
@click.option("--no-cache", is_flag=True, help="Wyłącz deduplikację promptów")
def edit_cmd(
    session_id: str,
    iteration_id: str,
    prompt: str | None,
    prompt_file: str | None,
    preset: int | None,
    no_cache: bool,
) -> None:
    session = _load_session_id(session_id)
    source = session.get_iteration(iteration_id)
    if not iteration_is_ready(source):
        raise click.ClickException("Iteracja musi mieć status done/picked i URL wideo.")

    if prompt_file:
        prompt = Path(prompt_file).read_text(encoding="utf-8").strip()
    presets = edit_prompt_suggestions()
    if preset is not None:
        prompt = presets[preset]
    if not prompt:
        for i, p in enumerate(presets):
            console.print(f"  [{i}] {p}")
        raise click.ClickException("Podaj --prompt lub --preset N")

    client = VideoClient()
    it = session.add_iteration(IterationKind.EDIT, prompt, parent_id=iteration_id)
    try:
        src = resolve_video_source(source.video_url, source.local_path)
        result = client.edit_video(prompt, src, on_progress=_progress, use_cache=not no_cache)
        it.status = "done"
        it.video_url = result["url"]
        it.duration = result.get("duration")
        _apply_cache_result(it, result)
        _ensure_local(session, it, cached=bool(result.get("cached")))
        session.save()
        _update_cache_after_save(session, it, result)
        _record_credit(session, result)
        _record_ok(session, it, resolution=session.resolution)
        _print_iteration_done(session, it)
    except RuntimeError as e:
        it.status = "failed"
        it.error = str(e)
        session.save()
        console.print(f"[red]{e}[/red]")


@main.command("extend")
@click.argument("session_id")
@click.argument("iteration_id")
@click.option("-f", "--file", "prompt_file", default=None)
@click.option("--prompt", default=None)
@click.option("--seconds", "duration", type=int, default=7, show_default=True)
@click.option("--no-cache", is_flag=True)
def extend_cmd(
    session_id: str,
    iteration_id: str,
    prompt_file: str | None,
    prompt: str | None,
    duration: int,
    no_cache: bool,
) -> None:
    """Przedłuż wideo o 1–10 s (xAI video.extend) — łańcuch do pełnego reela."""
    session = _load_session_id(session_id)
    source = session.get_iteration(iteration_id)
    if not iteration_is_ready(source):
        raise click.ClickException("Iteracja musi mieć done/picked i lokalne/URL wideo.")

    if prompt_file:
        prompt = Path(prompt_file).read_text(encoding="utf-8").strip()
    if not prompt:
        raise click.ClickException("Podaj --prompt lub -f plik.")

    client = VideoClient()
    it = session.add_iteration(IterationKind.EDIT, prompt, parent_id=iteration_id)
    try:
        src = resolve_video_source(source.video_url, source.local_path)
        result = client.extend_video(
            prompt, src, duration=duration, on_progress=_progress, use_cache=not no_cache,
        )
        it.status = "done"
        it.video_url = result["url"]
        it.duration = result.get("duration")
        _apply_cache_result(it, result)
        _ensure_local(session, it, cached=bool(result.get("cached")))
        session.picked_id = it.id
        it.status = "picked"
        session.save()
        _update_cache_after_save(session, it, result)
        _record_credit(session, result)
        _record_ok(session, it, resolution=session.resolution)
        _print_iteration_done(session, it)
    except RuntimeError as e:
        it.status = "failed"
        it.error = str(e)
        session.save()
        console.print(f"[red]{e}[/red]")


@main.command("branch-edits")
@click.argument("session_id")
@click.argument("iteration_id")
# 3 parallel calls = 3x cost; start with 2, use -n 3 explicitly if needed
@click.option("-n", "--count", default=2, show_default=True)
@click.option("--yes", is_flag=True, help="Pomiń ostrzeżenie o koszcie równoległych wywołań")
@click.option("--no-cache", is_flag=True, help="Wyłącz deduplikację promptów")
def branch_edits_cmd(
    session_id: str,
    iteration_id: str,
    count: int,
    yes: bool,
    no_cache: bool,
) -> None:
    _warn_parallel_cost(count, yes)
    session = _load_session_id(session_id)
    source = session.get_iteration(iteration_id)
    if not iteration_is_ready(source):
        raise click.ClickException("Iteracja musi mieć done/picked + URL.")

    presets = edit_prompt_suggestions()[:count]
    client = VideoClient()
    src = resolve_video_source(source.video_url, source.local_path)
    iterations = [session.add_iteration(IterationKind.EDIT, p, parent_id=iteration_id) for p in presets]
    results = client.edit_variants(src, presets, on_progress=_progress, use_cache=not no_cache)

    credits = 0
    for it, res in zip(iterations, results):
        if res.get("error"):
            it.status = "failed"
            it.error = res["error"]
        else:
            it.status = "done"
            it.video_url = res["url"]
            it.duration = res.get("duration")
            _apply_cache_result(it, res)
            if res.get("cached"):
                _progress("[cache hit] skipping API call")
            _ensure_local(session, it, cached=bool(res.get("cached")))
            if not res.get("cached"):
                credits += 1
            _update_cache_after_save(session, it, res)
            _record_ok(session, it, resolution=session.resolution)
    if credits:
        session.record_credit(credits)
    session.save()
    _print_variants_table(session, iterations)


@main.command("finalize")
@click.argument("session_id")
@click.argument("iteration_id")
@click.option("--preview", is_flag=True, help="Najpierw 480p/8s preview przed pełnym 720p")
@click.option("--no-confirm", is_flag=True, help="Pomiń pytanie o potwierdzenie (skrypty)")
@click.option("--no-cache", is_flag=True, help="Wyłącz deduplikację promptów")
@click.option(
    "-f", "--prompt-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Nadpisz prompt generacji (np. prompts/reel3-brief-final-prompt.txt)",
)
@click.option(
    "--refs",
    "refs_manifest",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="manifest.yaml portretów Rady (1:1 likeness, max 7 ref)",
)
def finalize_cmd(
    session_id: str,
    iteration_id: str,
    preview: bool,
    no_confirm: bool,
    no_cache: bool,
    prompt_file: str | None,
    refs_manifest: str | None,
) -> None:
    session = _load_session_id(session_id)
    source = session.get_iteration(iteration_id)
    if not iteration_is_ready(source):
        raise click.ClickException("Iteracja musi mieć done/picked + URL.")

    if prompt_file:
        prompt = Path(prompt_file).read_text(encoding="utf-8").strip()
    else:
        prompt = source.prompt
    client = VideoClient()
    ref_paths = load_reference_paths(Path(refs_manifest)) if refs_manifest else None
    gen_duration = session.duration
    if ref_paths:
        gen_duration = min(gen_duration, 10)
        console.print(f"[dim]R2V finalize: {len(ref_paths)} portretów, {gen_duration}s (limit API)[/dim]")

    if preview:
        preview_it = session.add_iteration(IterationKind.GENERATE, prompt, parent_id=iteration_id)
        try:
            preview_result = client.generate_text_to_video(
                prompt,
                duration=min(session.duration, 8),
                aspect_ratio=session.aspect_ratio,
                resolution="480p",
                on_progress=_progress,
                use_cache=not no_cache,
            )
            preview_it.status = "done"
            preview_it.video_url = preview_result["url"]
            preview_it.duration = preview_result.get("duration")
            _apply_cache_result(preview_it, preview_result)
            _ensure_local(session, preview_it, cached=bool(preview_result.get("cached")))
            session.save()
            _update_cache_after_save(session, preview_it, preview_result)
            _record_credit(session, preview_result)
            preview_path = preview_it.local_path or f"output/{session_id}/{preview_it.id}.mp4"
            if not _confirm_preview(preview_path, no_confirm):
                console.print("[dim]Anulowano pełną generację 720p.[/dim]")
                return
        except RuntimeError as e:
            preview_it.status = "failed"
            preview_it.error = str(e)
            session.save()
            console.print(f"[red]{e}[/red]")
            return

    it = session.add_iteration(IterationKind.GENERATE, prompt, parent_id=iteration_id)
    try:
        result = client.generate_text_to_video(
            prompt, duration=gen_duration, aspect_ratio=session.aspect_ratio,
            resolution="720p", on_progress=_progress,
            reference_image_paths=ref_paths,
            use_cache=not no_cache,
        )
        it.status = "done"
        it.video_url = result["url"]
        it.duration = result.get("duration")
        session.picked_id = it.id
        _apply_cache_result(it, result)
        _ensure_local(session, it, cached=bool(result.get("cached")))
        session.save()
        _update_cache_after_save(session, it, result)
        _record_credit(session, result)
        _record_ok(session, it, resolution="720p")
        _print_iteration_done(session, it)
    except RuntimeError as e:
        it.status = "failed"
        it.error = str(e)
        session.save()
        console.print(f"[red]{e}[/red]")


@main.command("pick")
@click.argument("session_id")
@click.argument("iteration_id")
def pick_cmd(session_id: str, iteration_id: str) -> None:
    session = _load_session_id(session_id)
    it = session.get_iteration(iteration_id)
    if not iteration_is_ready(it):
        raise click.ClickException("Tylko udana iteracja z URL.")
    session.picked_id = it.id
    if it.status == "done":
        it.status = "picked"
    session.save()
    console.print(f"[green]Wybrano[/green] {iteration_id} → finalize {session_id} {iteration_id}")


@main.command("import-video")
@click.argument("video_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--session", "session_id", default=None, help="Istniejąca sesja (domyślnie: nowa)")
@click.option("-f", "--file", "prompt_file", default=None, help="Plik promptu bazowego")
@click.option("--title", default="Rada — seed import")
@click.option("--duration", type=int, default=15)
@click.option("--tags", default="rada,council,import")
def import_video_cmd(
    video_path: str,
    session_id: str | None,
    prompt_file: str | None,
    title: str,
    duration: int,
    tags: str,
) -> None:
    """Zaimportuj lokalny MP4 jako gotową iterację seed (do edit/finalize)."""
    import shutil

    style = load_brand_style()
    src = Path(video_path)
    dur = min(max(duration, 1), 15)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    base_prompt = ""
    if prompt_file:
        base_prompt = Path(prompt_file).read_text(encoding="utf-8").strip()
    if session_id:
        session = _load_session_id(session_id)
    else:
        session = create_session(
            title=title,
            hook="",
            base_prompt=base_prompt or f"Imported seed from {src.name}",
            concept_id=None,
            aspect_ratio=style.ig_defaults.aspect_ratio,
            resolution=style.ig_defaults.resolution,
            duration=dur,
            user_prompt_raw=base_prompt or None,
            tags=tag_list,
        )
    it = session.add_iteration(IterationKind.GENERATE, base_prompt or "imported seed video")
    dest = OUTPUT_DIR / session.id / f"{it.id}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    it.status = "done"
    it.video_url = "imported://local"
    it.local_path = str(dest)
    it.duration = None
    session.picked_id = it.id
    it.status = "picked"
    session.save()
    console.print(
        f"[green]Zaimportowano[/green] → {dest}\n"
        f"Sesja: {session.id} · iteracja: {it.id}\n"
        f"Następnie: aw-reels edit {session.id} {it.id} -f prompts/edit-extend-council.txt"
    )


@main.command("fcp-open")
@click.argument("fcpxml", type=click.Path(exists=True, dir_okay=False), required=False)
@click.option(
    "-b", "--bundle-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False),
    help="Folder z Rada-Polyphony.fcpxml (domyślnie: najnowszy fcp-rada-polyphony-*)",
)
def fcp_open_cmd(fcpxml: str | None, bundle_dir: str | None) -> None:
    """Otwórz FCPXML w Final Cut Pro z terminala (open / osascript)."""
    import subprocess

    path: Path | None = Path(fcpxml) if fcpxml else None
    if path is None:
        if bundle_dir:
            path = Path(bundle_dir) / "Rada-Polyphony.fcpxml"
        else:
            candidates = sorted(OUTPUT_DIR.glob("fcp-rada-polyphony-*/Rada-Polyphony.fcpxml"), reverse=True)
            if not candidates:
                raise click.ClickException("Brak FCPXML. Uruchom: aw-reels fcp-bundle")
            path = candidates[0]
    if not path.is_file():
        raise click.ClickException(f"Brak pliku: {path}")

    posix = str(path.resolve())
    # macOS 2025+: aplikacja może nazywać się "Final Cut Pro Creator Studio"
    attempts: list[tuple[str, list[str]]] = [
        ("bundle com.apple.FinalCutApp", ["open", "-b", "com.apple.FinalCutApp", posix]),
        ("Final Cut Pro Creator Studio", ["open", "-a", "Final Cut Pro Creator Studio", posix]),
        ("Final Cut Pro", ["open", "-a", "Final Cut Pro", posix]),
    ]
    opened = False
    for label, cmd in attempts:
        try:
            subprocess.run(cmd, check=True)
            console.print(f"[green]Otwarto ({label}):[/green] {posix}")
            opened = True
            break
        except subprocess.CalledProcessError:
            continue

    if not opened:
        for app_name in ("Final Cut Pro Creator Studio", "Final Cut Pro"):
            script = f'tell application "{app_name}" to open POSIX file "{posix}"'
            try:
                subprocess.run(["osascript", "-e", script], check=True)
                console.print(f"[green]Otwarto (osascript {app_name}):[/green] {posix}")
                opened = True
                break
            except subprocess.CalledProcessError:
                continue

    if not opened:
        raise click.ClickException(
            f"Nie znaleziono Final Cut Pro.\n"
            f'Spróbuj ręcznie:\n'
            f'  open -b com.apple.FinalCutApp "{posix}"\n'
            f'  open -a "Final Cut Pro Creator Studio" "{posix}"\n'
            f"  ls /Applications | grep -i final"
        )


@main.command("fcp-bundle")
@click.option(
    "-o", "--output",
    "output_dir",
    default=None,
    type=click.Path(),
    help="Folder wyjściowy (domyślnie output/fcp-rada-polyphony-YYYYMMDD)",
)
@click.option("--manifest", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--seed",
    "seed_video",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="MP4 na opening (np. seed Grok)",
)
@click.option("--no-icloud", is_flag=True, help="Nie kopiuj bundle do iCloud")
@click.option(
    "--narrate-syez",
    is_flag=True,
    help="Wygeneruj narrację Syeza (ElevenLabs) → Audio/10-syez-narration.mp3",
)
@click.option("--voice-id", default=None, help="ElevenLabs voice ID (domyślnie Syez z .env)")
def fcp_bundle_cmd(
    output_dir: str | None,
    manifest: str | None,
    seed_video: str | None,
    no_icloud: bool,
    narrate_syez: bool,
    voice_id: str | None,
) -> None:
    """Pakiet Final Cut Pro: klipy Ken Burns + FCPXML (9 agentów + Syez, ~24.5s)."""
    from datetime import datetime

    if output_dir:
        dest = Path(output_dir)
    else:
        ts = datetime.now().strftime("%Y%m%d")
        dest = OUTPUT_DIR / f"fcp-rada-polyphony-{ts}"

    seed = Path(seed_video) if seed_video else None
    if seed is None:
        for name in ("seed-rada-intro-grok.mp4", "seed-grok-edit-8s.mp4"):
            candidate = ROOT / "assets" / "council" / name
            if candidate.is_file():
                seed = candidate
                break

    bundle = build_fcp_bundle(
        dest,
        manifest=Path(manifest) if manifest else None,
        seed_video=seed,
        sync_icloud=not no_icloud,
        narrate_syez=narrate_syez,
        voice_id=voice_id,
    )
    xml = bundle / "Rada-Polyphony.fcpxml"
    console.print(Panel(
        f"Bundle: [bold]{bundle}[/bold]\n"
        f"FCPXML: {xml}\n"
        f"README: {bundle / 'README-FCP.md'}\n\n"
        "Final Cut Pro → Plik → Importuj → XML…\n"
        "Dopracuj przejścia, napisy i Syez (audio) w FCP.",
        title="FCP bundle gotowy",
        border_style="green",
    ))
    icloud_note = bundle / "ICLOUD.txt"
    if icloud_note.is_file():
        console.print(f"[dim]iCloud: {icloud_note.read_text(encoding='utf-8').strip()}[/dim]")


@main.command("hybrid-extend")
@click.argument("session_id")
@click.argument("iteration_id")
@click.option("--target", "target_duration", type=float, default=20.0, show_default=True)
@click.option("--fps", default=30, show_default=True)
def hybrid_extend_cmd(
    session_id: str,
    iteration_id: str,
    target_duration: float,
    fps: int,
) -> None:
    """15s wideo → ~20s (fps + hold ostatniej klatki), bez xAI."""
    session = _load_session_id(session_id)
    it = session.get_iteration(iteration_id)
    src = _iteration_video_file(session, it)
    dest = OUTPUT_DIR / session.id / f"{iteration_id}-hybrid.mp4"
    extend_reel_hybrid(src, dest, target_duration=target_duration, target_fps=fps)
    console.print(f"[green]Hybryd[/green] → {dest}")


@main.command("fetch")
@click.argument("session_id")
@click.argument("iteration_id", required=False)
def fetch_cmd(session_id: str, iteration_id: str | None) -> None:
    """Pobierz MP4 lokalnie (URL z CLI nie otwiera się w przeglądarce)."""
    session = _load_session_id(session_id)
    targets = [session.get_iteration(iteration_id)] if iteration_id else session.iterations
    ok = 0
    for it in targets:
        if it.status not in ("done", "picked") or not it.video_url:
            continue
        if _auto_save(session, it):
            ok += 1
    session.save()
    console.print(f"[green]Pobrano {ok} plików[/green] → output/{session_id}/")


@main.command("open")
@click.argument("session_id")
@click.argument("iteration_id")
def open_cmd(session_id: str, iteration_id: str) -> None:
    """Otwórz lokalny MP4 (macOS)."""
    import subprocess

    session = _load_session_id(session_id)
    it = session.get_iteration(iteration_id)
    path = None
    for candidate in (it.ready_path, it.muxed_path):
        if candidate and Path(candidate).is_file():
            path = Path(candidate)
            break
    if path is None:
        path = Path(it.local_path) if it.local_path else OUTPUT_DIR / session_id / f"{iteration_id}.mp4"
    if not path.is_file():
        _auto_save(session, it)
        session.save()
        path = Path(it.local_path) if it.local_path else path
    if not path.is_file():
        raise click.ClickException(f"Brak pliku. Uruchom: aw-reels fetch {session_id} {iteration_id}")
    subprocess.run(["open", str(path)], check=False)
    console.print(f"Otwarto: {path}")


@main.command("download")
@click.argument("session_id")
@click.argument("iteration_id")
@click.option("--name", default="final.mp4")
def download_cmd(session_id: str, iteration_id: str, name: str) -> None:
    session = _load_session_id(session_id)
    it = session.get_iteration(iteration_id)
    if not it.video_url:
        raise click.ClickException("Brak URL wideo.")
    dest = OUTPUT_DIR / session_id / name
    download_video(it.video_url, dest, api_key=get_api_key(), on_progress=_progress)
    it.local_path = str(dest)
    session.save()
    _record_ok(session, it, resolution=session.resolution)
    console.print(f"[green]Zapisano:[/green] {dest}")


@main.command("show")
@click.argument("session_id")
def show_cmd(session_id: str) -> None:
    session = _load_session_id(session_id)
    ctx = f"\nKontekst: {session.context_notes}" if session.context_notes else ""
    tags = f"\nTagi: {', '.join(session.tags)}" if session.tags else ""
    vo = ""
    if session.voiceover_script:
        vo = f"\nVoiceover: {len(session.voiceover_script)} znaków"
        if session.narration_path:
            vo += f" · MP3: {session.narration_path}"
    console.print(Panel(
        f"[bold]{session.title}[/bold]\n{session.hook}{ctx}{tags}{vo}\n\n"
        f"Format: {session.aspect_ratio} · {session.resolution} · {session.duration}s\n"
        f"Kredyty xAI (szac.): {session.estimated_credits_used}\n"
        f"Wybrany: {session.picked_id or '—'}",
        title=session.id,
    ))
    if session.user_prompt_raw:
        console.print(Panel(session.user_prompt_raw[:600], title="Prompt użytkownika (raw)"))
    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Kind")
    table.add_column("Status")
    table.add_column("Parent")
    table.add_column("URL / error")
    for it in session.iterations:
        extra = ""
        if it.muxed_path:
            extra = " · muxed"
        table.add_row(
            it.id, it.kind.value, it.status, it.parent_id or "—",
            ((it.video_url or it.error or "—")[:60] + extra),
        )
    console.print(table)


@main.command("list")
def list_cmd() -> None:
    sessions = list_sessions()
    if not sessions:
        console.print("Brak sesji.")
        return
    table = Table(title="Sesje reels")
    table.add_column("ID", style="cyan")
    table.add_column("Tytuł")
    table.add_column("Iteracji", justify="right")
    table.add_column("Kredyty", justify="right")
    table.add_column("Wybrany")
    total_credits = 0
    for s in sessions:
        total_credits += s.estimated_credits_used
        table.add_row(
            s.id, s.title, str(len(s.iterations)),
            str(s.estimated_credits_used), s.picked_id or "—",
        )
    console.print(table)
    console.print(f"[dim]Łącznie kredytów (szac.): {total_credits}[/dim]")


@main.command("prompt")
@click.argument("concept_id")
def prompt_cmd(concept_id: str) -> None:
    style = load_brand_style()
    compiled = compile_concept_prompt(concept_id, style)
    console.print(Panel(compiled.text, title=f"{compiled.title} — prompt"))


@main.group("cache")
def cache_group() -> None:
    """Deduplikacja promptów — oszczędza kredyty xAI (TTL 7 dni)."""


@cache_group.command("list")
@click.option("--expired", is_flag=True, help="Pokaż też wygasłe wpisy")
def cache_list_cmd(expired: bool) -> None:
    entries = prompt_cache.list_entries(include_expired=expired)
    if not entries:
        console.print("Pusty cache promptów.")
        return
    table = Table(title="Prompt cache")
    table.add_column("Hash", style="cyan")
    table.add_column("Sesja/Iter")
    table.add_column("TS")
    table.add_column("Local")
    for key, entry in entries:
        loc = "✓" if entry.get("local_path") else "—"
        sid = entry.get("session_id") or "—"
        iid = entry.get("iteration_id") or "—"
        expired_tag = " [expired]" if entry.get("expired") else ""
        table.add_row(key[:12], f"{sid}/{iid}{expired_tag}", entry.get("ts", "—")[:19], loc)
    console.print(table)


@cache_group.command("clear")
@click.option("--expired-only", is_flag=True, help="Usuń tylko wygasłe wpisy (>7 dni)")
def cache_clear_cmd(expired_only: bool) -> None:
    removed = prompt_cache.clear(expired_only=expired_only)
    label = "wygasłych" if expired_only else "wszystkich"
    console.print(f"[green]Usunięto {removed} wpisów ({label})[/green]")


@main.group("memory")
def memory_group() -> None:
    """Historia generacji Imagine (lokalna, bez kosztu API)."""


@memory_group.command("list")
@click.option("--limit", default=15, show_default=True)
@click.option("--tag", default=None)
def memory_list_cmd(limit: int, tag: str | None) -> None:
    entries = load_entries(limit=limit, tag=tag)
    if not entries:
        console.print("Pusta pamięć. Generacje zapisują się automatycznie po sukcesie.")
        return
    table = Table(title="Pamięć Imagine")
    table.add_column("Sesja/Iter", style="cyan")
    table.add_column("Tytuł")
    table.add_column("Res")
    table.add_column("Hash")
    for e in entries:
        table.add_row(f"{e.session_id}/{e.iteration_id}", e.title, e.resolution, e.prompt_hash)
    console.print(table)


@memory_group.command("show")
@click.argument("session_id")
@click.argument("iteration_id")
def memory_show_cmd(session_id: str, iteration_id: str) -> None:
    e = find_by_iteration(session_id, iteration_id)
    if not e:
        raise click.ClickException("Brak wpisu w pamięci.")
    console.print(Panel(
        f"{e.title}\nHook: {e.hook}\nCtx: {e.context_notes or '—'}\n"
        f"URL: {e.video_url or '—'}\nLocal: {e.local_path or '—'}",
        title=f"{session_id}/{iteration_id}",
    ))
    console.print(Panel(e.prompt, title="Prompt"))


@memory_group.command("context")
@click.option("--limit", default=5, show_default=True)
def memory_context_cmd(limit: int) -> None:
    console.print(Panel(context_brief(limit=limit), title="Kontekst ostatnich generacji"))


@memory_group.command("note")
@click.argument("session_id")
@click.argument("iteration_id")
@click.argument("text")
def memory_note_cmd(session_id: str, iteration_id: str, text: str) -> None:
    session = _load_session_id(session_id)
    it = session.get_iteration(iteration_id)
    it.notes = text
    session.save()
    if iteration_is_ready(it):
        record_iteration(session, it, resolution=session.resolution)
    console.print("[green]Notatka zapisana[/green]")


def _resolve_voiceover_for_session(session: ReelSession, it) -> str | None:
    """Ustal tekst narracji: sesja → auto-parse promptu iteracji."""
    if session.voiceover_script.strip():
        return session.voiceover_script.strip()
    parsed = extract_voiceover(it.prompt)
    if parsed:
        return parsed
    return None


def _resolve_onscreen_for(it, line1: str | None, line2: str | None) -> list[str]:
    """Ustal linie napisów: jawne flagi → auto-parse promptu iteracji."""
    explicit = [l for l in (line1, line2) if l and l.strip()]
    if explicit:
        return explicit
    return extract_onscreen_text(it.prompt)


@main.command("publish")
@click.argument("session_id")
@click.argument("iteration_id")
@click.option("--skip-narrate", is_flag=True, help="Pomiń generację narracji ElevenLabs")
@click.option("--skip-mux", is_flag=True, help="Pomiń nakładanie narracji na wideo")
@click.option("--skip-subs", is_flag=True, help="Pomiń wypalanie napisów")
@click.option("--mix-ambient", is_flag=True, help="Zmiksuj ciche audio wideo z narracją")
@click.option("--force-narrate", is_flag=True, help="Wygeneruj narrację nawet gdy istnieje")
@click.option("--no-confirm", is_flag=True, help="Bez pytań (skrypty)")
@click.option("--draft-only", is_flag=True, help="Tylko walidacja + plan kroków, zero API/ffmpeg")
@click.option("--caption-line1", default=None, help="Linia 1 napisów (override auto-parse)")
@click.option("--caption-line2", default=None, help="Linia 2 napisów (override auto-parse)")
def publish_cmd(
    session_id: str,
    iteration_id: str,
    skip_narrate: bool,
    skip_mux: bool,
    skip_subs: bool,
    mix_ambient: bool,
    force_narrate: bool,
    no_confirm: bool,
    draft_only: bool,
    caption_line1: str | None,
    caption_line2: str | None,
) -> None:
    """Pełny pipeline → output/SESSION/ITER-ready.mp4 + caption.txt (status: published)."""
    session = _load_session_id(session_id)
    it = session.get_iteration(iteration_id)

    voiceover = _resolve_voiceover_for_session(session, it)
    onscreen = _resolve_onscreen_for(it, caption_line1, caption_line2)
    out_dir = OUTPUT_DIR / session_id
    ready_dest = out_dir / f"{iteration_id}-ready.mp4"

    # ── Plan / draft-only ────────────────────────────────────────────────────
    plan = []
    plan.append("1. Lokalny MP4 iteracji (fetch jeśli brak)")
    if not skip_narrate:
        plan.append(f"2. Narracja: {'auto-parse z promptu' if not session.voiceover_script else 'voiceover_script sesji'}"
                    f" {'— BRAK tekstu!' if not voiceover else 'OK'}")
    if not skip_mux:
        plan.append("3. Mux narracji + loudnorm audio")
    if not skip_subs:
        plan.append(f"4. Napisy: {onscreen if onscreen else '— brak linii (pominę)'}")
    plan.append(f"5. ready.mp4 + caption.txt → {ready_dest}")

    if draft_only:
        console.print(Panel("\n".join(plan), title=f"publish --draft-only · {iteration_id}", border_style="cyan"))
        if not skip_narrate and not voiceover:
            console.print("[yellow]Uwaga: brak tekstu narracji. Dodaj voiceover-set lub sekcję VOICEOVER w promptcie.[/yellow]")
        elif voiceover:
            a = analyze_voiceover(voiceover, reel_duration_s=float(session.duration), prompt=it.prompt)
            if not a.fits_in_window:
                console.print(
                    f"[yellow]Voiceover może być za długi (~{a.estimated_duration_s:.1f}s / "
                    f"okno {a.window.duration_s:.1f}s). "
                    f"aw-reels script-plan {session_id} --probe --apply[/yellow]"
                )
        return

    # ── 1. Lokalny MP4 ───────────────────────────────────────────────────────
    if it.status not in ("done", "picked") or not it.video_url:
        raise click.ClickException("Iteracja musi mieć status done/picked i URL wideo.")
    video_path = _ensure_local(session, it, cached=True)
    session.save()
    if not video_path or not video_path.is_file():
        raise click.ClickException(
            f"Brak lokalnego MP4. Uruchom: aw-reels fetch {session_id} {iteration_id}"
        )
    problems = validate_mp4(video_path, expected_aspect=session.aspect_ratio)
    for p in problems:
        console.print(f"[yellow]validate: {p}[/yellow]")

    current = video_path  # plik wędrujący przez pipeline

    # ── 2. Narracja ──────────────────────────────────────────────────────────
    narration_path = Path(session.narration_path) if session.narration_path else None
    if not skip_narrate:
        need = force_narrate or not (narration_path and narration_path.is_file())
        if need and not voiceover:
            console.print("[yellow]Brak tekstu narracji — pomijam narrację (mux użyje istniejącej lub zostanie pominięty).[/yellow]")
        elif need:
            dest_mp3 = out_dir / "narration.mp3"
            dest_mp3.parent.mkdir(parents=True, exist_ok=True)
            _progress("ElevenLabs TTS (narracja)…")
            try:
                voice_id = session.elevenlabs_voice_id or get_elevenlabs_voice_id()
                audio = synthesize_speech(voiceover, voice_id=voice_id)
                dest_mp3.write_bytes(audio)
            except RuntimeError as e:
                raise click.ClickException(str(e)) from e
            narration_path = dest_mp3
            session.narration_path = str(dest_mp3)
            it.narration_path = str(dest_mp3)
            session.pipeline_stage = "voiced"
            session.save()

    # ── 3. Mux + loudnorm ────────────────────────────────────────────────────
    if not skip_mux and narration_path and narration_path.is_file():
        try:
            norm_mp3 = normalize_audio(narration_path)
        except (FileNotFoundError, RuntimeError) as e:
            console.print(f"[yellow]loudnorm pominięty: {e}[/yellow]")
            norm_mp3 = narration_path
        muxed = out_dir / f"{iteration_id}-muxed.mp4"
        _progress("Mux narracji na wideo…")
        try:
            mux_narration(current, norm_mp3, muxed, mix_ambient=mix_ambient)
        except (FileNotFoundError, RuntimeError) as e:
            raise click.ClickException(str(e)) from e
        it.muxed_path = str(muxed)
        session.pipeline_stage = "muxed"
        session.save()
        current = muxed

    # ── 4. Napisy ────────────────────────────────────────────────────────────
    if not skip_subs and onscreen:
        subbed = out_dir / f"{iteration_id}-subbed.mp4"
        _progress("Wypalam napisy (drawtext)…")
        try:
            burn_subtitles(current, onscreen, subbed, duration=it.duration)
        except (FileNotFoundError, RuntimeError) as e:
            raise click.ClickException(str(e)) from e
        current = subbed

    # ── 5. ready.mp4 + caption.txt ───────────────────────────────────────────
    import shutil

    shutil.copy2(current, ready_dest)
    problems = validate_mp4(ready_dest, expected_aspect=session.aspect_ratio)
    for p in problems:
        console.print(f"[yellow]validate ready.mp4: {p}[/yellow]")

    caption = _build_caption(session)
    caption_path = out_dir / "caption.txt"
    caption_path.write_text(caption, encoding="utf-8")

    it.ready_path = str(ready_dest)
    session.pipeline_stage = "published"
    session.save()

    console.print(Panel(
        f"Gotowe do IG: [bold]{ready_dest}[/bold]\n"
        f"Caption: {caption_path}\n"
        f"Stage: published\n\n"
        f"open {ready_dest}",
        title="Reel opublikowany (lokalnie)",
        border_style="green",
    ))


def _build_caption(session: ReelSession) -> str:
    """Hook + hashtagi konceptu (jeśli jest) — bez LLM."""
    lines: list[str] = []
    if session.hook:
        lines.append(session.hook)
    if session.title and session.title not in ("custom", "Custom Reel"):
        lines.append(session.title)
    tags = list(session.tags)
    if session.concept_id:
        tags = tags + ["ArchitektWolności", session.concept_id]
    seen: set[str] = set()
    hashtags = []
    for t in tags:
        slug = t.strip().lstrip("#").replace(" ", "")
        if slug and slug.lower() not in seen:
            seen.add(slug.lower())
            hashtags.append(f"#{slug}")
    if hashtags:
        lines.append("")
        lines.append(" ".join(hashtags))
    return "\n".join(lines).strip() + "\n"


@main.command("doctor")
def doctor_cmd() -> None:
    """Diagnostyka środowiska — klucze (obecność, nie wartości), ffmpeg, output/."""
    import os
    import shutil as _sh

    from .config import load_env

    load_env()
    table = Table(title="aw-reels doctor")
    table.add_column("Element", style="cyan")
    table.add_column("Status")
    table.add_column("Szczegół")

    def row(name: str, ok: bool, detail: str = "") -> None:
        table.add_row(name, "[green]OK[/green]" if ok else "[red]FAIL[/red]", detail)

    row("XAI_API_KEY", bool(os.getenv("XAI_API_KEY", "").strip()), "obecny" if os.getenv("XAI_API_KEY", "").strip() else "brak")
    row("ELEVENLABS_API_KEY", bool(os.getenv("ELEVENLABS_API_KEY", "").strip()),
        "obecny" if os.getenv("ELEVENLABS_API_KEY", "").strip() else "brak (narracja niedostępna)")

    ffmpeg = _sh.which("ffmpeg")
    ffmpeg_ver = ""
    if ffmpeg:
        import subprocess
        try:
            out = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True)
            ffmpeg_ver = out.stdout.splitlines()[0] if out.stdout else ""
        except Exception:
            ffmpeg_ver = "(wersja nieznana)"
    row("ffmpeg", bool(ffmpeg), ffmpeg_ver or "brak w PATH")

    ffprobe = _sh.which("ffprobe")
    row("ffprobe", bool(ffprobe), "obecny (walidacja MP4)" if ffprobe else "opcjonalny — brak")

    writable = False
    detail = ""
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        probe = OUTPUT_DIR / ".doctor_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        writable = True
        detail = str(OUTPUT_DIR)
    except OSError as e:
        detail = str(e)
    row("output/ zapis", writable, detail)

    try:
        from importlib.metadata import version
        xai_v = version("xai-sdk")
    except Exception:
        xai_v = "(nieznana)"
    row("xai-sdk", xai_v not in ("", "(nieznana)"), xai_v)

    console.print(table)


@main.command("compare")
@click.argument("session_id")
@click.argument("iteration_ids", nargs=-1, required=True)
@click.option("--open-all", is_flag=True, help="Otwórz po kolei wszystkie pliki (macOS)")
def compare_cmd(session_id: str, iteration_ids: tuple[str, ...], open_all: bool) -> None:
    """Porównaj iteracje obok siebie (status, czas, plik, hash). Otwórz pierwszą."""
    import subprocess

    from .memory import prompt_hash

    session = _load_session_id(session_id)
    table = Table(title=f"Porównanie — {session_id}")
    table.add_column("ID", style="cyan")
    table.add_column("Status")
    table.add_column("s", justify="right")
    table.add_column("Plik lokalny")
    table.add_column("Muxed")
    table.add_column("Hash")

    paths: list[Path] = []
    for iid in iteration_ids:
        try:
            it = session.get_iteration(iid)
        except KeyError:
            table.add_row(iid, "[red]brak[/red]", "—", "—", "—", "—")
            continue
        local = it.local_path or (f"output/{session_id}/{iid}.mp4" if it.status in ("done", "picked") else "—")
        if it.local_path and Path(it.local_path).is_file():
            paths.append(Path(it.local_path))
        muxed = "✓" if it.muxed_path else ("ready" if it.ready_path else "—")
        dur = f"{it.duration:.0f}" if it.duration else "—"
        table.add_row(iid, it.status, dur, local, muxed, prompt_hash(it.prompt))
    console.print(table)

    if paths:
        targets = paths if open_all else paths[:1]
        for p in targets:
            subprocess.run(["open", str(p)], check=False)
        console.print(f"[dim]Otwarto {len(targets)} plik(ów).[/dim]")


@main.command("rate")
@click.argument("session_id")
@click.argument("iteration_id")
@click.argument("score", type=int)
@click.argument("note", default="")
def rate_cmd(session_id: str, iteration_id: str, score: int, note: str) -> None:
    """Oceń iterację: SCORE = +1 / -1 / 0 (zapis do memory.jsonl)."""
    if score not in (1, -1, 0):
        raise click.ClickException("SCORE musi być: 1, -1 lub 0.")
    from .memory import append_rating, prompt_hash

    session = _load_session_id(session_id)
    it = session.get_iteration(iteration_id)
    append_rating(session_id, iteration_id, score, note, prompt_hash_value=prompt_hash(it.prompt))
    console.print(f"[green]Ocena zapisana[/green]: {iteration_id} = {score:+d} {note}")


@main.command("suggest")
@click.argument("session_id")
def suggest_cmd(session_id: str) -> None:
    """Zaproponuj następny lens na bazie ostatnich ocen (reguły, nie ML)."""
    from .memory import load_ratings

    _load_session_id(session_id)  # walidacja istnienia
    ratings = load_ratings(limit=10)
    lens_texts = [
        "symbolic identity element (lens 0)",
        "gold rim lighting + fog (lens 1)",
        "tighter intimate framing (lens 2)",
        "wider epic crane scale (lens 3)",
        "teal accent / cooler contrast (lens 4)",
    ]

    if not ratings:
        console.print(Panel(
            "Brak ocen w pamięci. Oceniaj iteracje: aw-reels rate SESSION ITER +1\n"
            "Domyślna sugestia: zacznij od lens 1 (gold rim lighting).",
            title="suggest",
        ))
        return

    # Heurystyka: licz słowa-klucze w pozytywnych notatkach.
    positive_notes = " ".join(r.get("note", "").lower() for r in ratings if r.get("score", 0) > 0)
    score_sum = sum(int(r.get("score", 0)) for r in ratings)

    pick = 1  # domyślnie gold rim
    if "gold" in positive_notes or "złot" in positive_notes:
        pick = 1
    elif "teal" in positive_notes or "ziel" in positive_notes:
        pick = 4
    elif "wide" in positive_notes or "epic" in positive_notes or "szerok" in positive_notes:
        pick = 3
    elif "tight" in positive_notes or "intim" in positive_notes or "blisk" in positive_notes:
        pick = 2

    console.print(Panel(
        f"Ocen w pamięci: {len(ratings)} · suma score: {score_sum:+d}\n"
        f"Sugerowany kierunek: [bold]{lens_texts[pick]}[/bold]\n\n"
        f"  aw-reels variants {session_id} -n 2  # użyj wariantu wokół tego lensa",
        title="suggest",
        border_style="cyan",
    ))


@main.command("prompt-lint")
@click.argument("session_id", required=False)
@click.option("-f", "--file", default=None, help="Lintuj prompt z pliku (zamiast sesji)")
@click.option("--script", "script_only", is_flag=True, help="Tylko analiza skryptu narracji (heurystyki)")
@click.option("--elevenlabs-probe", is_flag=True, help="Probe długości mowy przez ElevenLabs (1× kredyt)")
def prompt_lint_cmd(
    session_id: str | None,
    file: str | None,
    script_only: bool,
    elevenlabs_probe: bool,
) -> None:
    """Lint promptu + opcjonalnie rozumowanie o voiceover (ElevenLabs probe)."""
    if file:
        p = Path(file)
        if not p.is_file():
            raise click.ClickException(f"Brak pliku: {file}")
        text = p.read_text(encoding="utf-8")
        if script_only or elevenlabs_probe:
            vo = extract_voiceover(text)
            if not vo:
                raise click.ClickException("Brak sekcji voiceover w pliku.")
            measured = None
            if elevenlabs_probe:
                _progress("ElevenLabs probe…")
                r = synthesize_with_timestamps(normalize_for_tts(vo))
                measured = r["duration_s"]
            a = analyze_voiceover(vo, reel_duration_s=15.0, prompt=text, measured_duration_s=measured)
            _print_script_analysis(a)
            return
        findings = lint_prompt(text)
        console.print(Panel(format_findings(findings), title=f"prompt-lint · {p.name}"))
        return
    if not session_id:
        raise click.ClickException("Podaj SESSION lub -f plik.")
    session = _load_session_id(session_id)
    it = _iteration_for_script(session, None)
    if script_only or elevenlabs_probe:
        script = _resolve_voiceover_for_session(session, it)
        if not script:
            raise click.ClickException("Brak voiceover w sesji / promptcie.")
        measured = None
        if elevenlabs_probe:
            vid = session.elevenlabs_voice_id or get_elevenlabs_voice_id()
            _progress("ElevenLabs probe…")
            r = synthesize_with_timestamps(normalize_for_tts(script), voice_id=vid)
            measured = r["duration_s"]
        a = analyze_voiceover(
            script,
            reel_duration_s=float(session.duration),
            prompt=it.prompt,
            measured_duration_s=measured,
        )
        session.voiceover_analysis = a.to_dict()
        session.save()
        _print_script_analysis(a)
        return
    has_identity = None
    if session.concept_id:
        concepts = load_concepts()
        c = concepts.get(session.concept_id, {})
        has_identity = bool(c.get("identity"))
    findings = lint_prompt(session.base_prompt, has_identity=has_identity)
    vo = extract_voiceover(session.base_prompt)
    if vo:
        a = analyze_voiceover(
            vo,
            reel_duration_s=float(session.duration),
            prompt=session.base_prompt,
        )
        if not a.fits_in_window:
            findings.append(LintFinding(
                "warning",
                f"Voiceover (~{a.estimated_duration_s:.1f}s) może przekroczyć okno mowy "
                f"({a.window.duration_s:.1f}s). Uruchom: aw-reels script-plan {session_id} --probe",
            ))
    console.print(Panel(format_findings(findings), title=f"prompt-lint · {session_id}"))


def _print_session_created(session: ReelSession) -> None:
    preview = (session.user_prompt_raw or session.base_prompt)[:120].replace("\n", " ")
    vo_hint = ""
    if session.voiceover_script:
        vo_hint = (
            f"\n  aw-reels script-plan {session.id}  # rozumowanie voiceover\n"
            f"  aw-reels narrate {session.id}"
        )
    console.print(Panel(
        f"[bold]{session.title}[/bold]\n{session.hook}\n\n"
        f"ID: [cyan]{session.id}[/cyan]\n"
        f"Prompt: {preview}…\n"
        f"Format: {session.aspect_ratio} · {session.resolution} · {session.duration}s\n\n"
        f"  aw-reels variants {session.id} --draft -n 2{vo_hint}",
        title="Sesja utworzona",
        border_style="green",
    ))


def _print_iteration_done(session: ReelSession, it) -> None:
    local = it.local_path or f"output/{session.id}/{it.id}.mp4"
    vo_lines = ""
    if session.voiceover_script and not session.narration_path:
        vo_lines = f"\naw-reels narrate {session.id}"
    elif session.narration_path:
        vo_lines = f"\naw-reels mux {session.id} {it.id}"
    console.print(Panel(
        f"Iteracja: [cyan]{it.id}[/cyan]\n"
        f"Plik: [bold]{local}[/bold]\n\n"
        f"aw-reels open {session.id} {it.id}\n"
        f"aw-reels pick {session.id} {it.id}\n"
        f"aw-reels finalize {session.id} {it.id}{vo_lines}",
        title="Gotowe — otwórz lokalny plik, nie URL w przeglądarce",
        border_style="green",
    ))


def _print_variants_table(session: ReelSession, iterations) -> None:
    table = Table(title=f"Warianty — {session.id}")
    table.add_column("ID", style="cyan")
    table.add_column("Status")
    table.add_column("Plik lokalny")
    for it in iterations:
        loc = it.local_path or (f"output/{session.id}/{it.id}.mp4" if it.status == "done" else "—")
        table.add_row(it.id, it.status, loc)
    console.print(table)
    console.print(
        f"\n[bold]Oglądaj draft (8s):[/bold] aw-reels open {session.id} <ID>\n"
        f"Pełne {session.duration}s 720p: [bold]aw-reels finalize {session.id} <ID>[/bold]"
    )


if __name__ == "__main__":
    main()
