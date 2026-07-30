"""Review-fix 2026-07-16 — Etap 1 (blokery).

Pokrywa:
  • profil `AW_ENV=boxed` (api/settings.py): bramki bezpieczeństwa jak prod,
    bez preflightu infrastrukturalnego;
  • BYOK fail-closed w boxed (config/llm_providers.py);
  • advisor: gate na backend != anthropic (żadnych instrukcji advisora
    poza API Anthropic);
  • advisor: kontrolowany fallback do STANDARDOWEGO wywołania (nie
    _fallback_contribute) przy starym SDK / pause_turn bez domknięcia /
    pustym tekście — z czystym system promptem (bez sekcji ADVISOR);
  • advisor: rozliczenie kosztów z `usage.iterations`;
  • env_bootstrap boxed: sekret JWT 0600, trwałość między restartami.

Importy wewnątrz testów — plik nie wymusza ciężkich zależności przy kolekcji.
"""

from __future__ import annotations

import asyncio
import os
import stat
import sys
from types import SimpleNamespace


# ── helpers ──────────────────────────────────────────────────────────────

def _msg(text="OK", stop_reason="end_turn", iterations=None, in_tok=10, out_tok=5):
    usage = SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok)
    if iterations is not None:
        usage.iterations = iterations
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=usage,
        stop_reason=stop_reason,
    )


def _dummy_agent():
    import agents.base_agent as ba

    class Dummy(ba.BaseAgent):
        def __init__(self):
            super().__init__()
            self.name = "Szow"
            self.instruction = "Testowa instrukcja."

        def contribute(self, context: str) -> str:
            return "[fallback-placeholder]"

    return Dummy()


class _FakeClient:
    """Udaje AsyncAnthropic: .messages.create + .beta.messages.create."""

    def __init__(self, std_msg=None, beta_side_effect=None, beta_msgs=None):
        self.std_calls: list[dict] = []
        self.beta_calls: list[dict] = []
        outer = self

        async def _std_create(**kw):
            outer.std_calls.append(kw)
            return std_msg or _msg("STANDARD")

        async def _beta_create(**kw):
            outer.beta_calls.append(kw)
            if beta_side_effect is not None:
                raise beta_side_effect
            seq = beta_msgs or [_msg("ADVISED")]
            i = min(len(outer.beta_calls) - 1, len(seq) - 1)
            return seq[i]

        self.messages = SimpleNamespace(create=_std_create)
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(create=_beta_create)
        )


def _run_agent(monkeypatch, tmp_path, client, *, backend="anthropic"):
    import agents.base_agent as ba

    monkeypatch.setenv("COST_LOG_PATH", str(tmp_path / "cost.jsonl"))
    monkeypatch.setenv("DISABLE_CACHE", "1")
    monkeypatch.setattr(ba, "effective_llm_backend", lambda: backend)
    agent = _dummy_agent()
    monkeypatch.setattr(agent, "_get_client", lambda: client)

    async def _go():
        return await agent.acontribute(
            "Testowy brief.", advisor_override=True
        )

    return asyncio.run(_go()), client


# ── profil boxed ─────────────────────────────────────────────────────────

def test_boxed_flags(monkeypatch):
    from api import settings as s

    monkeypatch.delenv("NODE_ENV", raising=False)
    monkeypatch.setenv("AW_ENV", "boxed")
    assert s.is_boxed() and s.security_hardened() and not s.is_production()

    monkeypatch.setenv("AW_ENV", "production")
    assert s.is_production() and s.security_hardened() and not s.is_boxed()

    monkeypatch.setenv("AW_ENV", "development")
    assert not s.is_production() and not s.is_boxed() and not s.security_hardened()


def test_boxed_hides_docs_and_no_infra_preflight(monkeypatch):
    from api import settings as s

    monkeypatch.setenv("AW_ENV", "boxed")
    # bramka bezpieczeństwa: /docs ukryte jak w produkcji
    monkeypatch.delenv("AW_FORCE_OPENAPI", raising=False)
    assert s.openapi_urls() == (None, None, None)
    # infrastruktura: ZERO wymagań produkcyjnych (SQLite, bez Redis/CORS)
    assert s.production_preflight_errors() == []


def test_boxed_cors_without_wildcard(monkeypatch):
    from api import settings as s

    monkeypatch.setenv("AW_ENV", "boxed")
    monkeypatch.delenv("AW_CORS_ORIGINS", raising=False)
    origins = s.cors_allow_origins()
    assert "*" not in origins
    assert "tauri://localhost" in origins


