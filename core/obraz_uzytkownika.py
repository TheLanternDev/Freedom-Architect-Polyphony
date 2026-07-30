"""AKSJOMAT 1 — Obraz Użytkownika (destylat onboardingu).

Cichy ekstrakt 24 odpowiedzi onboardingowych w trwały, wysokosygnałowy model,
który Rada widzi przez ten sam kanał co Architekturę Marzenia. NIE jest 10. głosem
— działa jak `dream_architect.adistill_dream`: dystyluje, nie komentuje.

Zasady (bezwzględne):
  • Zero dopowiadania — w danym wymiarze brak danych → pole puste. Żadnej inferencji
    ponad to, co użytkownik napisał.
  • `zdanie_dla_siebie` to DOSŁOWNY cytat użytkownika (najwyższa wartość), nie parafraza.
  • `as_agent_context()` ma twardy limit długości — wstrzykiwany do KAŻDEGO agenta,
    więc każdy nadmiarowy znak rozmywa sygnał Rady.

Wstrzykiwanie: ContextVar `current_obraz_context` (task-scoped, jak tenant_id).
Agenci Rady to współdzielone singletony — trzymanie danych usera na instancji
agenta groziłoby wyciekiem cross-tenant. ContextVar jest izolowany per-asyncio-Task.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from config.llm_providers import (
    DREAM_TIMEOUT_WAIT_SEC,
    LLM_TIMEOUT_SDK_SEC,
    anthropic_api_key,
    anthropic_omits_temperature,
    anthropic_thinking_config,
    effective_llm_backend,
    map_claude_model_to_ollama,
    map_claude_model_to_xai,
    ollama_chat_completion,
    xai_chat_completion,
)
from core.dream_architect import _parse_llm_json_object  # współdzielony parser JSON
from personal_v1.rituals.onboarding import PYTANIA, SEKCJE

logger = logging.getLogger(__name__)

# Twardy limit kontekstu wstrzykiwanego do agenta (ochrona sygnału Rady).
_MAX_FIELD_CHARS = 220
_MAX_LIST_ITEMS = 3
_MAX_CONTEXT_CHARS = 1100


class ObrazUzytkownika(BaseModel):
    """Trwały obraz użytkownika z onboardingu. Wszystkie pola opcjonalne —
    puste = brak danych w wymiarze (zero dopowiadania)."""

    wartosci: list[str] = Field(default_factory=list)      # Kogit
    napiecia: list[str] = Field(default_factory=list)      # Szow / Deega
    relacje: list[str] = Field(default_factory=list)       # Relacjan
    wzorce: list[str] = Field(default_factory=list)        # Tai
    cialo: str = ""                                          # Smaty
    kreatywnosc: str = ""                                    # Kidi
    duchowosc: str = ""                                      # Deega / Obver
    potrzeba_teraz: str = ""                                 # seed Daily Signal
    zdanie_dla_siebie: str = ""                              # surowy cytat usera
    wersja: int = 1
    zrodlo: Literal["onboarding"] = "onboarding"

    def is_empty(self) -> bool:
        return not any(
            [
                self.wartosci, self.napiecia, self.relacje, self.wzorce,
                self.cialo.strip(), self.kreatywnosc.strip(), self.duchowosc.strip(),
                self.potrzeba_teraz.strip(), self.zdanie_dla_siebie.strip(),
            ]
        )

    def as_agent_context(self) -> str:
        """Zwięzły, wysokosygnałowy blok do system-promptu agenta (twardy limit).

        Tylko niepuste wymiary. Hierarchia: ten blok KARMI Architekturę Marzenia,
        nie zastępuje jej — wstrzykiwany PO marzeniu, PRZED tożsamością agenta.
        """
        if self.is_empty():
            return ""

        def _clip(s: str) -> str:
            s = " ".join(s.split())
            return s if len(s) <= _MAX_FIELD_CHARS else s[: _MAX_FIELD_CHARS - 1].rstrip() + "…"

        def _list(items: list[str]) -> str:
            return "; ".join(_clip(x) for x in items[:_MAX_LIST_ITEMS] if x.strip())

        lines: list[str] = ["═══ OBRAZ UŻYTKOWNIKA (kontekst służący AKSJOMATOWI 1) ═══"]
        if self.wartosci:
            lines.append(f"Wartości: {_list(self.wartosci)}")
        if self.napiecia:
            lines.append(f"Napięcia/cień: {_list(self.napiecia)}")
        if self.relacje:
            lines.append(f"Relacje: {_list(self.relacje)}")
        if self.wzorce:
            lines.append(f"Wzorce: {_list(self.wzorce)}")
        if self.cialo.strip():
            lines.append(f"Ciało: {_clip(self.cialo)}")
        if self.kreatywnosc.strip():
            lines.append(f"Kreatywność: {_clip(self.kreatywnosc)}")
        if self.duchowosc.strip():
            lines.append(f"Duchowość: {_clip(self.duchowosc)}")
        if self.potrzeba_teraz.strip():
            lines.append(f"Potrzeba teraz: {_clip(self.potrzeba_teraz)}")
        if self.zdanie_dla_siebie.strip():
            lines.append(f"Jego słowa do siebie: „{_clip(self.zdanie_dla_siebie)}”")
        lines.append(
            "To wstępny obraz człowieka, z którym pracujesz. Nie cytuj go wprost ani "
            "nie streszczaj — pozwól mu zabarwić Twoją perspektywę."
        )
        out = "\n".join(lines)
        return out if len(out) <= _MAX_CONTEXT_CHARS else out[: _MAX_CONTEXT_CHARS - 1].rstrip() + "…"


# ── ContextVar wstrzykiwania (task-scoped, jak db.tenant) ────────────────────

current_obraz_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_obraz_context", default=None
)


def set_obraz_context(value: Optional[str]) -> None:
    current_obraz_context.set(value or None)


def get_obraz_context() -> Optional[str]:
    return current_obraz_context.get()


# ── Materiał + dystylacja ────────────────────────────────────────────────────


def _answers_by_section(answers: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Grupuje odpowiedzi wg sekcji onboardingu (SEKCJE)."""
    out: dict[str, list[str]] = {}
    for a in answers:
        try:
            idx = int(a.get("question_idx", -1))
        except (TypeError, ValueError):
            continue
        ans = (a.get("answer") or "").strip()
        if not ans or idx < 0 or idx >= len(SEKCJE):
            continue
        out.setdefault(SEKCJE[idx], []).append(ans)
    return out


