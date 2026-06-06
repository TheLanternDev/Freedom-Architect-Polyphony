"""Statyczny lint promptów grok-imagine-video — reguły if/else, zero LLM."""

from __future__ import annotations

from dataclasses import dataclass

from .voiceover_parse import extract_onscreen_text, extract_voiceover

MAX_PROMPT_CHARS = 4000

# Frazy sygnalizujące zakaz tekstu na ekranie.
_NO_TEXT_PHRASES = (
    "no text on screen",
    "no readable text",
    "no text overlays",
    "no on-screen text",
    "żadnych napisów",
    "bez napisów",
)


@dataclass(frozen=True)
class LintFinding:
    level: str  # error | warning | info
    message: str


def lint_prompt(prompt: str, *, has_identity: bool | None = None) -> list[LintFinding]:
    """Zwróć listę uwag. `has_identity` z koncepta (None = nie dotyczy custom promptu)."""
    findings: list[LintFinding] = []
    text = prompt or ""
    lower = text.lower()

    onscreen = extract_onscreen_text(text)
    says_no_text = any(p in lower for p in _NO_TEXT_PHRASES)

    # Sprzeczność: "No text on screen" + sekcja ON-SCREEN TEXT z treścią.
    if says_no_text and onscreen:
        findings.append(LintFinding(
            "error",
            "Sprzeczność: prompt deklaruje brak tekstu na ekranie, a sekcja ON-SCREEN TEXT "
            f"zawiera linie ({len(onscreen)}). Model dostaje sprzeczne instrukcje.",
        ))

    # Długość promptu.
    if len(text) > MAX_PROMPT_CHARS:
        findings.append(LintFinding(
            "warning",
            f"Prompt ma {len(text)} znaków (> {MAX_PROMPT_CHARS}). "
            "Ryzyko obcięcia / utraty kluczowych dyrektyw.",
        ))

    # Brak tożsamości w koncepcie.
    if has_identity is False:
        findings.append(LintFinding(
            "info",
            "Koncept nie deklaruje pola `identity` — reel nie zakotwicza żadnego motywu marki.",
        ))

    # Info: wykryto narrację / tekst on-screen (przydatne dla publish).
    if extract_voiceover(text):
        findings.append(LintFinding("info", "Wykryto sekcję voiceover — publish może auto-parsować narrację."))
    if onscreen:
        findings.append(LintFinding(
            "info", f"Wykryto tekst on-screen ({len(onscreen)} linii) — publish może wypalić napisy."
        ))

    return findings


def format_findings(findings: list[LintFinding]) -> str:
    if not findings:
        return "Brak uwag — prompt czysty."
    icons = {"error": "✗", "warning": "⚠", "info": "ℹ"}
    return "\n".join(f"{icons.get(f.level, '·')} [{f.level}] {f.message}" for f in findings)
