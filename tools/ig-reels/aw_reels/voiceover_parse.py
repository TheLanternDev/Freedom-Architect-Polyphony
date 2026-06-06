"""Wyciąganie narracji i tekstu on-screen z promptu — bez żadnego LLM.

Działa na strukturze promptów w stylu `prompt.txt` (sekcje oddzielone nagłówkami
`═══ … ═══` lub prostymi markerami). Czyste reguły tekstowe: zero wywołań API.
"""

from __future__ import annotations

import re

# Markery rozpoczynające blok narracji (case-insensitive).
_VOICEOVER_MARKERS = (
    "SYEZ VOICEOVER",
    "VOICEOVER —",
    "VOICEOVER-",
    "VOICEOVER:",
    "VOICEOVER",
    "NARRACJA:",
    "NARRACJA",
)

# Markery rozpoczynające blok tekstu na ekranie.
_ONSCREEN_MARKERS = (
    "ON-SCREEN TEXT",
    "ON SCREEN TEXT",
    "TEKST NA EKRANIE",
    "NAPISY:",
)

# Linia będąca nagłówkiem kolejnej sekcji (kończy bieżący blok).
_SECTION_HEADER = re.compile(r"^\s*═+")
# Linie, które nie są treścią narracji (instrukcje formatujące w nagłówku).
_NOISE_PREFIX = re.compile(r"^\s*(line\s*\d+\s*:|linia\s*\d+\s*:)", re.IGNORECASE)


def _strip_quotes(line: str) -> str:
    """Usuń otaczające cudzysłowy (proste i typograficzne), zachowaj polskie znaki."""
    s = line.strip()
    pairs = (('"', '"'), ("„", "”"), ("“", "”"), ("'", "'"), ("»", "«"), ("«", "»"))
    for left, right in pairs:
        if len(s) >= 2 and s.startswith(left) and s.endswith(right):
            return s[1:-1].strip()
    # Pojedynczy cudzysłów na początku/końcu (np. tylko otwierający)
    return s.strip('"„”“'"'»«").strip()


def _line_has_marker(line: str, markers: tuple[str, ...]) -> bool:
    upper = line.upper()
    return any(m in upper for m in markers)


def _find_marker_line(lines: list[str], markers: tuple[str, ...]) -> int | None:
    """Znajdź linię markera. Preferuj nagłówek sekcji (═══) — inline wzmianki
    (np. w bloku FORBIDDEN: 'omitting on-screen text') NIE są sekcją treści.
    """
    header_hit: int | None = None
    plain_hit: int | None = None
    for idx, line in enumerate(lines):
        if not _line_has_marker(line, markers):
            continue
        if _SECTION_HEADER.match(line):
            if header_hit is None:
                header_hit = idx
        elif plain_hit is None:
            plain_hit = idx
    # Jeśli istnieje jakikolwiek nagłówek sekcji z markerem — użyj go.
    return header_hit if header_hit is not None else plain_hit


def _inline_after_marker(line: str) -> str:
    """Treść w tej samej linii co marker, np. 'voiceover: Cześć' → 'Cześć'.
    Pomija nagłówki sekcji (═══ … ═══), gdzie po dwukropku bywa opis formatu."""
    if _SECTION_HEADER.match(line):
        return ""
    if ":" not in line:
        return ""
    after = line.split(":", 1)[1]
    return _strip_quotes(after)


def _collect_block(lines: list[str], start: int) -> list[str]:
    """Zbierz linie treści po linii markera aż do następnego nagłówka sekcji."""
    block: list[str] = []
    inline = _inline_after_marker(lines[start])
    if inline:
        block.append(inline)
    for line in lines[start + 1 :]:
        if _SECTION_HEADER.match(line):
            break
        if not line.strip():
            # Pusta linia po treści kończy blok; przed treścią — pomiń.
            if block:
                break
            continue
        if _NOISE_PREFIX.match(line):
            # "Line 1: ..." → zachowaj tylko część po dwukropku.
            after = line.split(":", 1)[1] if ":" in line else line
            cleaned = _strip_quotes(after)
            if cleaned:
                block.append(cleaned)
            continue
        block.append(_strip_quotes(line))
    return [b for b in block if b]


def extract_voiceover(prompt: str) -> str | None:
    """Zwróć tekst narracji z promptu lub None, jeśli brak sekcji voiceover.

    Łączy wszystkie linie bloku w jeden tekst (spacje między liniami).
    """
    if not prompt:
        return None
    lines = prompt.splitlines()
    idx = _find_marker_line(lines, _VOICEOVER_MARKERS)
    if idx is None:
        return None
    block = _collect_block(lines, idx)
    if not block:
        return None
    text = " ".join(block).strip()
    return text or None


def extract_onscreen_text(prompt: str) -> list[str]:
    """Zwróć listę linii tekstu on-screen z promptu (pusta lista, jeśli brak)."""
    if not prompt:
        return []
    lines = prompt.splitlines()
    idx = _find_marker_line(lines, _ONSCREEN_MARKERS)
    if idx is None:
        return []
    return _collect_block(lines, idx)
