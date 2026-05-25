"""is_retryable_anthropic_exception — m.in. HTTP 529 overloaded."""

from __future__ import annotations

import httpx
import pytest

pytest.importorskip("anthropic")
from anthropic import APIStatusError  # noqa: E402

import config.llm_providers as lp


def _status_error(code: int) -> APIStatusError:
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(code, request=req)
    return APIStatusError("test", response=resp, body={})


def test_529_overloaded_is_retryable():
    assert lp.is_retryable_anthropic_exception(_status_error(529)) is True


def test_503_is_retryable():
    assert lp.is_retryable_anthropic_exception(_status_error(503)) is True


def test_400_not_retryable():
    assert lp.is_retryable_anthropic_exception(_status_error(400)) is False
