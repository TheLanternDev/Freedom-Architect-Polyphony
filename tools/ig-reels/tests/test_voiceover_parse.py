from __future__ import annotations

from aw_reels.voiceover_parse import extract_onscreen_text, extract_voiceover

PROMPT = """Vertical cinematic Reel. 9:16.

═══ SYEZ VOICEOVER — Polish, slow ═══
"Z Ciemności... z Pustki... budzi się Rada.
Tu, gdzie jest Światło."

═══ ON-SCREEN TEXT — golden serif, seconds 12–15 ═══
Line 1: "Architekt Wolności"
Line 2: "Twoja Rada Nadzorcza"

═══ CAMERA & AUDIO ═══
Slow orbit.
"""


def test_extract_voiceover_basic():
    vo = extract_voiceover(PROMPT)
    assert vo is not None
    assert "budzi się Rada" in vo
    assert "Tu, gdzie jest Światło" in vo
    # cudzysłowy usunięte
    assert not vo.startswith('"')


def test_extract_voiceover_preserves_polish():
    vo = extract_voiceover(PROMPT)
    assert "Ciemności" in vo
    assert "Światło" in vo


def test_extract_voiceover_none_when_absent():
    assert extract_voiceover("Just a scene with no narration markers.") is None
    assert extract_voiceover("") is None


def test_extract_onscreen_text():
    lines = extract_onscreen_text(PROMPT)
    assert lines == ["Architekt Wolności", "Twoja Rada Nadzorcza"]


def test_extract_onscreen_empty_when_absent():
    assert extract_onscreen_text("scene only") == []


def test_voiceover_lowercase_marker():
    p = "intro\nvoiceover: Cześć świecie\n\nnext"
    assert extract_voiceover(p) == "Cześć świecie"
