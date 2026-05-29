from agents.base_agent import BaseAgent


def test_sanitize_keeps_mermaid_strips_json_fence():
    raw = """Wstęp prozą.

```json
{"completion_audit": {"x": 1}}
```

Więcej tekstu.

```mermaid
flowchart LR
  A --> B
```

Koniec."""
    out = BaseAgent._sanitize_syez_output(raw)
    assert "```mermaid" in out
    assert "flowchart LR" in out
    assert "completion_audit" not in out
    assert "```json" not in out


def test_sanitize_mermaid_only_returns_meaningful():
    chart = "```mermaid\nsequenceDiagram\n  X->>Y: ping\n```"
    out = BaseAgent._sanitize_syez_output(chart)
    assert "sequenceDiagram" in out


def test_sanitize_strips_naked_json_lines():
    raw = (
        "To jest sensowna proza o odpowiedniej długości dla testu progu.\n"
        '{"k": "v"}\n'
        "[1, 2, 3]\n"
        "Drugie zdanie prozą domyka myśl."
    )
    out = BaseAgent._sanitize_syez_output(raw)
    assert '{"k"' not in out and "[1, 2, 3]" not in out
    assert "proza" in out


def test_sanitize_short_prose_with_mermaid_passes():
    raw = "Krótko.\n```mermaid\nflowchart TD\n  A --> B\n```"
    out = BaseAgent._sanitize_syez_output(raw)
    assert "```mermaid" in out and "flowchart TD" in out


def test_sanitize_short_prose_without_mermaid_graceful():
    out = BaseAgent._sanitize_syez_output("Krótko.")
    assert "Synteza nie została" in out


def test_fa2_anchor_present_for_council_absent_for_syez():
    from agents.kogit import Kogit
    from agents.syez import Syez

    anchor = "członkiem Rady Nadzorczej Architekta Wolności"
    kogit_fa2 = Kogit().get_full_instruction(council_mode="fa2")
    assert anchor in kogit_fa2
    assert anchor not in Syez().get_full_instruction(council_mode="fa2")
    assert anchor not in Kogit().get_full_instruction(council_mode="personal")
