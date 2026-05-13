"""
P6 — kanoniczny eksport debaty do Markdown (źródło prawdy: SQLite).

Używane przez GET /debate/{id}/export.md oraz (opcjonalnie) UI zamiast
czysto klienckiego sklejania — ten sam układ co `synthesisToMarkdown` w SyezPanel.
"""

from __future__ import annotations

import json
from typing import Any, Optional


def _structured_block(structured: dict[str, Any]) -> str:
    md = ""
    rows = structured.get("insights_per_agent")
    if isinstance(rows, list) and rows:
        md += "## Perspectives overview\n\n"
        for r in rows:
            if not isinstance(r, dict):
                continue
            ag = r.get("agent", "?")
            ins = r.get("insight", "")
            md += f"- **{ag}**: {ins}\n"
        md += "\n"
    tens = structured.get("tensions")
    if isinstance(tens, list) and tens:
        md += "## Tensions\n\n"
        for t in tens:
            if not isinstance(t, dict):
                continue
            bet = t.get("between")
            if isinstance(bet, list):
                label = " ↔ ".join(str(x) for x in bet)
            else:
                label = "?"
            md += f"- **{label}**: {t.get('why', '')}\n"
        md += "\n"
    recs = structured.get("recommendations")
    if isinstance(recs, list) and recs:
        md += "## Recommendations\n\n"
        for r in recs:
            md += f"1. {r}\n"
        md += "\n"
    oq = structured.get("open_questions")
    if isinstance(oq, list) and oq:
        md += "## Open questions\n\n"
        for q in oq:
            md += f"- {q}\n"
        md += "\n"
    steps = structured.get("action_steps")
    if isinstance(steps, list) and steps:
        md += "## Action steps\n\n"
        for a in steps:
            if not isinstance(a, dict):
                continue
            due = a.get("due")
            suf = f" _(due: {due})_" if due else ""
            md += f"- [ ] {a.get('step', '')}{suf}\n"
        md += "\n"
    cm = structured.get("commitments")
    if isinstance(cm, list) and cm:
        md += "## Commitments (from the synthesis)\n\n"
        for c in cm:
            if not isinstance(c, dict):
                continue
            fu = c.get("follow_up_at")
            tail = f" → follow-up: {fu}" if fu else ""
            md += f"- {c.get('text', '')}{tail}\n"
        md += "\n"
    ca = structured.get("completion_audit")
    if isinstance(ca, dict):
        md += "## Functionality audit\n\n"
        rem = ca.get("functionality_checklist_remaining")
        if isinstance(rem, list):
            md += "- Remaining checklist items: " + "; ".join(str(x) for x in rem) + "\n"
        else:
            md += "- Remaining checklist items: —\n"
        blk = ca.get("blocked_by")
        if isinstance(blk, list):
            md += "- Blockers: " + "; ".join(str(x) for x in blk) + "\n"
        else:
            md += "- Blockers: —\n"
        md += "- Smallest increment: " + str(ca.get("smallest_next_functional_increment") or "—") + "\n\n"
    md += "---\n\n## Full structured (JSON)\n\n```json\n"
    md += json.dumps(structured, ensure_ascii=False, indent=2)
    md += "\n```\n"
    return md


def render_debate_markdown(
    debate: dict[str, Any],
    voices: list[dict[str, Any]],
    commitments: list[dict[str, Any]],
    synthesis_text: str,
    structured: Optional[dict[str, Any]],
) -> str:
    did = debate.get("id", "?")
    lines: list[str] = [
        f"# Architekt Wolności — debata #{did}",
        "",
        f"- **Data:** {debate.get('created_at', '')}",
        f"- **Kategoria:** {debate.get('category', '')}",
        f"- **Tryb:** {debate.get('mode', '')}",
        f"- **dream_id:** {debate.get('dream_id') or '—'}",
        "",
        "## Brief",
        "",
        str(debate.get("brief_description") or "").strip(),
        "",
    ]
    if debate.get("intention"):
        lines += ["### Intencja", "", str(debate["intention"]).strip(), ""]
    if debate.get("extra_context"):
        lines += ["### Dodatkowy kontekst", "", str(debate["extra_context"]).strip(), ""]

    lines += ["## Głosy Rady", ""]
    if voices:
        for v in voices:
            name = v.get("agent_name", "?")
            txt = str(v.get("voice_text") or "").strip()
            lines += [f"### {name}", "", txt, ""]
    else:
        lines += ["_(brak zapisanych głosów)_", ""]

    if commitments:
        lines += ["## Zobowiązania (SQLite)", ""]
        for c in commitments:
            cid = c.get("id", "")
            st = c.get("status", "")
            txt = str(c.get("text") or "").strip()
            lines.append(f"- [{st}] #{cid} — {txt}")
        lines.append("")

    raw = (synthesis_text or "").strip()
    lines += ["## Synteza Syeza (tekst)", "", raw if raw else "_(brak)_", ""]

    if structured and isinstance(structured, dict):
        lines += ["## Synteza — struktura", "", _structured_block(structured)]

    return "\n".join(lines).strip() + "\n"
