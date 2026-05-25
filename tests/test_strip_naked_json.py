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
_STUBBED_MODS = [
    "config", "config.agent_models", "config.llm_providers",
    "core", "core.completion_enforcer",
    "business_fa2", "business_fa2.config", "business_fa2.config.roles",
    "anthropic", "tenacity", "redis", "redis.asyncio",
]
# Zapamiętujemy, które moduły faktycznie podmieniliśmy — żeby je posprzątać
# w teardown_module (inaczej stuby w sys.modules zatruwają kolejne testy,
# np. test_anthropic_temperature_compat — patrz [[fa-test-isolation]]).
_INSERTED_BY_US = [m for m in _STUBBED_MODS if m not in sys.modules]
for mod in _STUBBED_MODS:
    if mod not in sys.modules:
        sys.modules[mod] = type(sys)("stub")

# Atrybuty stubów — ustawiamy WYŁĄCZNIE na modułach, które sami wstrzyknęliśmy
# (_INSERTED_BY_US). Mutowanie realnego modułu (gdy był już zaimportowany przez
# wcześniejszy test) zatruwałoby go trwale — np. nadpisanie realnego
# config.llm_providers.anthropic_omits_temperature lambdą psuło
# test_anthropic_temperature_compat w pełnym zestawie.
def _stub_attr(mod_name, attr, value):
    if mod_name in _INSERTED_BY_US:
        setattr(sys.modules[mod_name], attr, value)

_stub_attr("config.agent_models", "HYBRID_MODELS_ENABLED", False)
_stub_attr("config.agent_models", "ModelCfg", dict)
_stub_attr("config.agent_models", "get_model_config", lambda *a, **kw: {})
_stub_attr("config.llm_providers", "anthropic_api_key", lambda: None)
_stub_attr("config.llm_providers", "anthropic_omits_temperature", lambda m: False)
_stub_attr("config.llm_providers", "effective_llm_backend", lambda: "none")
_stub_attr("config.llm_providers", "map_claude_model_to_xai", lambda m: m)
_stub_attr("config.llm_providers", "xai_chat_completion", None)
_stub_attr("core.completion_enforcer", "AGENT_COMPLETION_POSTSCRIPT", "")
_stub_attr("core.completion_enforcer", "SYEZ_AKSJOMAT2_PROSE_APPEND", "")
_stub_attr("business_fa2.config.roles", "FA2_BUSINESS_ROLES", {})

# Importujemy base_agent jako samodzielny moduł (z katalogu agents/), NIE przez
# pakiet agents — żeby agents/__init__.py nie wciągał realnych zależności,
# które celowo stubujemy powyżej.
_agents_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents")
sys.path.insert(0, _agents_dir)
from base_agent import BaseAgent  # noqa: E402

# KLUCZOWE: sprzątamy stuby NATYCHMIAST po imporcie. _sanitize_syez_output jest
# @staticmethod i nie sięga w runtime do stubowanych modułów, więc nie są już
# potrzebne. Pozostawienie ich w sys.modules zatruwałoby collection kolejnych
# plików testowych (np. test_anthropic_temperature_compat importuje realny
# config.llm_providers). Usuwamy tylko to, co sami wstrzyknęliśmy.
for _mod in _INSERTED_BY_US:
    sys.modules.pop(_mod, None)
if _agents_dir in sys.path:
    sys.path.remove(_agents_dir)


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
