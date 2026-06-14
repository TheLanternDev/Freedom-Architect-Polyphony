"""BYOK: ContextVar klucza LLM, anthropic_api_key, cache klientów per-klucz."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

from db.tenant import (
    current_llm_key,
    reset_current_llm_key,
    set_current_llm_key,
)


class TestAnthropicApiKey:
    def test_returns_contextvar_key_when_set(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        token = set_current_llm_key("sk-user-byok-test")
        try:
            from config.llm_providers import anthropic_api_key

            assert anthropic_api_key() == "sk-user-byok-test"
        finally:
            reset_current_llm_key(token)

    def test_prod_without_key_returns_none(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-server-env")
        token = set_current_llm_key(None)
        try:
            with patch("api.settings.is_production", return_value=True):
                from config.llm_providers import anthropic_api_key

                assert anthropic_api_key() is None
        finally:
            reset_current_llm_key(token)

    def test_dev_without_context_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-dev-env")
        token = set_current_llm_key(None)
        try:
            with patch("api.settings.is_production", return_value=False):
                from config.llm_providers import anthropic_api_key

                assert anthropic_api_key() == "sk-dev-env"
        finally:
            reset_current_llm_key(token)


class TestGetClient:
    def test_none_when_no_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        token = set_current_llm_key(None)
        try:
            with patch("api.settings.is_production", return_value=True):
                from agents.base_agent import BaseAgent

                BaseAgent._client_cache.clear()
                BaseAgent._client_cache_order.clear()
                assert BaseAgent._get_client() is None
        finally:
            reset_current_llm_key(token)

    def test_same_instance_for_same_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-cache-a")
        from agents.base_agent import BaseAgent

        BaseAgent._client_cache.clear()
        BaseAgent._client_cache_order.clear()
        mock_cls = MagicMock()
        with patch("agents.base_agent.AsyncAnthropic", mock_cls):
            c1 = BaseAgent._get_client()
            c2 = BaseAgent._get_client()
            assert c1 is c2
            assert mock_cls.call_count == 1

    def test_different_instances_for_different_keys(self, monkeypatch):
        from agents.base_agent import BaseAgent

        BaseAgent._client_cache.clear()
        BaseAgent._client_cache_order.clear()
        instances: list[MagicMock] = []

        def _factory(**_kw):
            m = MagicMock(name=f"client-{len(instances)}")
            instances.append(m)
            return m

        with patch("agents.base_agent.AsyncAnthropic", side_effect=_factory):
            token_a = set_current_llm_key("sk-key-aaa")
            try:
                ca = BaseAgent._get_client()
            finally:
                reset_current_llm_key(token_a)

            token_b = set_current_llm_key("sk-key-bbb")
            try:
                cb = BaseAgent._get_client()
            finally:
                reset_current_llm_key(token_b)

            assert ca is not cb
            assert len(instances) == 2
            id_a = hashlib.sha256(b"sk-key-aaa").hexdigest()[:16]
            id_b = hashlib.sha256(b"sk-key-bbb").hexdigest()[:16]
            assert id_a in BaseAgent._client_cache
            assert id_b in BaseAgent._client_cache


class TestLlmKeyContextIsolation:
    def test_reset_clears_contextvar_between_requests(self):
        token = set_current_llm_key("sk-first")
        assert current_llm_key() == "sk-first"
        reset_current_llm_key(token)
        assert current_llm_key() is None

        token2 = set_current_llm_key("sk-second")
        assert current_llm_key() == "sk-second"
        reset_current_llm_key(token2)
        assert current_llm_key() is None

    def test_sequential_requests_do_not_share_key_after_reset(self):
        token1 = set_current_llm_key("sk-req-one")
        try:
            from config.llm_providers import anthropic_api_key

            assert anthropic_api_key() == "sk-req-one"
        finally:
            reset_current_llm_key(token1)

        assert current_llm_key() is None

        token2 = set_current_llm_key("sk-req-two")
        try:
            from config.llm_providers import anthropic_api_key

            assert anthropic_api_key() == "sk-req-two"
        finally:
            reset_current_llm_key(token2)

        assert current_llm_key() is None


class TestBudgetGuardByok:
    def test_byok_skips_hard_cap(self):
        import asyncio

        token = set_current_llm_key("sk-user-pays")
        try:
            block = MagicMock()
            with patch(
                "api.services.budget_guard.evaluate_hard_budget", return_value=block
            ), patch(
                "api.services.budget_guard.load_budget_snapshot",
                return_value=MagicMock(),
            ):
                from api.services.budget_guard import ensure_hard_budget_or_raise

                asyncio.run(ensure_hard_budget_or_raise())  # nie rzuca mimo block
        finally:
            reset_current_llm_key(token)
