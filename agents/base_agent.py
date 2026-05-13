"""
BaseAgent – wspólna abstrakcja dla wszystkich członków Rady Nadzorczej.

Warstwa LLM v3.0:
- async (anthropic.AsyncAnthropic) — nie blokuje pętli FastAPI
- retry: tenacity, exp backoff + jitter, 5 prób
- cost monitoring: tokeny + szacunkowy koszt USD per call
- cache: Redis, TTL 3600s, klucz = sha256(context[:400] + model + temp)
- fallback: gdy brak ANTHROPIC_API_KEY albo wyczerpane retry
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from config.agent_models import (
    HYBRID_MODELS_ENABLED,
    ModelCfg,
    get_model_config,
)
from config.llm_providers import (
    anthropic_api_key,
    anthropic_omits_temperature,
    effective_llm_backend,
    map_claude_model_to_xai,
    xai_chat_completion,
)

# AKSJOMAT 2 — postscriptum wstrzykiwane do KAŻDEGO agenta. Importujemy lazy
# z try/except, żeby nie tworzyć cyklicznej zależności w testach jednostkowych.
try:  # pragma: no cover
    from core.completion_enforcer import AGENT_COMPLETION_POSTSCRIPT
except Exception:  # pragma: no cover
    AGENT_COMPLETION_POSTSCRIPT = ""

# AKSJOMAT 1 — typ podpowiedzi (nie egzekwujemy importem, żeby BaseAgent
# pozostał lekki i testowalny bez Pydantic Dream models).
if False:  # TYPE_CHECKING bez kosztu runtime
    from core.dream_architect import DreamArchitecture  # noqa: F401

logger = logging.getLogger(__name__)

# ── Lazy / opcjonalne zależności ────────────────────────────────────────────
# Importy wewnątrz try/except, żeby BaseAgent działał w trybie fallback
# nawet gdy anthropic / tenacity / redis nie są zainstalowane (testy, dev).

try:  # pragma: no cover
    import anthropic
    from anthropic import (
        APIConnectionError,
        APIError,
        APIStatusError,
        AsyncAnthropic,
        BadRequestError,
        RateLimitError,
    )
    _ANTHROPIC_OK = True

    # Tylko transient errors → retry. BadRequest / Auth są deterministyczne,
    # ponawianie ich = spalanie kredytów.
    _RETRYABLE = (RateLimitError, APIConnectionError)
except Exception:  # pragma: no cover
    anthropic = None
    AsyncAnthropic = None
    RateLimitError = APIConnectionError = APIError = APIStatusError = BadRequestError = Exception
    _ANTHROPIC_OK = False
    _RETRYABLE = (Exception,)

try:  # pragma: no cover
    from tenacity import (
        before_sleep_log,
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
        wait_random,
    )
    _TENACITY_OK = True
except Exception:  # pragma: no cover
    _TENACITY_OK = False

    def retry(*_a, **_kw):  # type: ignore[no-redef]
        def deco(fn):
            return fn
        return deco

    def stop_after_attempt(*_a, **_kw): return None       # type: ignore
    def wait_exponential(*_a, **_kw): return 0            # type: ignore
    def wait_random(*_a, **_kw): return 0                 # type: ignore
    def retry_if_exception_type(*_a, **_kw): return None  # type: ignore
    def before_sleep_log(*_a, **_kw): return None         # type: ignore

try:  # pragma: no cover
    import redis.asyncio as aioredis
    _REDIS_OK = True
except Exception:  # pragma: no cover
    aioredis = None
    _REDIS_OK = False


# ── Cennik (USD za 1M tokenów) — jedno miejsce do podmiany ──────────────────
# Zapis kosztów: `core.cost_tracking` (async append).
_PRICES_PER_M: dict[str, tuple[float, float]] = {
    # input, output
    "claude-opus-4-6":             (15.0, 75.0),
    "claude-sonnet-4-6":            (3.0, 15.0),
    "claude-haiku-4-5-20251001":    (0.25, 1.25),
    # legacy aliasy — bez kosztu „rozbicia”, gdy ktoś nadpisze przez env
    "claude-4-opus":               (15.0, 75.0),
    "claude-3-5-sonnet-20241022":   (3.0, 15.0),
    "claude-3-haiku":               (0.25, 1.25),
    # xAI (szacunki USD / 1M — do logów kosztu; API zwraca tokeny)
    "grok-3":                       (3.0, 15.0),
    "grok-3-mini":                  (0.3, 0.5),
}


class BaseAgent(ABC):
    """Abstrakcyjna klasa bazowa dla każdego agenta Rady."""

    # singleton-per-process (klient Anthropic + redis)
    _client: Optional["AsyncAnthropic"] = None
    _redis: Optional[Any] = None

    def __init__(self) -> None:
        self.emoji: str = ""
        self.name: str = ""
        self.role: str = ""
        self.instruction: str = ""

    # ── API agenta ──────────────────────────────────────────────────────────
    @abstractmethod
    def contribute(self, context: str) -> str:
        """Synchronous fallback – każdy agent musi mieć swój placeholder."""
        pass

    async def acontribute(
        self,
        context: str,
        dream: Optional[Any] = None,
        *,
        language: str = "pl",
        debate_mode: str = "pelna",
        evolution_note: Optional[str] = None,
    ) -> str:
        """
        Asynchroniczna wersja: realne wywołanie LLM (z cache + retry).

        `dream`: opcjonalny `DreamArchitecture` z AKSJOMATU 1. Jeśli przekazany,
        jego nagłówek (`as_agent_context()`) jest wstrzykiwany na początek
        system promptu, żeby każdy agent wiedział, JAKIE marzenie wspiera.

        `language`: 'pl' (default) lub 'en'. Steruje:
          - którą wersję `instruction*` użyć (jeśli istnieje `instruction_en`),
          - dyrektywą wyjściową ("Respond ONLY in English." / "Odpowiadaj po polsku."),
          - kluczem cache (oddzielnie dla obu języków).

        `debate_mode`: np. `codzienny` — niższy max_tokens (oszczędność API).

        `evolution_note` (P5): skrót wcześniejszych wypowiedzi tego agenta — prefix user-message.
        """
        ctx = context
        if evolution_note and evolution_note.strip():
            if language == "en":
                hdr = (
                    "[Council evolution — compressed notes from YOUR past turns only; "
                    "stay consistent or consciously revise]\n"
                )
            else:
                hdr = (
                    "[EWOLUCJA Rady — skrót z Twoich wcześniejszych wypowiedzi (tylko TY, "
                    "nie inni agenci). Zachowaj spójność albo świadomie zmień linię.]\n"
                )
            ctx = (
                hdr
                + evolution_note.strip()
                + "\n\n═══════════════════\n\n"
                + context
            )
        return await self._call_llm(
            ctx, dream=dream, language=language, debate_mode=debate_mode
        )

    def get_full_instruction(
        self, dream: Optional[Any] = None, *, language: str = "pl"
    ) -> str:
        """
        Składa pełną instrukcję systemową:
        [Architektura Marzenia (opt.)] + [tożsamość agenta] + [postscriptum AKSJOMATU 2]
        + [dyrektywa językowa].

        Jeśli agent zdefiniuje `instruction_en`, dla `language="en"` użyjemy jej.
        W przeciwnym wypadku zostawiamy polską `instruction` i dorzucamy dyrektywę
        "Respond ONLY in English." — Claude świetnie sobie z tym radzi.
        """
        parts: list[str] = []
        if dream is not None:
            try:
                parts.append(dream.as_agent_context())
            except Exception as e:  # pragma: no cover
                logger.warning("Dream context skipped for %s: %s", self.name, e)

        if language == "en":
            instr = getattr(self, "instruction_en", None) or self.instruction
        else:
            instr = getattr(self, "instruction_pl", None) or self.instruction
        parts.append(instr)

        if AGENT_COMPLETION_POSTSCRIPT:
            parts.append(AGENT_COMPLETION_POSTSCRIPT)

        if language == "en":
            parts.append(
                "═══ LANGUAGE DIRECTIVE ═══\n"
                "Respond ONLY in fluent, natural English. Even if instructions above are in "
                "Polish, your reply MUST be in English. Stay in character."
            )
        else:
            parts.append(
                "═══ DYREKTYWA JĘZYKOWA ═══\n"
                "Odpowiadaj WYŁĄCZNIE po polsku — niezależnie od języka briefu."
            )
        return "\n\n".join(p for p in parts if p)

    def get_model_config(self) -> ModelCfg:
        return get_model_config(self.name)

    def identity(self) -> str:
        return f"{self.emoji} {self.name} — {self.role}"

    def __repr__(self) -> str:
        cfg = self.get_model_config()
        return (
            f"<Agent {self.name} ({self.role}) "
            f"model={cfg['model']} t={cfg['temperature']}>"
        )

    # ── Warstwa LLM ─────────────────────────────────────────────────────────
    @classmethod
    def _get_client(cls) -> Optional["AsyncAnthropic"]:
        if not _ANTHROPIC_OK:
            return None
        if cls._client is None:
            api_key = anthropic_api_key()
            if not api_key:
                return None
            cls._client = AsyncAnthropic(api_key=api_key)
        return cls._client

    @classmethod
    async def _get_redis(cls):
        if not _REDIS_OK:
            return None
        if cls._redis is None:
            cls._redis = aioredis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                decode_responses=True,
            )
        return cls._redis

    @staticmethod
    def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        prices = _PRICES_PER_M.get(model)
        if not prices:
            return 0.0
        pin, pout = prices
        return (input_tokens * pin + output_tokens * pout) / 1_000_000

    @staticmethod
    def _cache_key(
        name: str,
        context: str,
        model: str,
        temperature: float,
        dream_id: Optional[str] = None,
        language: str = "pl",
        debate_mode: str = "pelna",
    ) -> str:
        # v6: izolacja cache per debate_mode (codzienny vs pełna Rada).
        raw = (
            f"{context[:400]}:{model}:{temperature}:{dream_id or ''}:{language}:{debate_mode}"
        ).encode("utf-8")
        return f"llm:v6:{name}:{hashlib.sha256(raw).hexdigest()}"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30) + wait_random(0, 2),
        retry=retry_if_exception_type(_RETRYABLE),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _call_llm(
        self,
        context: str,
        dream: Optional[Any] = None,
        *,
        language: str = "pl",
        debate_mode: str = "pelna",
    ) -> str:
        cfg = dict(self.get_model_config())
        if debate_mode == "codzienny":
            if self.name == "Syez":
                cfg["max_tokens"] = min(int(cfg["max_tokens"]), 1400)
            else:
                cfg["max_tokens"] = min(int(cfg["max_tokens"]), 380)
        backend = effective_llm_backend()
        client = self._get_client()
        if backend == "none" or (backend == "anthropic" and client is None):
            return self._fallback_contribute(context)

        dream_id = getattr(dream, "dream_id", None) if dream is not None else None
        cache_key = self._cache_key(
            self.name,
            context,
            cfg["model"],
            cfg["temperature"],
            dream_id=dream_id,
            language=language,
            debate_mode=debate_mode,
        )
        redis = await self._get_redis()
        if redis is not None:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    return cached
            except Exception as e:  # cache nigdy nie blokuje ścieżki głównej
                logger.warning("Cache read failed for %s: %s", self.name, e)

        system_prompt = self.get_full_instruction(dream=dream, language=language)
        user_msg = self._build_user_message(context, language=language)

        try:
            if backend == "xai":
                x_model = map_claude_model_to_xai(cfg["model"])
                response_text, in_tok, out_tok = await xai_chat_completion(
                    system=system_prompt,
                    user=user_msg,
                    model=x_model,
                    max_tokens=int(cfg["max_tokens"]),
                    temperature=float(cfg["temperature"]),
                )
                log_model = x_model
            else:
                assert client is not None
                create_kw: dict = {
                    "model": cfg["model"],
                    "max_tokens": cfg["max_tokens"],
                    "system": system_prompt,
                    "messages": [{
                        "role": "user",
                        "content": user_msg,
                    }],
                }
                if not anthropic_omits_temperature(cfg["model"]):
                    create_kw["temperature"] = cfg["temperature"]
                message = await client.messages.create(**create_kw)
                response_text = message.content[0].text.strip()
                in_tok = message.usage.input_tokens
                out_tok = message.usage.output_tokens
                log_model = cfg["model"]

            # Syez — kontrakt strict-PROSE; sanitizujemy JSON/markdown jeśli model się zbuntuje.
            if self.name == "Syez":
                response_text = self._sanitize_syez_output(response_text)

            cost = self._calculate_cost(log_model, in_tok, out_tok)
            logger.info(
                "LLM [%s] %s in=%d out=%d ≈ $%.4f",
                self.name, log_model, in_tok, out_tok, cost,
            )
            try:
                from core.cost_tracking import append_cost_log_async, build_cost_entry

                await append_cost_log_async(
                    build_cost_entry(
                        agent=self.name,
                        model=log_model,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cost_usd=cost,
                        context=context,
                    )
                )
            except Exception as e:
                logger.warning("Cost log write failed for %s: %s", self.name, e)

            if redis is not None:
                try:
                    await redis.setex(cache_key, 3600, response_text)
                except Exception as e:
                    logger.warning("Cache write failed for %s: %s", self.name, e)

            return response_text

        except _RETRYABLE:
            # transient — retry tenacity ponowi automatycznie
            raise
        except BadRequestError as e:
            # 400 = nasz błąd (zły config, za długi context, etc.) — fail fast
            logger.error("LLM BadRequest for %s: %s", self.name, e)
            raise
        except Exception as e:
            logger.error("LLM unrecoverable for %s: %s", self.name, e)
            return self._fallback_contribute(context)

    def _build_user_message(self, context: str, *, language: str = "pl") -> str:
        """
        Składa user-message dostosowany do roli agenta i języka odpowiedzi.

        Syez: żądanie czystej prozy (jeden blok ```mermaid` jako wyjątek).
        Reszta: 3 zdania, konkret, bez autoprezentacji.
        """
        if self.name == "Syez":
            if language == "en":
                return (
                    f"Input from the Council and the context:\n"
                    f"---\n{context}\n---\n\n"
                    f"RESPONSE RULES:\n"
                    f"1. Write PURE ENGLISH PROSE — for a human reader, not a parser.\n"
                    f"2. NO JSON and NO code fences EXCEPT one diagram block "
                    f"```mermaid … ``` (flowchart or sequenceDiagram).\n"
                    f"3. ALWAYS include: a monitor of tensions between specific "
                    f"agents (real contradictions), one Mermaid relationship "
                    f"diagram, and a separate section of open questions (min. four short).\n"
                    f"4. NO keys like `insights_per_agent`, `completion_audit` "
                    f"as code — it has to be prose.\n"
                    f"5. Completion audit (what remains, what blocks first, "
                    f"smallest move ≤60 min) WOVEN into prose.\n"
                    f"6. Length: 4–10 paragraphs; dash lists only when they help.\n\n"
                    f"Write the synthesis now."
                )
            return (
                f"Wejście od Rady i kontekst:\n"
                f"---\n{context}\n---\n\n"
                f"ZASADY ODPOWIEDZI:\n"
                f"1. Piszesz CZYSTĄ POLSKĄ PROZĄ — dla człowieka, nie parsera.\n"
                f"2. ZAKAZ JSON-a i bloków ``` poza JEDNYM wyjątkiem: diagram "
                f"w ```mermaid … ``` (flowchart lub sequenceDiagram).\n"
                f"3. ZAWSZE uwzględnij: monitor napięć między konkretnymi "
                f"agentami (sprzeczności), jeden diagram Mermaid relacji, oraz "
                f"osobną sekcję pytań otwartych (min. cztery krótkie pytania).\n"
                f"4. ZAKAZ kluczy jak `insights_per_agent`, `completion_audit` "
                f"jako kod — to ma być proza.\n"
                f"5. Audyt domknięcia (co zostało, co blokuje, najmniejszy ruch "
                f"≤60 min) WPLEĆ w prozę.\n"
                f"6. Długość: 4–10 akapitów; listy myślnikiem tylko gdy pomagają.\n\n"
                f"Napisz syntezę."
            )

        # 9 członków Rady — krótka proza
        if language == "en":
            return (
                f"User's brief (FYI — DO NOT quote, DO NOT paraphrase):\n"
                f"---\n{context}\n---\n\n"
                f"RESPONSE RULES:\n"
                f"1. NO self-presentation like 'I am analyzing...', 'I feel...', "
                f"'From my perspective...' — get to the point.\n"
                f"2. DO NOT repeat the brief or the word 'Context:'.\n"
                f"3. Max 3 sentences. Format: [observation] → [concrete suggestion "
                f"that gets one item closer to being ticked off in the functionality_checklist].\n"
                f"4. Start the message EXACTLY with: '{self.emoji} {self.name}: '\n"
                f"   then the substance immediately.\n\n"
                f"Reply now."
            )
        return (
            f"Brief użytkownika (do Twojej wiadomości — NIE cytuj, NIE parafrazuj):\n"
            f"---\n{context}\n---\n\n"
            f"ZASADY WYPOWIEDZI:\n"
            f"1. NIE pisz autoprezentacji typu 'Analizuję...', 'Czuję...', "
            f"'Z perspektywy...' — od razu konkret.\n"
            f"2. NIE powtarzaj briefu ani słowa 'Kontekst:'.\n"
            f"3. Maks. 3 zdania. Format: [obserwacja] → [konkretna sugestia "
            f"przybliżająca odhaczenie pozycji z functionality_checklist].\n"
            f"4. Zacznij wypowiedź dokładnie tak: '{self.emoji} {self.name}: '\n"
            f"   a potem od razu treść merytoryczna.\n\n"
            f"Odpowiedz teraz."
        )

    @staticmethod
    def _sanitize_syez_output(text: str) -> str:
        """
        Wymusza kontrakt strict-PROSE dla Syeza.

        Syez ma pisać do człowieka, nie do parsera. Mimo system promptu LLM
        czasem dolepia blok ```json {...}``` albo wręcz odpowiada samym JSON-em.
        Wyjątek: bloki ```mermaid … ``` są zachowywane (diagram).

        Strategia:
          1. Wyodrębnij bloki ```mermaid … ``` do placeholderów.
          2. Usuń pozostałe ogrodzenia ``` … ``` oraz nagie JSON-y.
          3. Przywróć placeholdery mermaid.
          4. Jeśli tekst jest pusty — komunikat graceful degradation.
        """
        if not text:
            return text

        import re

        placeholders: list[str] = []

        def _stash_mermaid(match: re.Match[str]) -> str:
            placeholders.append(match.group(0))
            return f"\n\n__SYEZ_PRESERVED_MERMAID_{len(placeholders) - 1}__\n\n"

        cleaned = re.sub(
            r"```mermaid\s*\n.*?```",
            _stash_mermaid,
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        cleaned = re.sub(
            r"```[a-zA-Z0-9_-]*\n?.*?```",
            "",
            cleaned,
            flags=re.DOTALL,
        )

        cleaned = re.sub(r"^\s*```[a-zA-Z0-9_-]*\s*$", "", cleaned, flags=re.MULTILINE)

        # usuń nagi obiekt JSON (gdy model dolepił bez fence)
        def _strip_naked_json(s: str) -> str:
            # Szukamy potencjalnych bloków JSON: { ... } na poziomie 0 zagnieżdżenia
            i = 0
            out = []
            while i < len(s):
                if s[i] == "{":
                    # Spróbuj znaleźć pasujący }
                    depth = 0
                    j = i
                    in_string = False
                    escape = False
                    while j < len(s):
                        c = s[j]
                        if escape:
                            escape = False
                        elif c == "\\":
                            escape = True
                        elif c == '"' and not escape:
                            in_string = not in_string
                        elif not in_string:
                            if c == "{":
                                depth += 1
                            elif c == "}":
                                depth -= 1
                                if depth == 0:
                                    candidate = s[i:j + 1]
                                    # Wycinaj tylko jeśli to faktycznie JSON-y
                                    # z kluczami w cudzysłowiu (heurystyka)
                                    try:
                                        parsed = json.loads(candidate)
                                        if isinstance(parsed, dict) and parsed:
                                            i = j + 1
                                            break
                                    except json.JSONDecodeError:
                                        pass
                                    out.append(s[i])
                                    i += 1
                                    break
                        j += 1
                    else:
                        out.append(s[i])
                        i += 1
                else:
                    out.append(s[i])
                    i += 1
            return "".join(out)

        cleaned = _strip_naked_json(cleaned)

        for i, block in enumerate(placeholders):
            cleaned = cleaned.replace(f"__SYEZ_PRESERVED_MERMAID_{i}__", block)

        # Krok 4: posprzątaj wiele pustych linii pod rząd
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

        # Krok 5: jeśli zostało puste — graceful degradation
        if not cleaned or len(cleaned) < 20:
            return (
                "⚪ Syez: Synteza nie została wygenerowana w czytelnej formie. "
                "Powtórz debatę lub uprość brief."
            )

        return cleaned

    def _fallback_contribute(self, context: str) -> str:
        """Bezpieczny fallback — używamy istniejącego sync `contribute`."""
        return self.contribute(context)
