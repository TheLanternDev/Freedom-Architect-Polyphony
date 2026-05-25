"""Wrapper LLM — hybryda Haiku/Sonnet/Opus, lazy client, cost log, rozróżnione błędy."""
from __future__ import annotations
import json, os, time
from pathlib import Path
from typing import Optional

MODELS = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-6",
}
# uśrednione $/1k tok (estymata do dashboardu — nie do faktury)
PRICES = {"haiku": (0.001, 0.005), "sonnet": (0.003, 0.015), "opus": (0.015, 0.075)}

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
    pin, pout = PRICES.get(tier, (0, 0))
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
        r = await client.messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        dt = time.perf_counter() - t0
        usage = getattr(r, "usage", None)
        in_tok = getattr(usage, "input_tokens", 0) if usage else 0
        out_tok = getattr(usage, "output_tokens", 0) if usage else 0
        _log_cost(model_tier, model, in_tok, out_tok, dt)
        return r.content[0].text
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
