"""Wrapper LLM — hybryda Haiku/Sonnet/Opus, lazy client, cost log, rozróżnione błędy."""
from __future__ import annotations
import json, logging, os, time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

MODELS = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-5",
    "opus":   "claude-opus-4-6",
}


def extract_message_text(message: Any) -> str:
    """Zbiera bloki `type=text` z odpowiedzi Anthropic (pomija thinking / tool_use).

    Nowe modele (np. claude-sonnet-5) często zwracają `ThinkingBlock` jako
    `content[0]` — bezpośrednie `content[0].text` rzuca AttributeError.
    """
    blocks = getattr(message, "content", None) or []
    parts: list[str] = []
    for block in blocks:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
    if parts:
        return "".join(parts).strip()
    # Legacy / mock bez `.type`: jeden blok z atrybutem `.text`.
    if len(blocks) == 1:
        text = getattr(blocks[0], "text", None)
        if isinstance(text, str):
            return text.strip()
    return ""


def _prices_per_1k(tier: str) -> tuple[float, float]:
    """$/1k tok z config/pricing.py (jedno źródło prawdy; promo wg daty).

    Nieznany model → (0, 0), ale `price_per_m` sam loguje wtedy warning (raz na
    proces). Świadomie NIE łykamy tu wszystkiego `except Exception` (review
    2026-07-30): to zamieniało literówkę w nazwie modelu albo błąd importu
    w cichy koszt $0.00 na dashboardzie, wyglądający jak poprawny wynik.
    """
    try:
        from config.pricing import price_per_m
    except ImportError:  # pragma: no cover — pricing jest częścią repo
        logger.error(
            "config.pricing niedostępny — koszty LLM będą logowane jako $0.00."
        )
        return (0.0, 0.0)
    per_m = price_per_m(MODELS.get(tier, ""))
    if per_m:
        return (per_m[0] / 1000.0, per_m[1] / 1000.0)
    return (0.0, 0.0)

_COST_LOG = Path(os.getenv("COST_LOG_PATH", "cost_log.jsonl"))
_client_singleton = None
_client_tried = False

def _get_client():
    global _client_singleton, _client_tried
    if _client_tried: return _client_singleton
    _client_tried = True
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import AsyncAnthropic
        _client_singleton = AsyncAnthropic()
    except Exception:
        _client_singleton = None
    return _client_singleton

def _log_cost(tier: str, model: str, in_tok: int, out_tok: int, latency_s: float) -> None:
    pin, pout = _prices_per_1k(tier)
    cost = (in_tok / 1000) * pin + (out_tok / 1000) * pout
    try:
        with _COST_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(), "tier": tier, "model": model,
                "in_tok": in_tok, "out_tok": out_tok,
                "cost_usd": round(cost, 6), "latency_s": round(latency_s, 3),
            }) + "\n")
    except OSError:
        pass


_DAILY_BUDGET = float(os.getenv("DAILY_BUDGET_USD", "5.0"))

def _today_spend() -> float:
    """Suma $ z cost_log.jsonl z ostatnich 24h."""
    if not _COST_LOG.exists(): return 0.0
    cutoff = time.time() - 86400
    total = 0.0
    try:
        with _COST_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if e.get("ts", 0) >= cutoff:
                        total += float(e.get("cost_usd", 0))
                except Exception:
                    continue
    except OSError:
        return 0.0
    return total

def _check_budget() -> None:
    if _today_spend() >= _DAILY_BUDGET:
        raise RuntimeError(f"Dzienny budżet ${_DAILY_BUDGET} przekroczony — zwiększ DAILY_BUDGET_USD lub poczekaj 24h.")

async def call_llm(model_tier: str, system: str, user: str, max_tokens: int = 512) -> str:
    _check_budget()
    client = _get_client()
    if client is None:
        return f"[STUB:{model_tier}] {user[:120]}..."
    model = MODELS.get(model_tier, MODELS["sonnet"])
    t0 = time.perf_counter()
    try:
        from anthropic import APIStatusError, AuthenticationError, RateLimitError
    except Exception:
        APIStatusError = AuthenticationError = RateLimitError = Exception  # type: ignore
    try:
        from config.llm_providers import (
            anthropic_omits_temperature,
            anthropic_thinking_config,
        )

        create_kw: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        # Uwaga: ten helper NIE wysyła `temperature` (używa domyślnej z API),
        # więc `anthropic_omits_temperature` nie ma tu czego pomijać. Wcześniej
        # stał tu `if not anthropic_omits_temperature(model): pass` — martwy
        # warunek sugerujący logikę, której nie było (review 2026-07-30).
        _thinking = anthropic_thinking_config(model)
        if _thinking is not None:
            create_kw["thinking"] = _thinking
        r = await client.messages.create(**create_kw)
        dt = time.perf_counter() - t0
        usage = getattr(r, "usage", None)
        in_tok = getattr(usage, "input_tokens", 0) if usage else 0
        out_tok = getattr(usage, "output_tokens", 0) if usage else 0
        _log_cost(model_tier, model, in_tok, out_tok, dt)
        return extract_message_text(r)
    except AuthenticationError as e:
        raise RuntimeError(f"LLM auth failed: {e}") from e
    except RateLimitError:
        # tylko rate-limit warto schodzić tier niżej
        if model_tier == "opus":   return await call_llm("sonnet", system, user, max_tokens)
        if model_tier == "sonnet": return await call_llm("haiku",  system, user, max_tokens)
        raise
    except APIStatusError as e:
        # 5xx → retry raz na sonnet jeśli byliśmy na opus; reszta → propaguj
        if model_tier == "opus":
            return await call_llm("sonnet", system, user, max_tokens)
        raise RuntimeError(f"LLM API error: {e}") from e
