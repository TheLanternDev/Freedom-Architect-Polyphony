"""Kompilacja promptów anty-upraszczających dla grok-imagine-video."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrictPrompt:
    text: str
    title: str


def wrap_strict(user_scene: str, *, duration: int = 15) -> StrictPrompt:
    """Owija scenę użytkownika w blokady NON-NEGOTIABLE + FORBIDDEN."""
    core = user_scene.strip()
    text = f"""Vertical cinematic Instagram Reel. 9:16. Exactly {duration} seconds.
ONE continuous unbroken shot — zero cuts.

NON-NEGOTIABLE (render ALL, no simplification):
□ Every element described in SCENE below must appear
□ Do not reduce character count or merge figures
□ Do not skip quoted voiceover or on-screen text if specified
□ Keep central symbolic anchor visible once introduced

FORBIDDEN:
✗ Lone single character when scene specifies many
✗ Empty void without described subjects
✗ Jump cuts, montage, stock look
✗ Skipping audio/language specified in scene

SCENE:
{core}

Execute full complexity. Maximum detail. Do not compress or omit."""
    return StrictPrompt(text=text, title="strict")


def rada_z_ciemnosci_prompt() -> StrictPrompt:
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / "prompt.txt"
    return StrictPrompt(text=p.read_text(encoding="utf-8"), title="Rada z Ciemności")
