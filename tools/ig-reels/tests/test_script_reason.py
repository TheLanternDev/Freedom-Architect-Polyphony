from aw_reels.script_reason import (
    analyze_voiceover,
    apply_analysis_to_script,
    estimate_duration_seconds,
    normalize_for_tts,
    parse_voiceover_window,
    trim_script_to_window,
)
from aw_reels.voiceover_parse import extract_voiceover

PROMPT = """
═══ TIMELINE ═══
8.0–12.0s Slow camera orbit. Syez speaks (Polish).
12.0–15.0s Text on screen.

═══ SYEZ VOICEOVER ═══
"Ze Ciemności z Pustki budzi się Rada."
"Wszyscy moi Agenci schodzą się w Jedno Miejsce."
"""


def test_parse_voiceover_window_from_timeline():
    w = parse_voiceover_window(PROMPT, 15.0)
    assert w.start_s == 8.0
    assert w.end_s == 12.0
    assert w.duration_s == 4.0


def test_analyze_fits_short_script():
    vo = "Ze Ciemności budzi się Rada."
    a = analyze_voiceover(vo, reel_duration_s=15.0, prompt=PROMPT)
    assert a.fits_in_window
    assert a.window.duration_s == 4.0


def test_analyze_flags_long_script():
    long = " ".join(["słowo"] * 80)
    a = analyze_voiceover(long, reel_duration_s=15.0, prompt=PROMPT)
    assert not a.fits_in_window
    assert a.suggestions


def test_trim_and_apply():
    long = " ".join(["To jest zdanie numer jeden."] * 10)
    a = analyze_voiceover(long, reel_duration_s=15.0, prompt=PROMPT)
    trimmed = apply_analysis_to_script(a)
    assert len(trimmed) < len(long)
    assert estimate_duration_seconds(trimmed) <= a.window.duration_s * 1.1


def test_normalize_adds_pauses():
    n = normalize_for_tts("Pierwsze. Drugie.")
    assert "..." in n or "." in n
