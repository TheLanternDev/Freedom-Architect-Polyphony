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