# Indeksy dwóch pytań „Ciszy" rozwiązane po treści (odporne na reorder).
def _resolve_idx(text: str) -> int:
    try:
        return PYTANIA.index(text)
    except ValueError:  # pragma: no cover
        return -1


_IDX_POTRZEBA = _resolve_idx("Czego najbardziej potrzebujesz w tym tygodniu?")
_IDX_ZDANIE = _resolve_idx("Jakie jedno zdanie chciałbyś usłyszeć od siebie sprzed roku?")


def _fallback_obraz(answers: list[dict[str, Any]]) -> ObrazUzytkownika:
    """Deterministyczny destylat bez LLM — czyste KOPIOWANIE odpowiedzi do pól
    wg sekcji (zero inferencji). Offline-safe i zgodny z zasadą zero dopowiadania.

    Dwa pola „Ciszy" mapowane po KONKRETNYM pytaniu (nie po pozycji), żeby
    częściowe odpowiedzi nie przesuwały cytatu do złego pola."""
    by = _answers_by_section(answers)
    by_idx: dict[int, str] = {}
    for a in answers:
        try:
            i = int(a.get("question_idx", -1))
        except (TypeError, ValueError):
            continue
        ans = (a.get("answer") or "").strip()
        if ans and i >= 0:
            by_idx[i] = ans
    return ObrazUzytkownika(
        wartosci=by.get("Wartości", []),
        napiecia=by.get("Cień", []) + by.get("Domknięcie", []),
        relacje=by.get("Relacje", []),
        wzorce=by.get("Historia", []),
        cialo=" / ".join(by.get("Ciało", [])),
        kreatywnosc=" / ".join(by.get("Kreatywność", [])),
        duchowosc=" / ".join(by.get("Duchowość", [])),
        potrzeba_teraz=by_idx.get(_IDX_POTRZEBA, ""),
        zdanie_dla_siebie=by_idx.get(_IDX_ZDANIE, ""),
    )