def test_boxed_byok_fail_closed(monkeypatch):
    from config import llm_providers as lp

    monkeypatch.setenv("AW_ENV", "boxed")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-server-key")
    monkeypatch.setenv("LLM_BACKEND", "auto")
    monkeypatch.setenv("XAI_API_KEY", "xai-k")
    # env fallback zabroniony (klucz tylko z X-LLM-Key/Keychain)
    assert lp.anthropic_api_key() is None
    # auto bez klucza usera → none (bez cichego zjazdu na xAI)
    assert lp.effective_llm_backend() == "none"

    monkeypatch.setenv("AW_ENV", "development")
    assert lp.anthropic_api_key() == "sk-env-server-key"


# ── advisor: gate + fallbacki ────────────────────────────────────────────

def test_advisor_gated_off_for_non_anthropic_backend(monkeypatch, tmp_path):
    import agents.base_agent as ba

    captured = {}

    async def fake_xai(*, system, user, model, max_tokens, temperature):
        captured["system"] = system
        return "OK-XAI", 7, 3

    monkeypatch.setattr(ba, "xai_chat_completion", fake_xai)
    out, _ = _run_agent(monkeypatch, tmp_path, client=None, backend="xai")
    assert out == "OK-XAI"
    # instrukcja advisora NIE może trafić do backendu bez narzędzia advisor
    assert "ADVISOR" not in captured["system"]


def test_advisor_old_sdk_falls_back_to_standard_call(monkeypatch, tmp_path):
    """Stary SDK (TypeError na `betas=`) → zwykłe wywołanie, czysty prompt."""
    client = _FakeClient(beta_side_effect=TypeError(
        "create() got an unexpected keyword argument 'betas'"
    ))
    out, client = _run_agent(monkeypatch, tmp_path, client)
    assert out == "STANDARD"          # NIE _fallback_contribute
    assert len(client.beta_calls) == 1
    assert len(client.std_calls) == 1
    # fallbackowe wywołanie bez sekcji ADVISOR w system prompcie
    assert "ADVISOR" not in client.std_calls[0]["system"]


def test_advisor_pause_turn_exhaustion_falls_back(monkeypatch, tmp_path):
    """4× pause_turn bez domknięcia → tekst byłby ucięty → standardowa ścieżka."""
    client = _FakeClient(beta_msgs=[_msg("PART", stop_reason="pause_turn")])
    out, client = _run_agent(monkeypatch, tmp_path, client)
    assert out == "STANDARD"
    assert len(client.beta_calls) == 4  # pełna pętla, potem fallback
    assert len(client.std_calls) == 1


def test_advisor_empty_text_falls_back(monkeypatch, tmp_path):
    client = _FakeClient(beta_msgs=[_msg("")])
    out, client = _run_agent(monkeypatch, tmp_path, client)
    assert out == "STANDARD"


def test_advisor_happy_path_uses_suffix_and_counts_cost(monkeypatch, tmp_path):
    import agents.base_agent as ba

    iters = [
        SimpleNamespace(type="executor_message", input_tokens=100, output_tokens=40),
        SimpleNamespace(
            type="advisor_message", model=ba.ADVISOR_MODEL,
            input_tokens=200, output_tokens=80,
        ),
    ]
    client = _FakeClient(beta_msgs=[_msg("ADVISED", iterations=iters)])
    out, client = _run_agent(monkeypatch, tmp_path, client)
    assert out == "ADVISED"
    assert len(client.std_calls) == 0
    # sekcja ADVISOR obecna TYLKO w wywołaniu z narzędziem
    assert "ADVISOR" in client.beta_calls[0]["system"]
    assert client.beta_calls[0]["betas"] == ["advisor-tool-2026-03-01"]


def test_extract_advisor_response_splits_costs():
    import agents.base_agent as ba

    agent = _dummy_agent()
    iters = [
        SimpleNamespace(type="executor_message", input_tokens=100, output_tokens=40),
        SimpleNamespace(
            type="advisor_message", model=ba.ADVISOR_MODEL,
            input_tokens=1000, output_tokens=500,
        ),
    ]
    text, in_tok, out_tok, adv_cost = agent._extract_advisor_response(
        [_msg("X", iterations=iters)]
    )
    assert (text, in_tok, out_tok) == ("X", 100, 40)
    assert adv_cost > 0  # Opus liczony osobno, wg własnych stawek

    # legacy SDK bez usage.iterations → wszystko na executora, koszt advisora 0
    text, in_tok, out_tok, adv_cost = agent._extract_advisor_response(
        [_msg("Y", in_tok=11, out_tok=6)]
    )
    assert (text, in_tok, out_tok, adv_cost) == ("Y", 11, 6, 0.0)


