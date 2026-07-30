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

import asyncio
import hashlib
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from config.agent_models import (
    ADVISOR_MAX_TOKENS,
    ADVISOR_MAX_USES,
    ADVISOR_MODEL,
    HYBRID_MODELS_ENABLED,
    ModelCfg,
    advisor_enabled_for,
    get_model_config,
)
from config.llm_providers import (
    LLM_TIMEOUT_SDK_SEC,
    LLM_TIMEOUT_WAIT_SEC,
    anthropic_api_key,
    anthropic_omits_temperature,
    anthropic_thinking_config,
    effective_llm_backend,
    map_claude_model_to_ollama,
    map_claude_model_to_xai,
    ollama_chat_completion,
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


class MissingLlmKeyError(RuntimeError):
    """Brak klucza Anthropic w żądaniu (BYOK fail-closed)."""


class InvalidLlmKeyError(RuntimeError):
    """Klucz Anthropic odrzucony przez API (np. 401)."""

try:
    from business_fa2.config.roles import FA2_BUSINESS_ROLES as _FA2_BUSINESS_ROLES
    from business_fa2.config.roles import FA2_BUSINESS_ROLES_EN as _FA2_BUSINESS_ROLES_EN
except ImportError:
    _FA2_BUSINESS_ROLES = {}  # type: ignore[assignment]
    _FA2_BUSINESS_ROLES_EN = {}  # type: ignore[assignment]


# ── Per-agent failure modes (poprawa rozumowania, chirurgiczna zmiana) ──────
# Każdy agent ma swój charakterystyczny błąd. Wstrzykiwane jako 1 zdanie do
# system promptu po higienie rozumowania. NIE zastępuje charakteru agenta —
# uzupełnia, jak alarm na własnej pułapce. Aktualizuj razem z evalem
# (`evals/rada/scorer.py`), żeby regresje były wychwytywalne.
_AGENT_FAILURE_MODES_PL: dict[str, str] = {
    "Kogit": "Twój błąd: racjonalizujesz odziedziczone założenie, "
             "udając że je analizujesz. Zanim nazwiesz założenie — sprawdź, "
             "czy nie służy ono Tobie samej w tej chwili.",
    "Szow": "Twój błąd: konfrontujesz zanim zobaczysz najmocniejszą wersję "
            "tezy którą tniesz. Konfrontacja bez steelmana to atak, nie wgląd.",
    "Kidi": "Twój błąd: uciekasz w ciekawość gdy jest trudno. "
            "Czysta ciekawość zostaje, gdy zostajesz w tym co bolesne.",
    "Tai": "Twój błąd: widzisz pętlę tam, gdzie są dwa różne zdarzenia. "
           "Trzy punkty to nie wzorzec — to trzy punkty. Sprawdź czy "
           "rzeczywiście się powtarza, czy tylko Ci to przypomina inne razem.",
    "Obver": "Twój błąd: dystansujesz się tak bardzo, że przestajesz być "
             "obecny. Meta-perspektywa bez kontaktu to ucieczka, nie obserwacja.",
    "Relacjan": "Twój błąd: projektujesz lojalność tam, gdzie jest tylko "
                "wpływ. Nie każda obecność innego człowieka to lojalność wobec niego.",
    "Emojy": "Twój błąd: zlewasz różne emocje w jedną. „Czuję ciężar” może "
             "ukrywać żal, gniew i wstyd jednocześnie — rozróżnij zanim nazwiesz.",
    "Smaty": "Twój błąd: nadinterpretujesz sygnał ciała. "
             "Napięcie w karku nie zawsze znaczy „opór” — czasem znaczy „za mało snu”.",
    "Deega": "Twój błąd: kopiesz do dzieciństwa, gdy odpowiedź jest w "
             "zeszłym tygodniu. Najstarszy wzorzec nie zawsze jest tym aktywnym.",
    "Syez": "Twój błąd: uśredniasz konfliktujące głosy do umiarkowanego "
            "stanowiska. Jeśli dwa głosy są w trwałym konflikcie — NAZWIJ konflikt, "
            "nie szukaj kompromisu. Sprzeczność jest informacją.",
}
_AGENT_FAILURE_MODES_EN: dict[str, str] = {
    "Kogit": "Your failure mode: you rationalise an inherited assumption "
             "under the guise of analysing it. Before naming the assumption, "
             "check whether it currently serves YOU.",
    "Szow": "Your failure mode: you confront before steelmanning the claim "
            "you are cutting. Confrontation without a steelman is attack, not insight.",
    "Kidi": "Your failure mode: you escape into curiosity when things get hard. "
            "Real curiosity stays when you stay with what hurts.",
    "Tai": "Your failure mode: you see a loop where there are three separate "
           "events. Three points are not a pattern — they are three points.",
    "Obver": "Your failure mode: you distance so far that you stop being present. "
             "Meta-perspective without contact is flight, not observation.",
    "Relacjan": "Your failure mode: you project loyalty where there is only "
                "influence. Not every relationship is a loyalty to that person.",
    "Emojy": "Your failure mode: you blend distinct emotions into one. "
             "‘I feel heavy’ may hide grief, anger and shame at once — separate them first.",
    "Smaty": "Your failure mode: you over-read body signals. Neck tension is not "
             "always resistance — sometimes it is just missed sleep.",
    "Deega": "Your failure mode: you dig into childhood when the answer is "
             "in last week. The oldest pattern is not always the active one.",
    "Syez": "Your failure mode: you average conflicting voices into a moderate "
            "stance. When two voices are in genuine conflict — NAME the conflict, "
            "do not seek compromise. Contradiction is information.",
}

# ── Lazy / opcjonalne zależności ────────────────────────────────────────────
# Importy wewnątrz try/except, żeby BaseAgent działał w trybie fallback
# nawet gdy anthropic / tenacity / redis nie są zainstalowane (testy, dev).

try:  # pragma: no cover
    import anthropic
    from anthropic import (
        APIConnectionError,
        APIError,
        APIStatusError,
        APITimeoutError,
        AsyncAnthropic,
        AuthenticationError,
        BadRequestError,
        RateLimitError,
    )
    _ANTHROPIC_OK = True

    # Tylko transient errors → retry. BadRequest / Auth są deterministyczne,
    # ponawianie ich = spalanie kredytów.
    _RETRYABLE = (RateLimitError, APIConnectionError)
    _LLM_TIMEOUT_ERRORS: tuple[type[BaseException], ...] = (
        asyncio.TimeoutError,
        APITimeoutError,
    )
except Exception:  # pragma: no cover
    anthropic = None
    AsyncAnthropic = None

    class APITimeoutError(Exception):  # noqa: N818 — stub gdy brak anthropic SDK
        """Placeholder — przy _ANTHROPIC_OK=False nieużywany."""

    RateLimitError = APIConnectionError = APIError = APIStatusError = BadRequestError = AuthenticationError = Exception
    _ANTHROPIC_OK = False
    _RETRYABLE = (Exception,)
    _LLM_TIMEOUT_ERRORS = (asyncio.TimeoutError,)

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


# ── Cennik: config/pricing.py (JEDYNE źródło prawdy; promo liczone datą) ────
# Zapis kosztów: `core.cost_tracking` (async append).
from config.pricing import price_per_m as _price_per_m


# ── Counter-hypothesis (anty-echo-chamber) ───────────────────────────────────
# Jeden agent na debatę (rotacyjnie wg hasha briefu) pełni rolę testu przesłanki.
# Ponieważ agenci lecą równolegle i nie widzą siebie, agent-kontra dedukuje
# DOMYŚLNĄ przesłankę z samego briefu — nie z innych głosów. Moduł = wspólny
# szkielet (struktura testu) + kalibracja per głos (zachowuje charakter agenta).
# Filozofia: wzmacnia Perspektywę i Uśmiech (AKSJOMAT 0) — ciekawość „a może
# inaczej?” zamiast 9-krotnego pogłębiania jednej diagnozy.

# Kalibracja tonu per agent — JEDNO zdanie w idiomie danego głosu. Klucz: imię.
_COUNTER_VOICE: dict[str, str] = {
    "Kogit":    "Testuj jak kognitywista: nazwij przesłankę jako zdanie logiczne i sprawdź, czy jej zaprzeczenie też się broni.",
    "Szow":     "Podważ ostro, ale to chłodny test przesłanki, nie Twoje zwykłe cięcie — nie myl jednego z drugim.",
    "Kidi":     "Testuj jak dziecko, które pyta z ciekawością „a co, jeśli jest dokładnie odwrotnie?” — bez analizy, ze zdziwieniem.",
    "Tai":      "Sprawdź, czy przeciwna hipoteza nie jest po prostu wcześniejszym ogniwem tej samej pętli czasowej.",
    "Obver":    "Opisz przeciwną sekwencję bez oceny — czysto, jak obserwator, który dopuszcza, że mapa jest odwrotna.",
    "Relacjan": "Sprawdź przesłankę przez relacje: a może to, co brief uznaje za problem, jest realną lojalnością wartą ochrony?",
    "Emojy":    "Testuj emocją: zanim nazwiesz, sprawdź, czy przeciwna hipoteza nie budzi ulgi zamiast oporu.",
    "Smaty":    "Sprawdź przesłankę ciałem: gdzie czujesz, że ta diagnoza NIE pasuje, gdzie ciało mówi „a jednak nie”.",
    "Deega":    "Sprawdź, czy przeciwna hipoteza nie jest starszym, prawdziwszym wzorcem niż ten, który brief bierze za oczywisty.",
}

_COUNTER_SKELETON_PL = (
    "═══ ROLA TESTU PRZESŁANKI (tylko w TEJ debacie) ═══\n"
    "Pełnisz dodatkowo rolę testu wspólnej przesłanki Rady. ZANIM dasz swój "
    "zwykły głos:\n"
    "(a) Nazwij w jednym zdaniu domyślne założenie, które ten brief traktuje "
    "jako oczywiste (np. „mury to tylko lęk”, „autentyczność zawsze wyzwala”).\n"
    "(b) Sformułuj hipotezę PRZECIWNĄ i wskaż, jaka konkretna informacja "
    "czyniłaby ją prawdziwą.\n"
    "(c) Dopiero potem swój zwykły głos.\n"
    "Nie podważasz dla sportu — testujesz, czy diagnoza Rady się broni. "
    "Zostajesz sobą; to Twój głos zwrócony na założenie, nie nowa rola.\n"
    "Jeśli brief NIE niesie ukrytej przesłanki wartej testu — powiedz to wprost "
    "jednym zdaniem i przejdź do zwykłego głosu. Nie wymyślaj kontrowersji.\n"
    "Kalibracja Twojego głosu: "
)

_COUNTER_SKELETON_EN = (
    "═══ PREMISE-TEST ROLE (this debate only) ═══\n"
    "You additionally carry the role of testing the Council's shared premise. "
    "BEFORE your usual voice:\n"
    "(a) Name in one sentence the default assumption this brief treats as "
    "obvious (e.g. „the walls are just fear”, „authenticity always frees”).\n"
    "(b) State the OPPOSITE hypothesis and what concrete evidence would make "
    "it true.\n"
    "(c) Only then your usual voice.\n"
    "You do not challenge for sport — you test whether the Council's diagnosis "
    "holds. You stay yourself; this is your voice turned onto the assumption, "
    "not a new role.\n"
    "If the brief carries NO hidden premise worth testing — say so plainly in "
    "one sentence and move to your usual voice. Do not invent controversy.\n"
    "Your voice calibration: "
)


class _AdvisorPathError(Exception):
    """Błąd w trakcie tury z Advisor toolem — niesie CZĘŚCIOWE odpowiedzi API
    (iteracje, które zdążyły wrócić przed błędem), żeby caller mógł doliczyć
    ich zafakturowany koszt do logu, zamiast udawać, że wydatku nie było."""

    def __init__(self, msg: str, responses: list[Any]):
        super().__init__(msg)
        self.responses = responses


class BaseAgent(ABC):
    """Abstrakcyjna klasa bazowa dla każdego agenta Rady."""

    # Per-klucz cache klientów Anthropic (BYOK) + redis singleton
    _CLIENT_CACHE_MAX = 32
    _client_cache: dict[str, "AsyncAnthropic"] = {}
    _client_cache_order: list[str] = []
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
        council_mode: str = "personal",
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        counter_role: bool = False,
        advisor_override: Optional[bool] = None,
    ) -> str:
        """
        Asynchroniczna wersja: realne wywołanie LLM (z cache + retry).

        `advisor_override`: nadpisuje `advisor_enabled_for()` dla TEGO wywołania.
        Użyj `False` dla wywołań mechanicznych (np. re-prompt naprawy formatu —
        `_attempt_completion_audit` w `debate_orchestrator.py`), gdzie treść
        merytoryczna się nie zmienia i konsultacja advisora byłaby podwójnym
        kosztem bez wartości. `None` (default) = decyduje konfiguracja.

        `counter_role` (anty-echo-chamber): gdy True, agent dostaje dodatkowy
        moduł testu wspólnej przesłanki (patrz `_COUNTER_SKELETON_*`). Ustawiany
        przez orchestrator dla DOKŁADNIE jednego agenta na debatę (rotacja wg
        hasha briefu). Wchodzi do klucza cache, więc nie koliduje z wariantem
        bez kontry.

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
            ctx, dream=dream, language=language, debate_mode=debate_mode,
            council_mode=council_mode,
            has_evolution_note=bool(evolution_note and evolution_note.strip()),
            tenant_id=tenant_id,
            user_id=user_id,
            counter_role=counter_role,
            advisor_override=advisor_override,
        )

    def get_full_instruction(
        self, dream: Optional[Any] = None, *, language: str = "pl",
        council_mode: str = "personal",
        has_evolution_note: bool = False,
        counter_role: bool = False,
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

        if council_mode == "fa2":
            # Kotwica tożsamości — tylko agenci Rady (nie Syez). Nie nadpisuje
            # oryginalnej instrukcji agenta (ta dochodzi niżej jako `instr`).
            if self.name != "Syez":
                if language == "en":
                    parts.append(
                        "You are a member of the Freedom Architect Supervisory Council "
                        "operating in a business context. Keep your original perspective and "
                        "philosophy — do not turn into a generic business consultant."
                    )
                else:
                    parts.append(
                        "Jesteś członkiem Rady Nadzorczej Architekta Wolności działającym "
                        "w kontekście biznesowym. Zachowaj swoją oryginalną perspektywę i "
                        "filozofię — nie zamieniaj się w ogólnego konsultanta biznesowego."
                    )
            _fa2_roles = _FA2_BUSINESS_ROLES_EN if language == "en" else _FA2_BUSINESS_ROLES
            fa2_role = _fa2_roles.get(self.name, "")
            if fa2_role:
                _fa2_header = (
                    "═══ FREEDOM ARCHITECT MODE (FA2) — BUSINESS ANALYST ═══\n"
                    if language == "en"
                    else "═══ TRYB FREEDOM ARCHITECT (FA2) — ANALITYK BIZNESOWY ═══\n"
                )
                parts.append(_fa2_header + fa2_role)
            # FA2 Syez ma własną instrukcję — wybór wg języka odpowiedzi.
            if language == "en":
                fa2_instr = getattr(self, "instruction_fa2_en", None) or getattr(
                    self, "instruction_fa2_pl", None
                )
            else:
                fa2_instr = getattr(self, "instruction_fa2_pl", None)
            if fa2_instr:
                parts.append(fa2_instr)
                # pomiń dalsze bloki — FA2 instruction jest kompletna
                if language == "en":
                    parts.append(
                        "═══ LANGUAGE DIRECTIVE ═══\n"
                        "Respond ONLY in fluent, natural English. Stay in character."
                    )
                else:
                    parts.append(
                        "═══ DYREKTYWA JĘZYKOWA ═══\n"
                        "Odpowiadaj WYŁĄCZNIE po polsku. Pozostań w roli."
                    )
                return "\n\n".join(p for p in parts if p)
        else:
            if dream is not None:
                # AKSJOMAT 0 (Filozofia Fragmentu) jest wstrzykiwany TUTAJ, na
                # czele kontekstu agenta — `dream.as_agent_context()` poprzedza
                # Architekturę Marzenia blokiem Fragmentu (Uśmiech ↔ Perspektywa
                # ↔ Droga). Hierarchia: AKSJOMAT 0 > AKSJOMAT 1 > AKSJOMAT 2.
                # Fragment jest osadzony w DreamArchitecture, więc nie wymaga
                # osobnego wstrzykiwania — płynie tym samym kanałem co marzenie.
                try:
                    parts.append(dream.as_agent_context())
                except Exception as e:  # pragma: no cover
                    logger.warning("Dream context skipped for %s: %s", self.name, e)

            # AKSJOMAT 1 — Obraz Użytkownika (destylat onboardingu). Wstrzykiwany
            # PO marzeniu, PRZED tożsamością agenta. Task-scoped ContextVar (agenci
            # to współdzielone singletony → dane usera NIE mogą wisieć na instancji).
            # Obraz KARMI marzenie, nie zastępuje go. Tylko tryb personal (nie fa2).
            try:
                from core.obraz_uzytkownika import get_obraz_context

                _obraz_ctx = get_obraz_context()
                if _obraz_ctx:
                    parts.append(_obraz_ctx)
            except Exception as e:  # pragma: no cover
                logger.warning("Obraz context skipped for %s: %s", self.name, e)

        if language == "en":
            instr = getattr(self, "instruction_en", None) or self.instruction
        else:
            instr = getattr(self, "instruction_pl", None) or self.instruction
        parts.append(instr)

        # Higiena rozumowania — tylko głosy Rady (nie Syez). Wspólna dla obu trybów;
        # w fa2 dochodzi rygor liczbowy, dla Szowa/Deegi steelman przed cięciem.
        # Cross-cutting — nie zmienia charakteru głosu.
        if self.name != "Syez":
            if language == "en":
                _hygiene = (
                    "Reasoning hygiene: tag each claim as observation / hypothesis / guess. "
                    "State only what you can support; do not invent facts. "
                    "For hypotheses and guesses: name in one phrase what concrete evidence "
                    "would raise OR lower your confidence — this cuts motivated reasoning."
                )
                if council_mode == "fa2":
                    _hygiene += (
                        " Every number carries a source or an explicit assumption. A FOURTH "
                        "STATE — only for data outside the brief (market metrics, medians, "
                        "report/benchmark names): wrap it in the marker ⟦weryfikuj: …⟧, e.g. "
                        "\"⟦weryfikuj: median time-to-revenue 14 mo, OpenView⟧\". Without this "
                        "marker do NOT state any external number or source — it is not an "
                        "observation, it is an assumption to verify."
                    )
                if self.name in ("Szow", "Deega"):
                    _hygiene += (
                        " Before you cut something down, state in one sentence the strongest "
                        "version of the claim you are about to challenge."
                    )
            else:
                _hygiene = (
                    "Higiena rozumowania: oznacz każde twierdzenie jako obserwacja / hipoteza "
                    "/ domysł. Pisz tylko to, co potrafisz podeprzeć; nie wymyślaj faktów. "
                    "Dla hipotez i domysłów: nazwij w jednym wyrażeniu, jaka konkretna "
                    "informacja podniosłaby ALBO obniżyła Twoją pewność — to ucina motivated "
                    "reasoning."
                )
                if council_mode == "fa2":
                    _hygiene += (
                        " Każda liczba ma źródło albo jawne założenie. CZWARTY STAN — "
                        "tylko dla danych spoza briefu (metryki rynkowe, mediany, nazwy "
                        "raportów/benchmarków): owiń je w znacznik ⟦weryfikuj: …⟧, np. "
                        "„⟦weryfikuj: mediana time-to-revenue 14 mc, OpenView⟧”. Bez tego "
                        "znacznika NIE podawaj żadnej liczby ani źródła zewnętrznego — to "
                        "nie obserwacja, to założenie do weryfikacji."
                    )
                if self.name in ("Szow", "Deega"):
                    _hygiene += (
                        " Zanim coś zetniesz, powiedz w jednym zdaniu najmocniejszą wersję "
                        "tezy, którą zaraz zakwestionujesz."
                    )
            parts.append(_hygiene)
            # Ryzyko B (niwelacja): głosy najczęściej cytujące twarde dane dostają
            # fa2-gated intensyfikator znacznika — żeby ⟦weryfikuj:…⟧ nie ginął pod
            # obciążeniem. Tylko fa2 (w personal znacznik nie istnieje).
            if council_mode == "fa2" and self.name in ("Obver", "Kogit", "Smaty", "Tai"):
                parts.append(
                    "You are one of the voices that cites hard data most — enforce "
                    "⟦weryfikuj:…⟧ on yourself for EVERY external number/source, no exceptions."
                    if language == "en"
                    else "Jesteś jednym z głosów najczęściej cytujących twarde dane — "
                    "egzekwuj na sobie ⟦weryfikuj:…⟧ przy KAŻDEJ liczbie/źródle spoza "
                    "briefu, bez wyjątku."
                )

        # Counter-hypothesis — tylko gdy ten agent pełni rolę testu przesłanki
        # (i nie jest Syezem). Szkielet (struktura testu) + kalibracja per głos,
        # żeby kontra brzmiała charakterem agenta, nie generycznym krytykiem.
        if counter_role and self.name != "Syez":
            _skeleton = _COUNTER_SKELETON_EN if language == "en" else _COUNTER_SKELETON_PL
            _voice = _COUNTER_VOICE.get(
                self.name,
                "Test the premise in your own characteristic register."
                if language == "en"
                else "Testuj przesłankę w swoim charakterystycznym rejestrze.",
            )
            parts.append(_skeleton + _voice)

        # Per-agent failure mode — chirurgiczny alarm na charakterystycznej pułapce
        # danego głosu. Dotyczy KAŻDEGO agenta (włącznie z Syezem), bo każdy ma
        # swój typowy błąd niewykrywany przez generyczną higienę. Dodawane na
        # końcu instrukcji, ZANIM dyrektywa językowa, żeby było ostatnią rzeczą
        # którą model widzi przed wypowiedzią.
        _failure_map = _AGENT_FAILURE_MODES_EN if language == "en" else _AGENT_FAILURE_MODES_PL
        _failure_line = _failure_map.get(self.name)
        if _failure_line:
            parts.append(_failure_line)

        if language == "en":
            try:
                from core.completion_enforcer import AGENT_COMPLETION_POSTSCRIPT_EN
                _postscript = AGENT_COMPLETION_POSTSCRIPT_EN
            except Exception:
                _postscript = AGENT_COMPLETION_POSTSCRIPT
        else:
            _postscript = AGENT_COMPLETION_POSTSCRIPT
        if _postscript:
            parts.append(_postscript)

        # Instrukcja o notatce ewolucyjnej — tylko agenci Rady (nie Syez w personal).
        if has_evolution_note and not (self.name == "Syez" and council_mode != "fa2"):
            if language == "en":
                parts.append(
                    "Your evolution note is at the start of the user message. Engage with it "
                    "consciously — either confirm continuity or deliberately revise your stance. "
                    "Do not ignore it."
                )
            else:
                parts.append(
                    "Twoja notatka ewolucyjna znajduje się na początku wiadomości użytkownika. "
                    "Odnieś się do niej świadomie — albo potwierdź ciągłość, albo świadomie zmień "
                    "stanowisko. Nie ignoruj jej."
                )

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

    def get_model_config(self, council_mode: str = "personal") -> ModelCfg:
        return get_model_config(self.name, council_mode=council_mode)

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
        api_key = anthropic_api_key()
        if not api_key:
            return None
        cache_id = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        cached = cls._client_cache.get(cache_id)
        if cached is not None:
            return cached
        client = AsyncAnthropic(
            api_key=api_key, timeout=float(LLM_TIMEOUT_SDK_SEC)
        )
        cls._client_cache[cache_id] = client
        cls._client_cache_order.append(cache_id)
        while len(cls._client_cache_order) > cls._CLIENT_CACHE_MAX:
            evict = cls._client_cache_order.pop(0)
            cls._client_cache.pop(evict, None)
        return client

    @classmethod
    async def _get_redis(cls):
        if not _REDIS_OK:
            return None
        if cls._redis is None:
            cls._redis = aioredis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return cls._redis

    @staticmethod
    async def _redis_op(coro, *, attempts: int = 2, timeout: float = 2.0):
        """Wykonaj operację Redis z krótkim timeoutem i max 2 próbami.

        Nigdy nie rzuca wyjątku — zwraca None przy błędzie (caller sprawdza).
        Łapie asyncio.TimeoutError, ConnectionError i każdy inny Exception."""
        import asyncio
        last_err = None
        for attempt in range(attempts):
            try:
                return await asyncio.wait_for(coro(), timeout=timeout)
            except (asyncio.TimeoutError, OSError, Exception) as e:
                last_err = e
                if attempt < attempts - 1:
                    continue
        # Wyczerpano próby — loguj i zwróć None (nie rzucaj)
        if last_err is not None:
            logger.warning(
                "Redis op failed after %d attempts: %s: %s",
                attempts, type(last_err).__name__, last_err,
            )
            logger.debug("Redis op traceback:", exc_info=last_err)
        return None

    @staticmethod
    def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        prices = _price_per_m(model)
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
        council_mode: str = "personal",
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        counter_role: bool = False,
        advisor: bool = False,
    ) -> str:
        # v11: TYLKO dla wywołań z advisorem (Advisor tool wpływa na
        # system_prompt/treść — inny wynik dla tego samego briefu). Wywołania
        # BEZ advisora zostają na v10 bajt-w-bajt: bump wersji dla wszystkich
        # unieważniałby cały ciepły cache (zimny start + realny koszt BYOK)
        # za feature domyślnie wyłączony. Rozdzielne przestrzenie kluczy dają
        # tę samą izolację co pole w kluczu.
        # v10: + llm_key_hash — izolacja cache między różnymi kluczami BYOK.
        # v9: + counter_role (anty-echo-chamber) w kluczu — ten sam brief z
        llm_key_hash = ""
        try:
            _ak = anthropic_api_key()
            if _ak:
                llm_key_hash = hashlib.sha256(_ak.encode("utf-8")).hexdigest()[:16]
        except Exception:
            pass
        base = (
            f"{context[:400]}:{model}:{temperature}:{dream_id or ''}:"
            f"{language}:{debate_mode}:{council_mode}:"
            f"{tenant_id or ''}:{user_id or ''}:{int(counter_role)}"
        )
        if advisor:
            raw = f"{base}:1:{llm_key_hash}".encode("utf-8")
            return f"llm:v11:{name}:{hashlib.sha256(raw).hexdigest()}"
        raw = f"{base}:{llm_key_hash}".encode("utf-8")
        return f"llm:v10:{name}:{hashlib.sha256(raw).hexdigest()}"

    @retry(
        # Tenacity retry TYLKO dla RateLimitError + APIConnectionError.
        # Timeouty (asyncio.TimeoutError, APITimeoutError) NIE są retry'owane —
        # propagowane do `_phase_council` jako agent_error{kind:'timeout'}.
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 2),
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
        council_mode: str = "personal",
        has_evolution_note: bool = False,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        counter_role: bool = False,
        advisor_override: Optional[bool] = None,
    ) -> str:
        use_advisor = (
            advisor_override
            if advisor_override is not None
            else advisor_enabled_for(self.name, debate_mode)
        )
        cfg = dict(self.get_model_config(council_mode=council_mode))
        if debate_mode == "codzienny":
            if self.name == "Syez":
                cfg["max_tokens"] = min(int(cfg["max_tokens"]), 1400)
            else:
                cfg["max_tokens"] = min(int(cfg["max_tokens"]), 380)
        backend = effective_llm_backend()
        # Advisor tool istnieje TYLKO w API Anthropic. Na xai/ollama instrukcja
        # „skonsultuj się z advisorem" kazałaby modelowi odgrywać nieistniejące
        # narzędzie w treści odpowiedzi. Gate PRZED cache_key (advisor= w kluczu).
        if use_advisor and backend != "anthropic":
            use_advisor = False
        client = self._get_client()
        if backend == "anthropic" and client is None:
            raise MissingLlmKeyError()
        if backend == "none":
            try:
                from api.settings import security_hardened

                if security_hardened():
                    raise MissingLlmKeyError()
            except MissingLlmKeyError:
                raise
            except Exception:
                pass
            return self._fallback_contribute(context)

        dream_id = getattr(dream, "dream_id", None) if dream is not None else None
        # Multi-tenancy hard isolation: gdy caller nie podał ID, sięgamy do
        # ContextVar z `db.tenant` (ustawianego przez middleware na podstawie
        # JWT claim `sub` / `tenant_id`). Try/except, żeby BaseAgent działał
        # w testach jednostkowych bez warstwy DB / w trybie offline.
        if tenant_id is None or user_id is None:
            try:
                from db.tenant import current_tenant_id, current_user_id
                if tenant_id is None:
                    tenant_id = current_tenant_id()
                if user_id is None:
                    user_id = current_user_id()
            except Exception:
                pass
        cache_key = self._cache_key(
            self.name,
            context,
            cfg["model"],
            cfg["temperature"],
            dream_id=dream_id,
            language=language,
            debate_mode=debate_mode,
            council_mode=council_mode,
            tenant_id=tenant_id,
            user_id=user_id,
            counter_role=counter_role,
            advisor=use_advisor,
        )
        redis = await self._get_redis()
        if redis is not None:
            try:
                cached = await self._redis_op(lambda: redis.get(cache_key))
                if cached:
                    # Metryki observability (Tydzień 2 mapy luk). Lazy import,
                    # żeby BaseAgent działał w testach bez api/_metrics.
                    try:
                        from api._metrics import llm_cache_hits_total
                        llm_cache_hits_total.labels(agent=self.name).inc()
                    except Exception:  # pragma: no cover
                        pass
                    return cached
                # Brak trafienia — odnotuj miss przed pójściem do LLM.
                try:
                    from api._metrics import llm_cache_misses_total
                    llm_cache_misses_total.labels(agent=self.name).inc()
                except Exception:  # pragma: no cover
                    pass
            except Exception as e:  # cache nigdy nie blokuje ścieżki głównej
                logger.warning("Cache read failed for %s: %s", self.name, e)

        system_prompt = self.get_full_instruction(
            dream=dream, language=language, council_mode=council_mode,
            has_evolution_note=has_evolution_note,
            counter_role=counter_role,
        )
        user_msg = self._build_user_message(
            context, language=language, council_mode=council_mode
        )

        advisor_cost = 0.0  # tylko backend anthropic z advisorem to nadpisuje
        advisor_suffix = ""  # do system promptu WYŁĄCZNIE dla wywołania z advisorem
        if use_advisor:
            # Advisor daje radę mid-generation, ale finalny tekst nadal piszesz
            # Ty, swoim głosem, wg formatu z instrukcji wyżej — bez tego agent
            # dolepia narrację „konsultuję się z advisorem”, co łamie format
            # (Rada: 3 zdania bez autoprezentacji; Syez: strict-PROSE).
            #
            # CELOWO osobna zmienna, nie mutacja system_prompt: gdy ścieżka
            # advisora padnie (stary SDK / 400 / rate-limit), fallbackowe
            # standardowe wywołanie MUSI iść z czystym promptem — inaczej
            # każemy modelowi używać narzędzia, którego w tym wywołaniu nie ma.
            #
            # Syez dostaje CELOWANE pytanie zamiast ogólnej instrukcji advisora
            # (ta wbudowana w narzędzie jest pisana pod agentowe pętle tool-use
            # w kodowaniu — "zapisz plik przed konsultacją" itp. — nietrafiona
            # dla jednorazowej syntezy prozą). Syez ma udokumentowany failure
            # mode: "uśredniasz konfliktujące głosy do umiarkowanego stanowiska"
            # (patrz _AGENT_FAILURE_MODES_PL powyżej) — advisor jest tu
            # najbardziej wart swojej ceny, gdy pyta się GO właśnie o to,
            # zamiast o generyczne "zaplanuj podejście".
            if self.name == "Syez":
                advisor_suffix = (
                    "\n\n═══ ADVISOR ═══\nZANIM zaczniesz pisać syntezę, "
                    "skonsultuj się z `advisor` (ciche wywołanie — nie "
                    "informuj o nim w odpowiedzi). Zapytaj go konkretnie: "
                    "(1) którą sprzeczność między głosami Rady ryzykujesz "
                    "uśrednić do umiarkowanego stanowiska zamiast ją nazwać "
                    "wprost — to Twój udokumentowany błąd; (2) czy audyt "
                    "domknięcia który planujesz (co zostało / co blokuje / "
                    "najmniejszy ruch ≤60 min) jest konkretny, nie ogólnikowy. "
                    "Rada advisora wpływa na TREŚĆ; format, długość i kontrakt "
                    "strict-PROSE z instrukcji wyżej zostają bez zmian."
                    if language != "en"
                    else "\n\n═══ ADVISOR ═══\nBEFORE you start writing the "
                    "synthesis, consult `advisor` (silent call — do not "
                    "narrate it in your reply). Ask it specifically: (1) which "
                    "tension between Council voices you're at risk of "
                    "averaging into a moderate stance instead of naming "
                    "directly — this is your documented failure mode; (2) "
                    "whether the completion audit you're planning (what "
                    "remains / what blocks / smallest move ≤60 min) is "
                    "concrete, not generic. Let the advice inform the "
                    "CONTENT; the format, length, and strict-PROSE contract "
                    "above stay unchanged."
                )
            else:
                advisor_suffix = (
                    "\n\n═══ ADVISOR ═══\nMasz dostęp do narzędzia `advisor` "
                    "(silniejszy model konsultowany w trakcie generacji). Użyj go "
                    "PRZED napisaniem odpowiedzi, jeśli sprawa jest nieoczywista — "
                    "ciche wywołanie, bez informowania o tym w odpowiedzi. Rada "
                    "advisora wpływa na TREŚĆ, format i długość odpowiedzi zostają "
                    "bez zmian (patrz instrukcja wyżej)."
                    if language != "en"
                    else "\n\n═══ ADVISOR ═══\nYou have access to an `advisor` tool "
                    "(a stronger model consulted mid-generation). Use it BEFORE "
                    "writing your answer if the call is non-obvious — call it "
                    "silently, do not narrate the consultation in your reply. Let "
                    "the advice inform the CONTENT; the format/length rules above "
                    "still apply unchanged."
                )

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
            elif backend == "ollama":
                o_model = map_claude_model_to_ollama(cfg["model"])
                response_text, in_tok, out_tok = await ollama_chat_completion(
                    system=system_prompt,
                    user=user_msg,
                    model=o_model,
                    max_tokens=int(cfg["max_tokens"]),
                    temperature=float(cfg["temperature"]),
                )
                log_model = o_model
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
                _thinking = anthropic_thinking_config(cfg["model"])
                if _thinking is not None:
                    create_kw["thinking"] = _thinking

                # Per-agent timeout (ModelCfg.timeout_s) — np. Syez fa2 z 5000 tok.
                # PODŁOGA, nie zamiennik: gdy globalny AW_LLM_TIMEOUT_WAIT jest
                # wyższy (np. .env = 120s), timeout_s=90 nie może go SKRACAĆ.
                # Belt+suspenders (wait_for > SDK) obowiązuje ZAWSZE, nie tylko
                # przy per-agent timeout_s — bez tego ścieżka globalna szła
                # z domyślnym timeoutem SDK (10 min) pod wait_for 55s i para
                # przestawała cokolwiek znaczyć.
                _wait_s = max(
                    float(cfg.get("timeout_s") or 0.0), float(LLM_TIMEOUT_WAIT_SEC)
                )
                create_kw["timeout"] = max(1.0, _wait_s - 10.0)

                advisor_done = False
                if use_advisor:
                    # Fail-open na STANDARDOWĄ ścieżkę (nie _fallback_contribute):
                    # stary SDK bez tej bety (TypeError na `betas=`/`tools=`),
                    # 400 na niedozwolonej parze modeli, rate-limit w środku
                    # konsultacji, pusty tekst, niedomknięty pause_turn —
                    # synteza MA powstać zwykłym wywołaniem; advisor to
                    # opcjonalne wzmocnienie, nie warunek odpowiedzi.
                    # Wyjątki łapiemy TUTAJ (nie propagujemy do tenacity):
                    # retry całej wielowywołaniowej konsultacji Opusa na
                    # kluczu BYOK mnożyłby koszt bez wartości.
                    _adv_responses: list[Any] = []
                    try:
                        adv_kw = dict(create_kw)
                        adv_kw["system"] = system_prompt + advisor_suffix
                        _adv_responses = await self._call_with_advisor(client, adv_kw)
                        (response_text, in_tok, out_tok,
                         advisor_cost) = self._extract_advisor_response(_adv_responses)
                        if _adv_responses and getattr(
                            _adv_responses[-1], "stop_reason", None
                        ) == "pause_turn":
                            raise RuntimeError(
                                f"pause_turn niedomknięty po {len(_adv_responses)} "
                                f"iteracjach — tekst byłby ucięty"
                            )
                        if not response_text:
                            raise RuntimeError("ścieżka advisora zwróciła pusty tekst")
                        advisor_done = True
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        # Częściowa konsultacja została już ZAFAKTUROWANA na
                        # kluczu BYOK (tokeny executora nieudanej tury + tokeny
                        # advisora) — NIE zerujemy, tylko przenosimy jako koszt
                        # utopiony do `advisor_cost`, żeby log kosztów mówił
                        # prawdę. Wcześniejsze `advisor_cost = 0.0` sprawiało,
                        # że realny wydatek znikał z trackingu.
                        if isinstance(e, _AdvisorPathError):
                            _adv_responses = e.responses or _adv_responses
                        _w_in, _w_out, _w_adv = 0, 0, 0.0
                        if _adv_responses:
                            _, _w_in, _w_out, _w_adv = (
                                self._extract_advisor_response(_adv_responses)
                            )
                        advisor_cost = (
                            self._calculate_cost(cfg["model"], _w_in, _w_out) + _w_adv
                        )
                        logger.error(
                            "LLM [%s] ścieżka advisora padła (%s: %s) — fallback "
                            "do standardowego wywołania bez advisora; koszt "
                            "utopiony nieudanej tury ≈ $%.4f (zaliczony do logu)",
                            self.name, type(e).__name__, e, advisor_cost,
                        )
                        # Wynik fallbacku powstaje BEZ advisora — musi trafić
                        # pod klucz cache advisor=False (v10). Zapis pod kluczem
                        # v11/advisor=1 serwowałby nie-advisorową odpowiedź jako
                        # advisorową do końca TTL (cache poisoning).
                        cache_key = self._cache_key(
                            self.name, context, cfg["model"], cfg["temperature"],
                            dream_id=dream_id, language=language,
                            debate_mode=debate_mode, council_mode=council_mode,
                            tenant_id=tenant_id, user_id=user_id,
                            counter_role=counter_role, advisor=False,
                        )
                if not advisor_done:
                    # Belt+suspenders: wait_for > SDK (AW_LLM_TIMEOUT_WAIT vs SDK).
                    try:
                        message = await asyncio.wait_for(
                            client.messages.create(**create_kw),
                            timeout=_wait_s,
                        )
                    except BadRequestError as _e:
                        # Nowe modele odrzucają `temperature` (400 "deprecated").
                        # Jeden retry bez parametru zamiast pustej syntezy.
                        # TYLKO typowany 400 (nie sniffing dowolnego Exception
                        # po stringu) — timeouty/5xx/sieć nie mają prawa wejść
                        # w tę gałąź, a warunek nie zależy od pełnej treści
                        # komunikatu, tylko od nazwy odrzuconego parametru.
                        _msg = str(_e).lower()
                        if "temperature" in create_kw and "temperature" in _msg:
                            logger.warning(
                                "LLM [%s] %s odrzucił `temperature` — retry bez parametru",
                                self.name, cfg["model"],
                            )
                            create_kw.pop("temperature", None)
                            message = await asyncio.wait_for(
                                client.messages.create(**create_kw),
                                timeout=_wait_s,
                            )
                        else:
                            raise
                    from shared.utils.llm import extract_message_text

                    response_text = extract_message_text(message)
                    # Sonnet 5 + adaptive thinking: thinking zjada max_tokens →
                    # content = [ThinkingBlock] bez text. Jeden retry z jawnym
                    # disabled (jeśli jeszcze nie) zamiast pustego głosu Rady.
                    if not response_text:
                        _types = [
                            getattr(b, "type", type(b).__name__)
                            for b in (message.content or [])
                        ]
                        _sr = getattr(message, "stop_reason", None)
                        if (
                            "thinking" in _types
                            and create_kw.get("thinking", {}).get("type") != "disabled"
                        ):
                            logger.warning(
                                "LLM [%s] %s: tylko thinking (stop=%s, types=%s) "
                                "— retry z thinking=disabled",
                                self.name, cfg["model"], _sr, _types,
                            )
                            create_kw["thinking"] = {"type": "disabled"}
                            message = await asyncio.wait_for(
                                client.messages.create(**create_kw),
                                timeout=_wait_s,
                            )
                            response_text = extract_message_text(message)
                        if not response_text:
                            raise ValueError(
                                f"LLM [{self.name}] zwrócił odpowiedź bez bloku text "
                                f"(content types: {_types}, stop_reason={_sr})"
                            )
                    _sr_final = getattr(message, "stop_reason", None)
                    if _sr_final == "max_tokens":
                        logger.warning(
                            "LLM [%s] %s: stop_reason=max_tokens (out≈%s, limit=%s) "
                            "— odpowiedź może być ucięta; podnieś max_tokens lub "
                            "trzymaj thinking=disabled",
                            self.name,
                            cfg["model"],
                            getattr(getattr(message, "usage", None), "output_tokens", "?"),
                            cfg["max_tokens"],
                        )
                    in_tok = message.usage.input_tokens
                    out_tok = message.usage.output_tokens
                log_model = cfg["model"]

            # Syez — kontrakt strict-PROSE; sanitizujemy JSON/markdown jeśli model się zbuntuje.
            if self.name == "Syez":
                response_text = self._sanitize_syez_output(response_text)

            cost = self._calculate_cost(log_model, in_tok, out_tok) + advisor_cost
            if advisor_cost:
                logger.info(
                    "LLM [%s] %s in=%d out=%d + advisor(%s) ≈ $%.4f (advisor $%.4f)",
                    self.name, log_model, in_tok, out_tok, ADVISOR_MODEL, cost, advisor_cost,
                )
            else:
                logger.info(
                    "LLM [%s] %s in=%d out=%d ≈ $%.4f",
                    self.name, log_model, in_tok, out_tok, cost,
                )
            # Strukturalny log (JSON gdy LOG_FORMAT=json) + Prometheus counter.
            try:
                from api._log import slog
                from api._metrics import llm_calls_total
                slog(
                    "llm_call_completed",
                    agent=self.name, model=log_model,
                    input_tokens=in_tok, output_tokens=out_tok,
                    cost_usd=round(cost, 6),
                    council_mode=council_mode, language=language,
                )
                llm_calls_total.labels(
                    agent=self.name, model=log_model, status="success"
                ).inc()
            except Exception:  # pragma: no cover
                pass
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
                    await self._redis_op(
                        lambda: redis.setex(cache_key, 3600, response_text)
                    )
                except Exception as e:
                    logger.warning("Cache write failed for %s: %s", self.name, e)

            return response_text

        except _RETRYABLE:
            # transient — retry tenacity ponowi automatycznie
            raise
        except AuthenticationError:
            raise InvalidLlmKeyError() from None
        except BadRequestError as e:
            # 400 = nasz błąd (zły config, za długi context, etc.) — fail fast
            logger.error("LLM BadRequest for %s: %s", self.name, e)
            raise
        except _LLM_TIMEOUT_ERRORS:
            try:
                from api._log import slog
                from api._metrics import llm_calls_total

                slog(
                    "llm_call_timeout",
                    agent=self.name,
                    model=cfg["model"],
                    timeout_s=LLM_TIMEOUT_WAIT_SEC,
                )
                llm_calls_total.labels(
                    agent=self.name, model=cfg["model"], status="timeout"
                ).inc()
            except Exception:  # pragma: no cover
                pass
            raise
        except Exception as e:
            logger.error("LLM unrecoverable for %s: %s", self.name, e)
            try:
                from api._metrics import llm_calls_total

                llm_calls_total.labels(
                    agent=self.name, model=cfg["model"], status="error"
                ).inc()
            except Exception:  # pragma: no cover
                pass
            return self._fallback_contribute(context)

    # ── Advisor tool (beta advisor-tool-2026-03-01) ────────────────────────
    # Executor = ten agent (Sonnet 5), advisor = model silniejszy (domyślnie
    # Opus 4.8, config/agent_models.py). Włączane per agent/tryb debaty przez
    # `advisor_enabled_for()` — domyślnie WYŁĄCZONE globalnie.
    #
    # UWAGA: ten kod NIE był odpalony przeciw prawdziwemu API (środowisko bez
    # dostępu do sieci Anthropic w momencie pisania) — kształt `usage.iterations`
    # jest zaimplementowany defensywnie wg docs, ale wymaga jednego realnego
    # przebiegu z AW_ADVISOR_ENABLED=true zanim zaufasz kosztom w produkcji.
    # Patrz docs Anthropic: platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool

    async def _call_with_advisor(self, client: "AsyncAnthropic", create_kw: dict) -> list[Any]:
        """Woła `beta.messages.create` z tools=[advisor] i obsługuje
        `stop_reason: "pause_turn"` (advisor call w toku) doreszłowaniem tury —
        patrz sekcja „Resuming a paused turn” w docs. Zwraca listę wszystkich
        odpowiedzi API złożonych na tę turę (zwykle 1, czasem 2-3 przy pauzach).

        Błąd W TRAKCIE tury (timeout, API error między iteracjami pause_turn)
        → `_AdvisorPathError` z częściowymi `responses`: caller musi umieć
        doliczyć koszt już zafakturowanych iteracji, mimo że tura padła."""
        tools = [{
            "type": "advisor_20260301",
            "name": "advisor",
            "model": ADVISOR_MODEL,
            "max_uses": ADVISOR_MAX_USES,
            "max_tokens": ADVISOR_MAX_TOKENS,
        }]
        betas = ["advisor-tool-2026-03-01"]
        messages = list(create_kw["messages"])
        # Advisor (np. opus-4-8) w turze wymusza reguły nowszych modeli:
        # `temperature` w payloadzie → 400 "deprecated". Wycinamy prewencyjnie.
        # UWAGA (świadomy side-effect, logowany): executor traci wtedy swoją
        # temperature (np. Syez 0.5 → default API) na czas tury z advisorem.
        if anthropic_omits_temperature(ADVISOR_MODEL) and "temperature" in create_kw:
            logger.info(
                "Advisor [%s]: para z %s wymusza brak `temperature` — "
                "executor idzie z domyślnym samplingiem w tej turze",
                self.name, ADVISOR_MODEL,
            )
            create_kw = {k: v for k, v in create_kw.items() if k != "temperature"}
        responses: list[Any] = []
        # Jeden ŁĄCZNY budżet czasu na całą turę (deadline), nie pełny timeout
        # per iteracja — inaczej 4 pauzy × 100s dawałyby ~7-minutową syntezę,
        # której pipeline SSE nie ma prawa tolerować.
        _budget = (
            float(create_kw["timeout"]) + 10.0
            if create_kw.get("timeout")
            else float(LLM_TIMEOUT_WAIT_SEC)
        )
        _loop = asyncio.get_running_loop()
        _deadline = _loop.time() + _budget
        # Bounded — dokumentacja mówi "a resumed turn can pause again", ale nie
        # ma twardego limitu; 4 próby to margines bez ryzyka pętli w nieskończoność.
        try:
            for _ in range(4):
                kw = dict(create_kw)
                kw["messages"] = messages
                kw["tools"] = tools
                kw["betas"] = betas
                _remaining = _deadline - _loop.time()
                if _remaining <= 0:
                    raise asyncio.TimeoutError(
                        f"advisor: budżet {_budget:.0f}s wyczerpany po {len(responses)} iteracjach"
                    )
                message = await asyncio.wait_for(
                    client.beta.messages.create(**kw),
                    timeout=_remaining,
                )
                responses.append(message)
                if getattr(message, "stop_reason", None) != "pause_turn":
                    break
                # Domknięty advisor call w toku, brak naszego tool_use do obsłużenia
                # (patrz base_agent — agenci Rady nie mają własnych client tools) —
                # doślij assistant content bez zmian, bez nowego user message.
                messages = messages + [{"role": "assistant", "content": message.content}]
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Iteracje, które ZDĄŻYŁY wrócić, są już zafakturowane — oddaj je
            # callerowi razem z błędem (koszt utopiony do logu kosztów).
            raise _AdvisorPathError(str(exc), responses) from exc
        return responses

    def _extract_advisor_response(self, responses: list[Any]) -> tuple[str, int, int, float]:
        """Skleja tekst finalny + sumuje tokeny executora i koszt advisora
        (osobne stawki — `usage.iterations[].type == "advisor_message"`).

        Fallback gdy SDK nie zna jeszcze `usage.iterations` (starsza wersja
        `anthropic` niż ta beta): liczy WSZYSTKO jako tokeny executora —
        koszt będzie zaniżony o realny koszt advisora, ale nic nie wybucha.

        Dedup przy pause_turn: wznowiona tura MOŻE zwrócić treść skumulowaną
        (powtórzyć dotychczasowy tekst + kontynuację) zamiast samego przyrostu.
        Naiwna konkatenacja dawałaby wtedy zduplikowaną syntezę — jeśli tekst
        kolejnej odpowiedzi zaczyna się od całości dotychczasowej, traktujemy
        go jako skumulowany i ZASTĘPUJEMY, nie doklejamy."""
        acc = ""
        in_tok = 0
        out_tok = 0
        advisor_cost = 0.0
        for message in responses:
            part = "".join(
                (getattr(block, "text", "") or "")
                for block in (getattr(message, "content", []) or [])
                if getattr(block, "type", None) == "text"
            )
            if part:
                if acc and part.startswith(acc):
                    acc = part  # treść skumulowana — zastąp
                else:
                    acc += part  # przyrost — doklej
            usage = getattr(message, "usage", None)
            iterations = getattr(usage, "iterations", None) if usage is not None else None
            if iterations:
                for it in iterations:
                    it_type = getattr(it, "type", None)
                    it_in = int(getattr(it, "input_tokens", 0) or 0)
                    it_out = int(getattr(it, "output_tokens", 0) or 0)
                    if it_type == "advisor_message":
                        it_model = getattr(it, "model", None) or ADVISOR_MODEL
                        advisor_cost += self._calculate_cost(it_model, it_in, it_out)
                    else:
                        in_tok += it_in
                        out_tok += it_out
            elif usage is not None:
                in_tok += int(getattr(usage, "input_tokens", 0) or 0)
                out_tok += int(getattr(usage, "output_tokens", 0) or 0)
        return acc.strip(), in_tok, out_tok, advisor_cost

    def _build_user_message(self, context: str, *, language: str = "pl",
                            council_mode: str = "personal") -> str:
        """
        Składa user-message dostosowany do roli agenta i języka odpowiedzi.

        Syez: żądanie czystej prozy (jeden blok ```mermaid` jako wyjątek).
        Reszta: 3 zdania, konkret, bez autoprezentacji.
        """
        if self.name == "Syez" and council_mode == "fa2":
            # #A/#B: protokół FA2 ma JEDNO źródło prawdy — instrukcja systemowa
            # (FA2_SYEZ_INSTRUCTION_PL / _EN). Tu tylko podajemy materiał i
            # wywołujemy protokół; bez drugiego, rozjeżdżającego się zestawu kroków.
            if language == "en":
                return (
                    f"Business briefing and Council Analysts' reports:\n"
                    f"---\n{context}\n---\n\n"
                    f"Write the synthesis now, strictly following the FA2 protocol "
                    f"from your system instruction (Steps 1–8, including the «One "
                    f"step now:» paragraph and the explicit weakest-link call)."
                )
            return (
                f"Briefing biznesowy i analizy Rady Analityków:\n"
                f"---\n{context}\n---\n\n"
                f"Napisz syntezę teraz, ściśle według protokołu FA2 z Twojej "
                f"instrukcji systemowej (Kroki 1–8, w tym akapit «Jeden krok "
                f"teraz:» oraz jawne wskazanie najsłabszego ogniwa)."
            )

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

        # FA2 — analitycy biznesowi: dłuższa, strukturalna analiza
        if council_mode == "fa2":
            return (
                f"Zapytanie biznesowe:\n"
                f"---\n{context}\n---\n\n"
                f"ZASADY TWOJEJ ANALIZY:\n"
                f"1. Zacznij dokładnie tak: '{self.emoji} {self.name}: '\n"
                f"2. Twoja odpowiedź to analiza z Twojej specjalizacji — konkretne liczby, "
                f"nazwy platform, przedziały kosztów, metryki rynkowe. Każda metryka "
                f"rynkowa / nazwa raportu / mediana SPOZA briefu MUSI być w znaczniku "
                f"⟦weryfikuj: …⟧; nie podawaj liczby zewnętrznej bez tego znacznika.\n"
                f"3. Zaproponuj 1–2 konkretne nisze/pomysły pasujące do briefu, "
                f"z krótkim uzasadnieniem dlaczego właśnie te.\n"
                f"4. Długość: 4–8 zdań. Bez autoprezentacji i bez ogólników.\n\n"
                f"Odpowiedz teraz."
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
                f"that gets one item closer to being ticked off in the functionality_checklist]. "
                f"The suggestion must follow from YOUR specialization — one no other "
                f"agent could voice; avoid generic all-purpose moves (Syez consolidates them). "
                f"If your reflex move is one ANY voice could give (e.g. 'write/call someone "
                f"and ask X') — drop it and give a micro-move only your pole could name, or "
                f"give none.\n"
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
            f"przybliżająca odhaczenie pozycji z functionality_checklist]. Sugestia musi "
            f"wynikać z TWOJEJ specjalizacji — taka, której nie wygłosiłby inny agent; "
            f"unikaj ruchów ogólnozadaniowych (Syez je skonsoliduje). Jeśli Twój "
            f"odruchowy ruch mógłby paść z ust dowolnego głosu (np. «napisz/zadzwoń "
            f"do kogoś i zapytaj o X») — porzuć go i daj mikro-ruch wyłącznie ze "
            f"swojego bieguna albo nie dawaj żadnego.\n"
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

        # Jawne bloki ```json … ``` (także wewnątrz prozy) — usuń przed regułą ogólną.
        cleaned = re.sub(
            r"```json\b.*?```",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )

        cleaned = re.sub(
            r"```[a-zA-Z0-9_-]*\n?.*?```",
            "",
            cleaned,
            flags=re.DOTALL,
        )

        cleaned = re.sub(r"^\s*```[a-zA-Z0-9_-]*\s*$", "", cleaned, flags=re.MULTILINE)

        # Linie wyglądające na surowy JSON ({...} lub [...] na początku linii).
        # Mermaid jest już ostashowany do placeholderów, więc go nie ruszamy.
        cleaned = re.sub(
            r'^\s*[{\[].*?[}\]],?\s*$',
            "",
            cleaned,
            flags=re.MULTILINE,
        )

        # usuń nagi obiekt JSON (gdy model dolepił bez fence)
        def _strip_naked_json(s: str) -> str:
            # Prostsze podejście: iterujemy po pozycjach '{', próbujemy json.loads
            # od każdej z nich do najbliższego '}' od końca. Usuwamy tylko valid dict.
            result = s
            i = 0
            while i < len(result):
                if result[i] != "{":
                    i += 1
                    continue
                # Szukaj ostatniego '}' — próbuj coraz krótsze podciągi
                last_brace = result.rfind("}", i + 1)
                removed = False
                while last_brace > i:
                    candidate = result[i:last_brace + 1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict) and parsed:
                            # Usuwamy ten fragment
                            result = result[:i] + result[last_brace + 1:]
                            removed = True
                            break
                    except (json.JSONDecodeError, ValueError):
                        pass
                    last_brace = result.rfind("}", i + 1, last_brace)
                if not removed:
                    i += 1
            return result

        cleaned = _strip_naked_json(cleaned)

        # Próg sensownej prozy liczymy PRZED przywróceniem mermaid (sam tekst).
        prose_only = re.sub(r"__SYEZ_PRESERVED_MERMAID_\d+__", "", cleaned)
        prose_len = len(re.sub(r"\s+", " ", prose_only).strip())

        for i, block in enumerate(placeholders):
            cleaned = cleaned.replace(f"__SYEZ_PRESERVED_MERMAID_{i}__", block)

        # Krok 4: posprzątaj wiele pustych linii pod rząd
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

        # Krok 5: mniej niż 20 znaków sensownej prozy → graceful degradation.
        # Wyjątek: zachowany diagram mermaid jest sam w sobie wartościową treścią.
        if not cleaned or (prose_len < 20 and not placeholders):
            return (
                "⚪ Syez: Synteza nie została wygenerowana w czytelnej formie. "
                "Powtórz debatę lub uprość brief."
            )

        return cleaned

    def _fallback_contribute(self, context: str) -> str:
        """Bezpieczny fallback — używamy istniejącego sync `contribute`."""
        return self.contribute(context)
