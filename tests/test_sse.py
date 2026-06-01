"""Testy shared SSE helper (api/services/_sse.py)."""

from api.services._sse import sse


def test_sse_format_basic():
    """Event SSE ma poprawny format: event: X\\ndata: {json}\\n\\n"""
    result = sse("test_event", {"key": "value"})
    assert result.startswith("event: test_event\n")
    assert "data: " in result
    assert result.endswith("\n\n")


def test_sse_json_payload():
    """Data jest poprawnym JSON-em."""
    import json
    result = sse("abc", {"num": 42, "nested": {"a": 1}})
    data_line = result.split("\n")[1]
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload == {"num": 42, "nested": {"a": 1}}


def test_sse_unicode():
    """Polskie znaki nie są escapowane (ensure_ascii=False)."""
    result = sse("pl", {"msg": "żółw"})
    assert "żółw" in result
    assert "\\u" not in result


def test_sse_debate_pending_and_agent_error_payload_shape():
    """Kształt payloadów zgodny z docs/spec/sse_events.schema.json (task 6)."""
    pending = sse(
        "debate_pending",
        {
            "status": "initializing",
            "council_mode": "personal",
            "msg": "Sprawdzam bezpieczeństwo i destyluję marzenie...",
        },
    )
    assert pending.startswith("event: debate_pending\n")

    err = sse(
        "agent_error",
        {
            "agent": "Szow",
            "error": "[timeout: agent Szow przekroczył 55s]",
            "kind": "timeout",
        },
    )
    import json

    data_line = err.split("\n")[1]
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload["kind"] == "timeout"