# ── env_bootstrap: boxed ─────────────────────────────────────────────────

def _boxed_env(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("AW_APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AW_DISABLE_DOTENV", "1")
    for var in ("AW_ENV", "NODE_ENV", "ARCHITEKT_JWT_SECRET",
                "ARCHITEKT_DB_PATH", "COST_LOG_PATH", "EVENTS_LOG_PATH"):
        # PUŁAPKA pytest (znaleziona 2026-07-17): delenv na NIEOBECNEJ
        # zmiennej NIE zapisuje nic do przywrócenia. Kod boxed ustawia te
        # zmienne bezpośrednio w os.environ → wyciekały do reszty suity
        # (AW_ENV=boxed → security_hardened → masowe 401). setenv PRZED
        # delenv wymusza wpis w książce restore: teardown przywróci stan
        # sprzed testu niezależnie od tego, co zrobi kod pod testem.
        monkeypatch.setenv(var, "__AW_TEST_PLACEHOLDER__")
        monkeypatch.delenv(var)


def test_boxed_bootstrap_secret_0600_and_persistent(monkeypatch, tmp_path):
    import env_bootstrap as eb

    _boxed_env(monkeypatch, tmp_path)
    eb.load_repo_env()

    assert os.environ["AW_ENV"] == "boxed"
    secret1 = os.environ["ARCHITEKT_JWT_SECRET"]
    assert len(secret1) >= 32  # settings.jwt_secret_strength_ok()

    cfg = tmp_path / "config.env"
    assert cfg.is_file()
    if os.name == "posix":
        mode = stat.S_IMODE(cfg.stat().st_mode)
        assert mode == 0o600, f"config.env ma {oct(mode)}, wymagane 0600"

    # „restart": czyste env → ten sam sekret odczytany z pliku, bez regeneracji.
    # os.environ.pop, NIE monkeypatch.delenv: delenv w środku testu zapisałby
    # wartość ustawioną przez kod pod testem jako cel restore i wyciekła ona
    # by do reszty suity (sprzątanie robi bookkeeping z _boxed_env).
    os.environ.pop("ARCHITEKT_JWT_SECRET", None)
    os.environ.pop("AW_ENV", None)
    eb.load_repo_env()
    assert os.environ["ARCHITEKT_JWT_SECRET"] == secret1
    assert cfg.read_text(encoding="utf-8").count("ARCHITEKT_JWT_SECRET=") == 1


def test_boxed_bootstrap_paths_in_app_data(monkeypatch, tmp_path):
    import env_bootstrap as eb

    _boxed_env(monkeypatch, tmp_path)
    eb.load_repo_env()
    for var in ("ARCHITEKT_DB_PATH", "COST_LOG_PATH", "EVENTS_LOG_PATH"):
        assert os.environ[var].startswith(str(tmp_path)), var


# ── review-fix 2026-07-17: cache poisoning, koszt utopiony, ratchet AW_ENV ──

def test_cache_key_v10_without_advisor_v11_with(monkeypatch):
    """Advisor wyłączony → klucz w przestrzeni v10 (ciepły cache przeżywa
    wdrożenie advisora); włączony → osobna przestrzeń v11."""
    import agents.base_agent as ba

    kw = dict(
        name="Szow", context="brief", model="claude-sonnet-5",
        temperature=1.0, language="pl", debate_mode="pelna",
        council_mode="personal",
    )
    k_off = ba.BaseAgent._cache_key(**kw, advisor=False)
    k_on = ba.BaseAgent._cache_key(**kw, advisor=True)
    assert k_off.startswith("llm:v10:Szow:")
    assert k_on.startswith("llm:v11:Szow:")
    assert k_off != k_on


def test_advisor_fallback_caches_under_v10_key(monkeypatch, tmp_path):
    """Gdy ścieżka advisora padnie, wynik fallbacku (bez advisora) NIE może
    wylądować pod kluczem v11/advisor=1 — to byłby cache poisoning."""
    import agents.base_agent as ba

    captured: dict = {}

    class _FakeRedis:
        async def get(self, key):
            captured.setdefault("get_keys", []).append(key)
            return None

        async def setex(self, key, ttl, value):
            captured["setex_key"] = key
            captured["setex_value"] = value

    client = _FakeClient(std_msg=_msg("STANDARD"), beta_side_effect=TypeError("stary SDK"))

    monkeypatch.setenv("COST_LOG_PATH", str(tmp_path / "cost.jsonl"))
    monkeypatch.delenv("DISABLE_CACHE", raising=False)
    monkeypatch.setattr(ba, "effective_llm_backend", lambda: "anthropic")
    agent = _dummy_agent()
    monkeypatch.setattr(agent, "_get_client", lambda: client)

    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(agent, "_get_redis", _fake_get_redis)

    async def _go():
        return await agent.acontribute("Testowy brief.", advisor_override=True)

    out = asyncio.run(_go())
    assert out == "STANDARD"
    # odczyt szedł po kluczu advisorowym (v11), zapis MUSI zejść na v10
    assert captured["get_keys"][0].startswith("llm:v11:")
    assert captured["setex_key"].startswith("llm:v10:"), captured["setex_key"]
    assert captured["setex_value"] == "STANDARD"


def test_advisor_partial_failure_keeps_sunk_cost(monkeypatch, tmp_path, caplog):
    """Iteracje zafakturowane przed błędem tury NIE znikają z rozliczenia —
    koszt utopiony przechodzi do advisor_cost i do logu."""
    import logging

    import agents.base_agent as ba

    paused = _msg(
        "częściowy tekst", stop_reason="pause_turn",
        iterations=[
            SimpleNamespace(type="executor_message", input_tokens=100, output_tokens=50),
            SimpleNamespace(type="advisor_message", input_tokens=2000, output_tokens=1000,
                            model="claude-opus-4-8"),
        ],
    )

    calls = {"n": 0}
    outer_client = _FakeClient(std_msg=_msg("STANDARD"))

    async def _beta_create(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return paused
        raise RuntimeError("rate-limit w środku konsultacji")

    outer_client.beta.messages.create = _beta_create

    monkeypatch.setenv("COST_LOG_PATH", str(tmp_path / "cost.jsonl"))
    monkeypatch.setenv("DISABLE_CACHE", "1")
    monkeypatch.setattr(ba, "effective_llm_backend", lambda: "anthropic")
    agent = _dummy_agent()
    monkeypatch.setattr(agent, "_get_client", lambda: outer_client)

    async def _go():
        return await agent.acontribute("Testowy brief.", advisor_override=True)

    with caplog.at_level(logging.ERROR, logger="agents.base_agent"):
        out = asyncio.run(_go())
    assert out == "STANDARD"
    sunk_logs = [r for r in caplog.records if "koszt utopiony" in r.getMessage()]
    assert sunk_logs, "brak logu kosztu utopionego"
    # advisor 2000 in / 1000 out na opus-4-8 (5/25 USD za 1M) = 0.01 + 0.025
    assert "$0.03" in sunk_logs[0].getMessage()


def test_extract_advisor_response_dedups_cumulative_text():
    """Wznowiona tura zwracająca treść SKUMULOWANĄ (prefiks powtórzony)
    nie może dawać zduplikowanej syntezy."""
    agent = _dummy_agent()
    r1 = _msg("Początek syntezy.", stop_reason="pause_turn")
    r2 = _msg("Początek syntezy. I jej dokończenie.", stop_reason="end_turn")
    text, _in, _out, _adv = agent._extract_advisor_response([r1, r2])
    assert text == "Początek syntezy. I jej dokończenie."

    # przyrostowa treść nadal jest DOKLEJANA
    r3 = _msg("Część A. ", stop_reason="pause_turn")
    r4 = _msg("Część B.", stop_reason="end_turn")
    text2, *_ = agent._extract_advisor_response([r3, r4])
    assert text2 == "Część A. Część B."


def test_boxed_env_ratchet_blocks_development(monkeypatch, tmp_path):
    """config.env z AW_ENV=development NIE zdejmuje postury boxed;
    production zostaje uszanowane (ratchet tylko w górę)."""
    import env_bootstrap as eb

    _boxed_env(monkeypatch, tmp_path)
    (tmp_path / "config.env").write_text("AW_ENV=development\n", encoding="utf-8")
    eb.load_repo_env()
    assert os.environ["AW_ENV"] == "boxed"

    os.environ.pop("AW_ENV", None)  # nie delenv — patrz komentarz w teście 0600
    (tmp_path / "config.env").write_text("AW_ENV=production\n", encoding="utf-8")
    eb.load_repo_env()
    assert os.environ["AW_ENV"] == "production"
