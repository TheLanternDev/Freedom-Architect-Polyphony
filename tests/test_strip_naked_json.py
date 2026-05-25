"""
Testy jednostkowe dla _strip_naked_json i _sanitize_syez_output (edge cases).
"""
import json
import re
import sys
import os

# Minimalna ścieżka — importujemy samą metodę statyczną bez pełnego drzewa zależności.
# BaseAgent._sanitize_syez_output jest @staticmethod, więc wystarczy patch importów.

# Stub wymaganych modułów, żeby import base_agent nie padł
for mod in [
    "config", "config.agent_models", "config.llm_providers",
    "core", "core.completion_enforcer",
    "business_fa2", "business_fa2.config", "business_fa2.config.roles",
    "anthropic", "tenacity", "redis", "redis.asyncio",
]:
    if mod not in sys.modules:
        sys.modules[mod] = type(sys)("stub")

# Stub atrybutów wymaganych przez import
sys.modules["config.agent_models"].HYBRID_MODELS_ENABLED = False
sys.modules["config.agent_models"].ModelCfg = dict
sys.modules["config.agent_models"].get_model_config = lambda *a, **kw: {}
sys.modules["config.llm_providers"].anthropic_api_key = lambda: None
sys.modules["config.llm_providers"].anthropic_omits_temperature = lambda m: False
sys.modules["config.llm_providers"].effective_llm_backend = lambda: "none"
sys.modules["config.llm_providers"].map_claude_model_to_xai = lambda m: m
sys.modules["config.llm_providers"].xai_chat_completion = None
sys.modules["core.completion_enforcer"].AGENT_COMPLETION_POSTSCRIPT = ""
sys.modules["business_fa2.config.roles"].FA2_BUSINESS_ROLES = {}

sys.path.insert(0, os.path.dirname(__file__))
from base_agent import BaseAgent


def test_pure_text_preserved():
    """Czysty tekst bez nawiasów klamrowych nie jest modyfikowany."""
    text = "To jest zwykła proza. Rady Nadzorczej.\nKilka linii tekstu."
    result = BaseAgent._sanitize_syez_output(text)
    assert "zwykła proza" in result
    assert "Kilka linii tekstu" in result


def test_naked_json_removed():
    """Nagi JSON dict zostaje usunięty, proza zachowana."""
    prose = "Synteza Rady:\n"
    blob = '{"insights_per_agent": {"Kogit": "ok"}, "completion_audit": true}'
    text = prose + blob + "\nKoniec."
    result = BaseAgent._sanitize_syez_output(text)
    assert "insights_per_agent" not in result
    assert "Synteza Rady" in result
    assert "Koniec" in result


def test_mermaid_preserved_with_json():
    """Blok mermaid jest zachowany, ale JSON obok niego usunięty."""
    mermaid = "```mermaid\nflowchart TD\n  A-->B\n```"
    blob = '{"key": "value"}'
    text = f"Wstęp.\n\n{mermaid}\n\n{blob}\n\nZakończenie."
    result = BaseAgent._sanitize_syez_output(text)
    assert "flowchart TD" in result
    assert "A-->B" in result
    assert '"key"' not in result
    assert "Zakończenie" in result


def test_broken_json_not_removed():
    """Uszkodzony JSON (brak zamknięcia) nie jest usuwany — to może być proza."""
    text = "Napięcia: {Kogit vs Emojy — brak porozumienia w kwestii priorytetów"
    result = BaseAgent._sanitize_syez_output(text)
    assert "Kogit vs Emojy" in result


def test_braces_in_natural_context():
    """Nawiasy klamrowe w naturalnej prozie (np. cytaty, wzory) nie znikają,
    o ile nie tworzą valid JSON dict."""
    text = "Wzór: f(x) = {x^2 + 1} dla x > 0. Koniec."
    result = BaseAgent._sanitize_syez_output(text)
    # {x^2 + 1} nie jest valid JSON → powinno zostać
    assert "{x^2 + 1}" in result


if __name__ == "__main__":
    test_pure_text_preserved()
    test_naked_json_removed()
    test_mermaid_preserved_with_json()
    test_broken_json_not_removed()
    test_braces_in_natural_context()
    print("✓ Wszystkie 5 testów przeszło.")
