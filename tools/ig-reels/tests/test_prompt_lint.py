from __future__ import annotations

from aw_reels.prompt_lint import lint_prompt


def _levels(findings):
    return {f.level for f in findings}


def test_contradiction_no_text_vs_onscreen():
    prompt = (
        "Cinematic shot. No text on screen.\n\n"
        "═══ ON-SCREEN TEXT ═══\n"
        'Line 1: "Architekt Wolności"\n'
    )
    findings = lint_prompt(prompt)
    assert any(f.level == "error" and "Sprzeczność" in f.message for f in findings)


def test_too_long_prompt_warns():
    long = "x" * 5000
    findings = lint_prompt(long)
    assert any(f.level == "warning" for f in findings)


def test_missing_identity_info():
    findings = lint_prompt("a short clean scene", has_identity=False)
    assert any(f.level == "info" and "identity" in f.message for f in findings)


def test_voiceover_detected_info():
    prompt = "scene\n\nVOICEOVER:\nCześć\n"
    findings = lint_prompt(prompt)
    assert any("voiceover" in f.message.lower() for f in findings)


def test_clean_prompt_no_errors():
    findings = lint_prompt("A simple cinematic shot of dawn light.")
    assert "error" not in _levels(findings)
