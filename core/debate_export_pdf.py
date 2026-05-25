"""
Eksport debaty do PDF (UTF-8, font DejaVu z pakietu core/fonts).

Używane przez GET /debate/{id}/export.pdf — ten sam kanon treści co Markdown
(`render_debate_markdown`), renderowany jako proza wielostronicowa.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fpdf import FPDF

from core.debate_export import render_debate_markdown

_FONT = Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf"


def render_debate_pdf_bytes(
    debate: dict[str, Any],
    voices: list[dict[str, Any]],
    commitments: list[dict[str, Any]],
    synthesis_text: str,
    structured: Optional[dict[str, Any]],
) -> bytes:
    md = render_debate_markdown(
        debate, voices, commitments, synthesis_text, structured
    )
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    left = 14.0
    pdf.set_left_margin(left)
    pdf.set_right_margin(14.0)
    pdf.add_page()
    if _FONT.is_file():
        pdf.add_font("DejaVu", "", str(_FONT))
        pdf.set_font("DejaVu", size=11)
    else:
        pdf.set_font("Helvetica", size=11)

    for raw_line in md.split("\n"):
        line = raw_line.rstrip()
        pdf.set_x(left)
        if not line.strip():
            pdf.ln(4)
            continue
        if line.startswith("# "):
            pdf.set_font_size(18)
            pdf.multi_cell(0, 10, line[2:].strip())
            pdf.ln(3)
            pdf.set_font_size(11)
            continue
        if line.startswith("## "):
            pdf.set_font_size(14)
            pdf.multi_cell(0, 8, line[3:].strip())
            pdf.ln(2)
            pdf.set_font_size(11)
            continue
        if line.startswith("### "):
            pdf.set_font_size(12)
            pdf.multi_cell(0, 7, line[4:].strip())
            pdf.ln(1)
            pdf.set_font_size(11)
            continue
        chunk = line
        if len(chunk) > 4000:
            chunk = chunk[:4000] + "\n…"
        pdf.multi_cell(0, 6, chunk)

    out = pdf.output()
    return bytes(out) if isinstance(out, bytearray) else out