def _format_material(answers: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for a in sorted(answers, key=lambda x: int(x.get("question_idx", 0))):
        try:
            idx = int(a.get("question_idx", -1))
        except (TypeError, ValueError):
            continue
        ans = (a.get("answer") or "").strip()
        if not ans or idx < 0 or idx >= len(PYTANIA):
            continue
        parts.append(f"[{SEKCJE[idx]}] {PYTANIA[idx]}\n→ {ans}")
    return "\n\n".join(parts)


_OBRAZ_SYSTEM_PROMPT = (
    "Jesteś cichym dystylatorem Obrazu Użytkownika w systemie Architekt Wolności. "
    "Twoja JEDYNA rola: złożyć odpowiedzi z onboardingu w zwięzły, ustrukturyzowany "
    "obraz człowieka. NIE jesteś głosem Rady, nie doradzasz, nie oceniasz.\n\n"
    "Zwróć WYŁĄCZNIE poprawny JSON (bez markdown, bez komentarzy) o polach:\n"
    "  wartosci: string[]      — na co się nie zgodzi / czego pragnie\n"
    "  napiecia: string[]      — cień, tłumione impulsy, niedomknięcia\n"
    "  relacje: string[]       — bliskość, kogo zna naprawdę, czego nie powiedział\n"
    "  wzorce: string[]        — powtarzające się pętle (zwł. z dzieciństwa)\n"
    "  cialo: string           — gdzie trzyma napięcie / fizyczna radość\n"
    "  kreatywnosc: string     — co tworzy, zwł. bez widowni\n"
    "  duchowosc: string       — pokora, przynależność do większego\n"
    "  potrzeba_teraz: string  — czego potrzebuje w najbliższym tygodniu\n"
    "  zdanie_dla_siebie: string — DOSŁOWNY cytat użytkownika (nie parafrazuj!)\n\n"
    "ZASADY BEZWZGLĘDNE:\n"
    "• ZERO dopowiadania: jeśli materiał nie pokrywa wymiaru — zostaw pole puste "
    "(\"\" lub []). Nie zmyślaj, nie generalizuj ponad słowa użytkownika.\n"
    "• Streszczaj wiernie, krótko, w 1. osobie obrazu (nie cytuj pytań).\n"
    "• `zdanie_dla_siebie` przepisz znak w znak z odpowiedzi — to kotwica."
)


async def adistill_obraz(
    answers: list[dict[str, Any]],
    *,
    model: Optional[str] = None,
    max_tokens: int = 1200,
    temperature: float = 0.3,
    wersja: int = 1,
) -> ObrazUzytkownika:
    """Destyluje odpowiedzi onboardingowe w `ObrazUzytkownika`.

    Brak materiału → pusty obraz. Brak LLM / błąd → deterministyczny fallback
    (czyste kopiowanie wg sekcji, zero inferencji)."""
    material = _format_material(answers)
    if not material.strip():
        return ObrazUzytkownika(wersja=wersja)

    backend = effective_llm_backend()
    if backend == "none":
        obraz = _fallback_obraz(answers)
        obraz.wersja = wersja
        return obraz

    model_name = model or os.getenv("MODEL_SONNET", "claude-sonnet-5")
    user_content = (
        "Odpowiedzi onboardingowe Patryka — zdestyluj w JSON wg schematu.\n"
        "---\n" + material + "\n---\nZwróć WYŁĄCZNIE JSON."
    )

    def _from_payload(payload: dict[str, Any]) -> ObrazUzytkownika:
        allowed = ObrazUzytkownika.model_fields.keys()
        clean = {k: v for k, v in payload.items() if k in allowed and k not in ("wersja", "zrodlo")}
        obraz = ObrazUzytkownika(**clean)
        obraz.wersja = wersja
        return obraz

    try:
        if backend == "xai":
            xm = map_claude_model_to_xai(model_name)
            text, _, _ = await asyncio.wait_for(
                xai_chat_completion(
                    system=_OBRAZ_SYSTEM_PROMPT, user=user_content,
                    model=xm, max_tokens=max_tokens, temperature=temperature,
                ),
                timeout=float(DREAM_TIMEOUT_WAIT_SEC),
            )
            return _from_payload(_parse_llm_json_object(text))

        if backend == "ollama":
            om = map_claude_model_to_ollama(model_name)
            text, _, _ = await asyncio.wait_for(
                ollama_chat_completion(
                    system=_OBRAZ_SYSTEM_PROMPT, user=user_content,
                    model=om, max_tokens=max_tokens, temperature=temperature,
                ),
                timeout=float(DREAM_TIMEOUT_WAIT_SEC),
            )
            return _from_payload(_parse_llm_json_object(text))

        from anthropic import AsyncAnthropic  # type: ignore

        ak = anthropic_api_key()
        if not ak:
            obraz = _fallback_obraz(answers)
            obraz.wersja = wersja
            return obraz
        client = AsyncAnthropic(api_key=ak, timeout=float(LLM_TIMEOUT_SDK_SEC))
        create_kw: dict[str, Any] = {
            "model": model_name, "max_tokens": max_tokens,
            "system": _OBRAZ_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_content}],
        }
        if not anthropic_omits_temperature(model_name):
            create_kw["temperature"] = temperature
        _thinking = anthropic_thinking_config(model_name)
        if _thinking is not None:
            create_kw["thinking"] = _thinking
        msg = await asyncio.wait_for(
            client.messages.create(**create_kw), timeout=float(DREAM_TIMEOUT_WAIT_SEC)
        )
        from shared.utils.llm import extract_message_text

        return _from_payload(_parse_llm_json_object(extract_message_text(msg)))
    except Exception as e:  # noqa: BLE001
        logger.warning("adistill_obraz: błąd LLM (%s) — fallback deterministyczny.", e)
        obraz = _fallback_obraz(answers)
        obraz.wersja = wersja
        return obraz
