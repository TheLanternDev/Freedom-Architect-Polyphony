"""
Wybór backendu LLM (Anthropic vs xAI OpenAI-compatible) i lekkie mapowanie modeli.

Zmienne:
  LLM_BACKEND=auto|anthropic|xai   (domyślnie auto)
  ANTHROPIC_API_KEY, XAI_API_KEY
  XAI_API_BASE — domyślnie https://api.x.ai/v1
  MODEL_XAI_OPUS, MODEL_XAI_SONNET, MODEL_XAI_HAIKU — gdy lecimy na xAI
  AW_ANTHROPIC_OMIT_TEMPERATURE_SUBSTR — opcjonalnie: dodatkowe fragmenty nazwy modelu
    (po przecinku), dla których nie wysyłamy `temperature` do Messages API (Anthropic
    zwraca 400 „deprecated for this model” m.in. dla Claude Opus 4.7).
"""

from __future__ import annotations

import os
from typing import Literal

LLMBackend = Literal["anthropic", "xai", "none"]


def _strip_key(name: str) -> str | None:
    v = os.getenv(name)
    if v is None:
        return None
    s = v.strip()
    return s or None


def anthropic_api_key() -> str | None:
    return _strip_key("ANTHROPIC_API_KEY")


def xai_api_key() -> str | None:
    return _strip_key("XAI_API_KEY")


def xai_api_base() -> str:
    return os.getenv("XAI_API_BASE", "https://api.x.ai/v1").strip() or "https://api.x.ai/v1"


def effective_llm_backend() -> LLMBackend:
    mode = os.getenv("LLM_BACKEND", "auto").strip().lower()
    ak, xk = anthropic_api_key(), xai_api_key()
    if mode == "anthropic":
        return "anthropic" if ak else "none"
    if mode == "xai":
        return "xai" if xk else "none"
    # auto
    if ak:
        return "anthropic"
    if xk:
        return "xai"
    return "none"


def anthropic_omits_temperature(model: str) -> bool:
    """
    Claude Opus 4.7 (wg Anthropic migration guide) odrzuca `temperature` w payloadzie
    z komunikatem 400 „deprecated for this model” — należy go pominąć.

    Dodatkowe dopasowania: `AW_ANTHROPIC_OMIT_TEMPERATURE_SUBSTR=a,b,c`
    (podłańcuchy w `model.lower()`, rozdzielone przecinkami).
    """
    m = (model or "").lower()
    if "opus-4-6" in m:
        return True
    raw = os.getenv("AW_ANTHROPIC_OMIT_TEMPERATURE_SUBSTR", "").strip()
    if not raw:
        return False
    for part in raw.split(","):
        p = part.strip().lower()
        if p and p in m:
            return True
    return False


def is_retryable_anthropic_exception(exc: Exception) -> bool:
    """HTTP 429/5xx/529 (overloaded) od Anthropic → retry."""
    code = getattr(getattr(exc, "response", None), "status_code", 0)
    if code == 529 or code == 429:
        return True
    return 500 <= code < 600


def map_claude_model_to_xai(claude_model: str) -> str:
    m = claude_model.lower()
    opus = os.getenv("MODEL_XAI_OPUS", "grok-3").strip() or "grok-3"
    sonnet = os.getenv("MODEL_XAI_SONNET", "grok-3-mini").strip() or "grok-3-mini"
    haiku = os.getenv("MODEL_XAI_HAIKU", "grok-3-mini").strip() or "grok-3-mini"
    if "opus" in m:
        return opus
    if "haiku" in m:
        return haiku
    return sonnet


_xai_async_client = None


def get_async_openai_xai_client():
    """Singleton AsyncOpenAI skonfigurowany pod endpoint x.ai."""
    global _xai_async_client
    if _xai_async_client is None:
        key = xai_api_key()
        if not key:
            return None
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return None
        _xai_async_client = AsyncOpenAI(api_key=key, base_url=xai_api_base())
    return _xai_async_client


async def xai_chat_completion(
    *,
    system: str,
    user: str,
    model: str,
    max_tokens: int,
    temperature: float,
) -> tuple[str, int, int]:
    client = get_async_openai_xai_client()
    if client is None:
        raise RuntimeError("xAI client unavailable (missing XAI_API_KEY or openai package)")
    t = max(0.0, min(2.0, float(temperature)))
    r = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=t,
    )
    text = (r.choices[0].message.content or "").strip()
    u = getattr(r, "usage", None)
    inp = int(getattr(u, "prompt_tokens", 0) or 0) if u else 0
    out = int(getattr(u, "completion_tokens", 0) or 0) if u else 0
    return text, inp, out
