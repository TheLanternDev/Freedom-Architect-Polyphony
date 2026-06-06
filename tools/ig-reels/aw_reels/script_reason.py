"""Rozumowanie o skrypcie narracji — heurystyki + opcjonalny probe ElevenLabs (with-timestamps).

Zero text-LLM: TTS z timestampami daje rzeczywistą długość mowy; reszta to reguły
(długość vs okno w promptcie, WPM, normalizacja pod eleven_multilingual_v2).
"""

from __future__ import annotations

import base64
import re
from dataclasses import asdict, dataclass, field

# Spokojny narrator PL (Syez) — ~2 słowa/s ≈ 120 sł/min; bufor na pauzy.
DEFAULT_WPM = 110
# Domyślne okno mowy w reelu, gdy prompt nie ma TIMELINE (sekundy od startu klipu).
DEFAULT_SPEECH_START = 2.0
DEFAULT_SPEECH_END_RATIO = 0.85  # końcówka na napisy / sygnaturę


@dataclass
class VoiceoverWindow:
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


@dataclass
class ScriptFinding:
    level: str  # error | warning | info
    message: str


@dataclass
class ScriptAnalysis:
    script: str
    reel_duration_s: float
    window: VoiceoverWindow
    char_count: int
    word_count: int
    estimated_duration_s: float
    measured_duration_s: float | None = None
    fits_in_window: bool = True
    findings: list[ScriptFinding] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    normalized_script: str = ""
    line_timings: list[tuple[str, float, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["window"] = asdict(self.window)
        return d


_TIMELINE_RANGE = re.compile(
    r"(\d+(?:\.\d+)?)\s*[–—-]\s*(\d+(?:\.\d+)?)\s*s",
    re.IGNORECASE,
)
_SPEECH_HINT = re.compile(
    r"(syez\s+speak|narrat|voiceover|mówi|speaks?\s*\(|narracja)",
    re.IGNORECASE,
)


def parse_voiceover_window(prompt: str, reel_duration_s: float) -> VoiceoverWindow:
    """Wyciągnij okno czasowe na mowę z sekcji TIMELINE (np. 8–12s Syez speaks)."""
    if not prompt:
        end = reel_duration_s * DEFAULT_SPEECH_END_RATIO
        return VoiceoverWindow(start_s=DEFAULT_SPEECH_START, end_s=end)

    lines = prompt.splitlines()
    best: VoiceoverWindow | None = None

    for line in lines:
        if not _SPEECH_HINT.search(line):
            continue
        for m in _TIMELINE_RANGE.finditer(line):
            start, end = float(m.group(1)), float(m.group(2))
            if end > start:
                cand = VoiceoverWindow(start_s=start, end_s=end)
                if best is None or cand.duration_s < best.duration_s:
                    # Preferuj węższe okno z explicite „speaks” (bardziej precyzyjne).
                    best = cand

    if best:
        return best

    # Fallback: najdłuższy zakres w całym TIMELINE po nagłówku.
    in_timeline = False
    ranges: list[VoiceoverWindow] = []
    for line in lines:
        if "TIMELINE" in line.upper():
            in_timeline = True
            continue
        if in_timeline and line.strip().startswith("═"):
            break
        if in_timeline:
            for m in _TIMELINE_RANGE.finditer(line):
                start, end = float(m.group(1)), float(m.group(2))
                if end > start:
                    ranges.append(VoiceoverWindow(start_s=start, end_s=end))
    if ranges:
        # Okno obejmujące „mowę” — często 8–12s w hero promptach.
        speech_like = [r for r in ranges if r.duration_s <= reel_duration_s * 0.6]
        if speech_like:
            return max(speech_like, key=lambda w: w.duration_s)
        return ranges[-1]

    end = reel_duration_s * DEFAULT_SPEECH_END_RATIO
    return VoiceoverWindow(start_s=DEFAULT_SPEECH_START, end_s=end)


def count_words_pl(text: str) -> int:
    return len(re.findall(r"[\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", text, re.UNICODE))


def estimate_duration_seconds(text: str, *, wpm: int = DEFAULT_WPM) -> float:
    words = count_words_pl(text)
    if words == 0:
        return 0.0
    return (words / wpm) * 60.0


def normalize_for_tts(text: str) -> str:
    """Przygotuj tekst pod ElevenLabs (bez LLM): łamanie zdań, pauzy, typografia."""
    s = text.strip()
    s = s.replace("…", "...")
    s = re.sub(r"\s+", " ", s)
    # Po kropce — krótka pauza w TTS (ElevenLabs respektuje ... i przecinki).
    s = re.sub(r"\.\s+", ". ", s)
    # Wielokrotne spacje po usunięciu łamań linii — już wyżej.
    # Długie zdania (> 12 słów) — podziel po przecinku lub średniku.
    sentences = re.split(r"(?<=[.!?])\s+", s)
    out: list[str] = []
    for sent in sentences:
        words = count_words_pl(sent)
        if words <= 12:
            out.append(sent)
            continue
        parts = re.split(r"(?<=[,;])\s+", sent)
        if len(parts) > 1:
            out.extend(p.strip() for p in parts if p.strip())
        else:
            out.append(sent)
    merged = " ".join(out)
    # Pauza między zdaniami dla spokojnego tempa.
    merged = merged.replace(". ", ". ... ")
    return merged.strip()


def alignment_to_line_timings(
    script: str,
    alignment: dict,
) -> list[tuple[str, float, float]]:
    """Zgrupuj alignment znak-po-znaku w linie (po \\n lub po zdaniach)."""
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not chars or len(chars) != len(starts):
        return []

    lines_raw = script.splitlines() if "\n" in script else [script]
    if len(lines_raw) == 1:
        # Podział po zdaniach.
        lines_raw = [p.strip() for p in re.split(r"(?<=[.!?])\s+", script) if p.strip()]

    timings: list[tuple[str, float, float]] = []
    idx = 0
    for line in lines_raw:
        line = line.strip()
        if not line:
            continue
        consumed = 0
        line_start: float | None = None
        line_end: float = 0.0
        target_len = len(line.replace(" ", ""))
        while idx < len(chars) and consumed < target_len:
            ch = chars[idx]
            if ch.strip():
                consumed += 1
            if line_start is None and ch.strip():
                line_start = starts[idx]
            line_end = ends[idx]
            idx += 1
        # Spacje w oryginale — przeskocz znaki białe w alignment.
        while idx < len(chars) and not chars[idx].strip():
            idx += 1
        if line_start is not None:
            timings.append((line, line_start, line_end))
    return timings


def analyze_voiceover(
    script: str,
    *,
    reel_duration_s: float,
    prompt: str | None = None,
    measured_duration_s: float | None = None,
    wpm: int = DEFAULT_WPM,
) -> ScriptAnalysis:
    """Oceń skrypt względem długości reela i okna mowy z promptu."""
    script = script.strip()
    window = parse_voiceover_window(prompt or "", reel_duration_s)
    est = estimate_duration_seconds(script, wpm=wpm)
    measured = measured_duration_s
    effective = measured if measured is not None else est
    slot = window.duration_s
    fits = effective <= slot * 1.05 if slot > 0 else True

    findings: list[ScriptFinding] = []
    suggestions: list[str] = []

    findings.append(ScriptFinding(
        "info",
        f"Okno mowy (z promptu): {window.start_s:.1f}s–{window.end_s:.1f}s "
        f"({slot:.1f}s dostępne).",
    ))

    if measured is not None:
        findings.append(ScriptFinding(
            "info",
            f"ElevenLabs probe: {measured:.2f}s mowy (model + głos z sesji/env).",
        ))
    else:
        findings.append(ScriptFinding(
            "info",
            f"Szacunek heuristiczny: {est:.2f}s przy ~{wpm} słów/min.",
        ))

    if not fits:
        over = effective - slot
        findings.append(ScriptFinding(
            "error",
            f"Skrypt za długi o ~{over:.1f}s względem okna mowy. "
            "Model wideo nie zsynchronizuje pełnego voiceoveru w jednym ujęciu.",
        ))
        suggestions.append(
            f"Skróć o ~{max(1, int(count_words_pl(script) * over / max(effective, 0.1)))} słów "
            "lub poszerz okno w TIMELINE (np. wcześniejszy start Syeza)."
        )
        suggestions.append(
            "Uruchom: aw-reels script-plan SESSION --apply — zapisze skróconą wersję (heurystyka)."
        )
    elif effective > slot * 0.92:
        findings.append(ScriptFinding(
            "warning",
            "Skrypt wypełnia okno mowy (>92%) — brak marginesu na pauzy i oddech.",
        ))
        suggestions.append("Dodaj krótkie pauzy (...) między zdaniami lub skróć o 1–2 słowa.")
    else:
        findings.append(ScriptFinding(
            "info",
            f"Margines w oknie: ~{slot - effective:.1f}s — dobry zapas pod mux z wideo.",
        ))

    if count_words_pl(script) > 55:
        findings.append(ScriptFinding(
            "warning",
            f"Długi skrypt ({count_words_pl(script)} słów) — ryzyko pośpiechu lub obcięcia.",
        ))

    normalized = normalize_for_tts(script)
    if normalized != script:
        suggestions.append("Użyj znormalizowanego tekstu (--apply) — lepsze pauzy dla ElevenLabs.")

    return ScriptAnalysis(
        script=script,
        reel_duration_s=reel_duration_s,
        window=window,
        char_count=len(script),
        word_count=count_words_pl(script),
        estimated_duration_s=est,
        measured_duration_s=measured,
        fits_in_window=fits,
        findings=findings,
        suggestions=suggestions,
        normalized_script=normalized,
    )


def trim_script_to_window(script: str, *, target_seconds: float, wpm: int = DEFAULT_WPM) -> str:
    """Skróć skrypt do docelowej długości mowy (zdania od końca)."""
    words_target = max(1, int((target_seconds / 60.0) * wpm * 0.95))
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", script.strip()) if p.strip()]
    kept: list[str] = []
    total = 0
    for p in parts:
        w = count_words_pl(p)
        if total + w > words_target and kept:
            break
        kept.append(p)
        total += w
    if not kept:
        # Pojedyncze długie zdanie — tnij słowa.
        words = re.findall(r"[\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", script)
        return " ".join(words[:words_target]) + ("." if words else "")
    return " ".join(kept)


def apply_analysis_to_script(analysis: ScriptAnalysis) -> str:
    """Wybierz tekst do zapisu w sesji po analizie."""
    if analysis.fits_in_window:
        return analysis.normalized_script or analysis.script
    target = analysis.window.duration_s * 0.92
    trimmed = trim_script_to_window(analysis.script, target_seconds=target)
    return normalize_for_tts(trimmed)
