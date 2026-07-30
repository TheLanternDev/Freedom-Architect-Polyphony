"""Regresja: ThinkingBlock nie może wywracać parsowania odpowiedzi LLM."""

from __future__ import annotations

from types import SimpleNamespace

from shared.utils.llm import extract_message_text


def test_extract_skips_thinking_block():
    thinking = SimpleNamespace(type="thinking", thinking="…")
    # ThinkingBlock w SDK nie ma `.text` — symulujemy AttributeError przy dostępie.
    class _Thinking:
        type = "thinking"

        @property
        def text(self):  # pragma: no cover - nie powinno być wołane
            raise AttributeError("'ThinkingBlock' object has no attribute 'text'")

    msg = SimpleNamespace(
        content=[
            _Thinking(),
            SimpleNamespace(type="text", text="  Głos Rady.  "),
        ]
    )
    assert extract_message_text(msg) == "Głos Rady."
    # upewnij się, że sam thinking bez text nie jest czytany przez getattr-path
    assert getattr(thinking, "type") == "thinking"


def test_extract_joins_multiple_text_blocks():
    msg = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="A"),
            SimpleNamespace(type="tool_use", name="x"),
            SimpleNamespace(type="text", text="B"),
        ]
    )
    assert extract_message_text(msg) == "AB"


def test_extract_legacy_single_block_without_type():
    msg = SimpleNamespace(content=[SimpleNamespace(text="legacy")])
    assert extract_message_text(msg) == "legacy"


def test_extract_empty_when_only_thinking():
    class _Thinking:
        type = "thinking"

    msg = SimpleNamespace(content=[_Thinking()])
    assert extract_message_text(msg) == ""
