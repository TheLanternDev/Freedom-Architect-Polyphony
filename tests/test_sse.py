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
