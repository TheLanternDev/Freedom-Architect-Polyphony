"""
AKSJOMAT 1 — Architektura Marzenia.

Pierwotny sens Architekta Wolności: tworzenie architektury do spełniania marzeń.
Każde zapytanie do Rady — niezależnie od kategorii — przechodzi przez tę warstwę.
Wynikiem jest `DreamArchitecture` — 5-warstwowy szkielet:

    Wizja (core_dream)
      → Kotwica wartości (value_anchor)
        → Filary (pillars)
          → Kamienie milowe (milestones)
            → Najbliższy ruch (next_move)
              → Kryteria spełnienia + Lista funkcjonalności (AKSJOMAT 2)

Moduł jest świadomie odporny na brak LLM: `distill_dream` ma deterministyczny
fallback, żeby system działał offline (np. w testach albo bez ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from config.llm_providers import (
    DREAM_TIMEOUT_WAIT_SEC,
    LLM_TIMEOUT_SDK_SEC,
    anthropic_api_key,
    anthropic_omits_temperature,
    effective_llm_backend,
    map_claude_model_to_ollama,
    map_claude_model_to_xai,
    ollama_chat_completion,
    xai_chat_completion,
)

logger = logging.getLogger(__name__)


# ── Modele ──────────────────────────────────────────────────────────────────


class Milestone(BaseModel):
    """Jeden kamień milowy w drodze do spełnienia marzenia."""

    title: str = Field(..., min_length=3, max_length=140)
    due: Optional[str] = Field(
        default=None,
        description="ISO-8601 date (YYYY-MM-DD) — jeśli znana.",
    )
    why_it_matters: str = Field(
        default="",
        description="Dlaczego ten kamień przybliża do core_dream.",
    )

    @field_validator("due")
    @classmethod
    def _validate_due(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        try:
            date.fromisoformat(v)
        except ValueError as e:
            raise ValueError(f"Milestone.due musi być YYYY-MM-DD, dostałem: {v!r}") from e
        return v


class NextMove(BaseModel):
    """Najbliższy konkretny krok (24–72h)."""

    action: str = Field(..., min_length=5, max_length=280)
    when: str = Field(..., min_length=3, max_length=80)  # np. "dziś wieczorem", "do piątku 18:00"
    smallest_form: str = Field(
        default="",
        description="Najmniejsza możliwa forma tego ruchu, gdyby nawet 30 minut wydawało się dużo.",
    )


class Fragment(BaseModel):
    """AKSJOMAT 0 — Filozofia Fragmentu (Uśmiech ↔ Perspektywa ↔ Droga).

    NAJBARDZIEJ FUNDAMENTALNA warstwa systemu — głębsza i NADRZĘDNA względem
    AKSJOMATU 1 (Architektura Marzenia) i AKSJOMATU 2 (Domknięcie). Tamte dwa
    są narzędziami SŁUŻĄCYMI temu żywemu, samopodtrzymującemu się układowi —
    nigdy odwrotnie.

    Trzy elementy tworzą symetryczny system (kompas, nie mapa):
      • Uśmiech     — postawa ciekawości skierowanej w siebie.
      • Perspektywa — „jak patrzeć” zamiast „gdzie dojść”; nieskończona.
      • Droga       — codzienne, rzeczywiste poruszanie się.

    Na tym etapie pola przechowują stan w prostej formie tekstowej (szkielet).
    Świadomie NIE budujemy tu zaawansowanego zarządzania stanem — struktura ma
    być solidna i rozszerzalna (np. pod Daily Signal), nie rozbudowana.
    """

    usmiech: str = Field(default="", description="Aktualna postawa Uśmiechu (ciekawość ku sobie).")
    perspektywa: str = Field(default="", description="Aktualny kierunek patrzenia (nie cel docelowy).")
    droga: str = Field(default="", description="Co realnie podtrzymuje ruch na co dzień.")

    def update(
        self,
        *,
        usmiech: Optional[str] = None,
        perspektywa: Optional[str] = None,
        droga: Optional[str] = None,
    ) -> "Fragment":
        """Prosta, świadoma aktualizacja stanu trzech elementów. Zwraca self."""
        if usmiech is not None:
            self.usmiech = usmiech.strip()
        if perspektywa is not None:
            self.perspektywa = perspektywa.strip()
        if droga is not None:
            self.droga = droga.strip()
        return self

    def weakest_element(self) -> str:
        """Zwraca etykietę elementu z najsłabszym lub pustym stanem ('Uśmiech', 'Perspektywa' lub 'Droga')."""
        elementy = (
            ("Uśmiech", self.usmiech),
            ("Perspektywa", self.perspektywa),
            ("Droga", self.droga),
        )
        # Puste pole jest zawsze najsłabsze; przy remisie wygrywa kolejność
        # Uśmiech → Perspektywa → Droga. Bez pustych: najkrótszy (najmniej nazwany).
        return min(elementy, key=lambda e: len(e[1].strip()))[0]

    def get_fragment_context(self) -> str:
        """Sformatowany nagłówek AKSJOMATU 0 — najwyższy filtr dla Rady i Syeza.

        Frame trzech elementów renderuje się ZAWSZE (sama filozofia jest
        wartością); stan wpisywany jest tam, gdzie został nazwany. Puste pole =
        szkielet do nazwania, nie błąd.
        """

        def _line(label: str, val: str, hint: str) -> str:
            v = (val or "").strip()
            return f"  • {label}: {v}" if v else f"  • {label}: (do nazwania — {hint})"

        return (
            "═══ AKSJOMAT 0 — FILOZOFIA FRAGMENTU (FILTR NAJWYŻSZY) ═══\n"
            "Warstwa NADRZĘDNA względem Architektury Marzenia (AKSJOMAT 1) i\n"
            "Domknięcia (AKSJOMAT 2). Nie „cel → osiągnięcie → pustka”, lecz żywy,\n"
            "samopodtrzymujący się układ trzech elementów (kompas, nie mapa):\n"
            + _line("Uśmiech", self.usmiech, "ciekawość ku sobie: „ciekawe, jak sobie z tym poradzę”")
            + "\n"
            + _line("Perspektywa", self.perspektywa, "jak patrzeć, nie gdzie dojść — perspektywa jest nieskończona")
            + "\n"
            + _line("Droga", self.droga, "co realnie podtrzymuje codzienny ruch")
            + "\n"
            "Każda obserwacja i sugestia ma najpierw służyć utrzymaniu tego układu\n"
            "przy życiu — dopiero potem marzeniu i domknięciu.\n"
            "══════════════════════════════════════════════════════════════════\n"
            f"Element wymagający uwagi dziś: {self.weakest_element()}"
        )


class DreamArchitecture(BaseModel):
    """Pełen szkielet marzenia stojącego za briefem Patryka.

    Uwaga hierarchii: pole `fragment` (AKSJOMAT 0) jest warstwą NADRZĘDNĄ wobec
    samej Architektury Marzenia (AKSJOMAT 1). Marzenie i domknięcie służą
    utrzymaniu żywego układu Uśmiech ↔ Perspektywa ↔ Droga, nie odwrotnie.
    """

    fragment: Fragment = Field(
        default_factory=Fragment,
        description="AKSJOMAT 0 — filtr najwyższy (Uśmiech ↔ Perspektywa ↔ Droga).",
    )

    dream_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_brief: str = Field(..., min_length=1)
    core_dream: str = Field(..., min_length=5, description="Jedno zdanie: o co tu naprawdę chodzi.")
    value_anchor: str = Field(..., min_length=5, description="Jedno zdanie: dlaczego to ma znaczenie.")
    pillars: list[str] = Field(default_factory=list)
    milestones: list[Milestone] = Field(default_factory=list)
    next_move: NextMove
    completion_criteria: list[str] = Field(
        default_factory=list,
        description="OBOWIĄZKOWE: co musi być spełnione, żeby marzenie było 'spełnione'.",
    )
    functionality_checklist: list[str] = Field(
        default_factory=list,
        description="OBOWIĄZKOWE (AKSJOMAT 2): co musi DZIAŁAĆ, żeby projekt był ukończony.",
    )
    distillation_quality: Literal["llm", "fallback"] = Field(
        default="fallback",
        description="Źródło destylacji: model LLM vs deterministyczny fallback.",
    )
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("pillars")
    @classmethod
    def _validate_pillars(cls, v: list[str]) -> list[str]:
        cleaned = [p.strip() for p in v if p and p.strip()]
        if not (3 <= len(cleaned) <= 7):
            raise ValueError(
                f"DreamArchitecture wymaga 3–7 filarów (pillars), dostałem {len(cleaned)}: {cleaned}"
            )
        return cleaned

    @field_validator("completion_criteria")
    @classmethod
    def _validate_completion_criteria(cls, v: list[str]) -> list[str]:
        cleaned = [c.strip() for c in v if c and c.strip()]
        if len(cleaned) < 1:
            raise ValueError(
                "DreamArchitecture wymaga co najmniej 1 completion_criterion — "
                "bez tego marzenie nie ma definicji spełnienia."
            )
        return cleaned

    @field_validator("functionality_checklist")
    @classmethod
    def _validate_functionality_checklist(cls, v: list[str]) -> list[str]:
        cleaned = [c.strip() for c in v if c and c.strip()]
        if len(cleaned) < 1:
            raise ValueError(
                "AKSJOMAT 2: functionality_checklist nie może być pusty. "
                "Każdy projekt ma co najmniej 1 wymóg funkcjonalny do odhaczenia."
            )
        return cleaned

    # ── Helpers dla orkiestracji ────────────────────────────────────────────

    def as_agent_context(self) -> str:
        """
        Tekstowy nagłówek wstrzykiwany do system promptu KAŻDEGO agenta Rady.
        Agenci mają wiedzieć, JAKIE marzenie wspierają — to wymóg AKSJOMATU 1.

        Hierarchia: blok AKSJOMATU 0 (Filozofia Fragmentu) jest wypisywany
        PRZED Architekturą Marzenia, bo jest wobec niej NADRZĘDNY. Marzenie
        i domknięcie służą utrzymaniu żywego układu Uśmiech ↔ Perspektywa ↔
        Droga, nie odwrotnie.
        """
        milestones_block = "\n".join(
            f"  • {m.title}" + (f" (do: {m.due})" if m.due else "")
            for m in self.milestones[:5]
        ) or "  (brak — Rada ma pomóc je nazwać)"
        return (
            self.fragment.get_fragment_context() + "\n"
            "═══ ARCHITEKTURA MARZENIA (kontekst służący AKSJOMATOWI 0) ═══\n"
            f"Rdzenne marzenie Patryka:\n  → {self.core_dream}\n"
            f"Kotwica wartości:\n  → {self.value_anchor}\n"
            f"Filary spełnienia:\n  • " + "\n  • ".join(self.pillars) + "\n"
            f"Kamienie milowe:\n{milestones_block}\n"
            f"Najbliższy ruch (24–72h):\n  → {self.next_move.action} ({self.next_move.when})\n"
            f"Co musi DZIAŁAĆ żeby uznać to za ukończone (AKSJOMAT 2):\n  • "
            + "\n  • ".join(self.functionality_checklist)
            + "\n══════════════════════════════════════════════════════════════════\n"
            "Twoje 3 zdania mają wspierać tę architekturę, nie ją rozcieńczać."
        )

    def get_fragment_signal_focus(self) -> str:
        """
        Zwraca zwięzłą, wysokosygnałową sugestię opartą na najsłabszym elemencie Fragmentu.
        Sugestia ma pomagać w wyborze zadań na najbliższe 18 godzin.
        """
        f = self.fragment
        if not (f.usmiech.strip() or f.perspektywa.strip() or f.droga.strip()):
            return ""
        sugestie = {
            "Uśmiech": "Na 18h: jedno zadanie podjęte z ciekawością „ciekawe, jak sobie z tym poradzę”, nie z przymusu.",
            "Perspektywa": "Na 18h: jeden ruch, który zmienia kąt patrzenia — nie domykanie kolejnego celu.",
            "Droga": "Na 18h: jeden mały, realny krok podtrzymujący codzienny ruch — bez skoków.",
        }
        return sugestie[f.weakest_element()]

    def for_syez(self) -> str:
        """Pełna serializacja przekazywana Syezowi przed syntezą."""
        return json.dumps(self.model_dump(), ensure_ascii=False, indent=2)


# ── Destylator marzenia (LLM lub fallback) ──────────────────────────────────


DREAM_DISTILLATION_SYSTEM_PROMPT = """Jesteś Architektem Marzenia. Twoja jedyna rola: zamienić surowy brief Patryka
w pełen szkielet marzenia, które stoi pod tym briefem — nawet jeśli brief mówi
o decyzji technicznej, biznesowej albo o blokadzie.

Patryk pracuje w systemie Architekt Wolności — pierwotnym sensem tego systemu
jest tworzenie architektury do spełniania marzeń ORAZ bezwzględne doprowadzanie
projektów do końca w pełni funkcjonalnym stanie.

Zwróć WYŁĄCZNIE poprawny JSON (bez markdown, bez komentarzy) o tym schemacie:

{
  "core_dream": "jedno zdanie: o co tu naprawdę chodzi pod spodem",
  "value_anchor": "jedno zdanie: dlaczego to ma głębsze znaczenie dla Patryka",
  "pillars": ["3 do 5 filarów — od czego zależy spełnienie tego marzenia"],
  "milestones": [
    {"title": "...", "due": "YYYY-MM-DD lub null", "why_it_matters": "..."}
  ],
  "next_move": {
    "action": "najbliższy konkretny ruch w 24–72h",
    "when": "kiedy (np. 'dziś wieczorem', 'do piątku 18:00')",
    "smallest_form": "najmniejsza możliwa forma tego ruchu — wersja 5-minutowa"
  },
  "completion_criteria": ["co musi być spełnione, żeby marzenie było spełnione"],
  "functionality_checklist": [
    "konkretne wymogi DZIAŁANIA — to, co musi działać, żeby projekt był ukończony"
  ]
}

WAŻNE (parsowanie maszynowe):
• Żadnych przecinków po ostatnim elemencie tablicy ani po ostatnim polu obiektu.
• Tylko podwójne cudzysłowy "..." w JSON — bez trailing comma, bez komentarzy // lub /* */.
• Nie dodawaj tekstu przed ani po obiekcie JSON.

ZASADY:
1. functionality_checklist musi być KONKRETNA i SPRAWDZALNA — każda pozycja
   to coś, co da się odhaczyć z dowodem (test przeszedł, użytkownik to widzi,
   przycisk działa, faktura wystawiona). Nie ogólniki.
2. completion_criteria może być bardziej jakościowe (np. „czuję, że to jest moje”),
   ale i tak musi być rozpoznawalne dla Patryka jako spełnione.
3. Nie redukuj marzenia do realizmu zanim je w pełni nazwiesz.
4. Jeśli brief jest o blokadzie / schemacie do przełamania — core_dream nazywa,
   CO leży po drugiej stronie tej blokady. Marzenie ukryte pod blokadą.
5. Trzymaj się polskiego.
"""


DREAM_DISTILLATION_SYSTEM_PROMPT_EN = """You are the Architect of the Dream. Your only role: turn Patryk's raw brief
into a full dream skeleton standing under that brief — even when the brief
talks about a technical decision, business choice, or a blocker.

Patryk works in the Freedom Architect system — the original meaning of this
system is to build the architecture for fulfilling dreams AND to relentlessly
drive projects to a fully functional finish.

Return ONLY valid JSON (no markdown, no comments) with this schema:

{
  "core_dream": "one sentence: what this is really about underneath",
  "value_anchor": "one sentence: why this carries deeper meaning for Patryk",
  "pillars": ["3 to 5 pillars — what fulfilling this dream depends on"],
  "milestones": [
    {"title": "...", "due": "YYYY-MM-DD or null", "why_it_matters": "..."}
  ],
  "next_move": {
    "action": "the next concrete move in 24–72h",
    "when": "when (e.g. 'tonight', 'by Friday 6pm')",
    "smallest_form": "smallest possible form of this move — a 5-minute version"
  },
  "completion_criteria": ["what must be true for the dream to be fulfilled"],
  "functionality_checklist": [
    "concrete WORKING requirements — what must work for the project to be done"
  ]
}

IMPORTANT (machine parsing):
• No trailing commas after the last array element or last object field.
• Only double quotes "..." in JSON — no trailing commas, no // or /* */ comments.
• Do not add text before or after the JSON object.

RULES:
1. functionality_checklist must be CONCRETE and CHECKABLE — every item is
   something one can tick off with proof (a test passes, the user sees it,
   a button works, the invoice is issued). No generalities.
2. completion_criteria can be more qualitative (e.g. "I feel this is mine"),
   but it must still be recognizable to Patryk as fulfilled.
3. Do not shrink the dream into realism before fully naming it.
4. If the brief is about a blocker / pattern to break — core_dream names WHAT
   lies on the other side of that block. The dream hidden under the block.
5. Use English.
"""


def _fallback_dream(raw_brief: str, *, language: str = "pl") -> DreamArchitecture:
    """
    Deterministyczny fallback gdy LLM jest niedostępny.
    Daje minimalny, ale poprawny szkielet — system działa offline.
    """
    short = raw_brief.strip().replace("\n", " ")
    if len(short) > 140:
        short = short[:137] + "..."
    if language == "en":
        return DreamArchitecture(
            raw_brief=raw_brief,
            core_dream=f"Patryk wants to drive this to completion: {short}",
            value_anchor=(
                "The original meaning of Freedom Architect: building the architecture "
                "to fulfill dreams and finishing projects in a fully functional state."
            ),
            pillars=[
                "Clear definition of 'done' (functionality_checklist)",
                "Smallest working increment (smallest functional increment)",
                "A move every week — no 14-day silences",
            ],
            milestones=[
                Milestone(
                    title="First working slice (end-to-end, even if ugly)",
                    due=(date.today() + timedelta(days=7)).isoformat(),
                    why_it_matters="Proof that this can be finished — against the pattern of abandoning things.",
                ),
                Milestone(
                    title="A version another human can use without your help",
                    due=(date.today() + timedelta(days=21)).isoformat(),
                    why_it_matters="Functionality = someone else uses it.",
                ),
            ],
            next_move=NextMove(
                action="Write 5 items from the functionality_checklist and tick off the smallest first",
                when="today, within 60 minutes",
                smallest_form="Open a notebook and write 1 sentence: what 'done' means for this brief.",
            ),
            completion_criteria=[
                "I can honestly say: I did not abandon this — I drove it to completion.",
            ],
            functionality_checklist=[
                "At least 1 working, demonstrable slice exists.",
                "Patryk (or another human) actually uses it in a real scenario.",
                "No open critical blockers (TODO list with 0 P0 items).",
            ],
        )
    return DreamArchitecture(
        raw_brief=raw_brief,
        core_dream=f"Patryk chce doprowadzić do końca: {short}",
        value_anchor=(
            "Pierwotny sens Architekta Wolności: tworzenie architektury do "
            "spełniania marzeń i kończenie projektów w pełni funkcjonalnym stanie."
        ),
        pillars=[
            "Jasna definicja 'skończone' (functionality_checklist)",
            "Najmniejszy działający przyrost (smallest functional increment)",
            "Cotygodniowy ruch — bez 14-dniowych przerw",
        ],
        milestones=[
            Milestone(
                title="Pierwszy działający fragment (end-to-end, choćby brzydki)",
                due=(date.today() + timedelta(days=7)).isoformat(),
                why_it_matters="Dowód, że to da się skończyć — przeciwko schematowi porzucania.",
            ),
            Milestone(
                title="Wersja, którą inny człowiek może użyć bez Twojej pomocy",
                due=(date.today() + timedelta(days=21)).isoformat(),
                why_it_matters="Funkcjonalność = ktoś inny korzysta.",
            ),
        ],
        next_move=NextMove(
            action="Wypisać 5 pozycji z functionality_checklist i odhaczyć pierwszą najmniejszą",
            when="dziś, w ciągu 60 minut",
            smallest_form="Otworzyć notes i zapisać 1 zdanie: co znaczy 'skończone' dla tego briefu.",
        ),
        completion_criteria=[
            "Mogę powiedzieć szczerze: tego nie porzuciłem — doprowadziłem do końca.",
        ],
        functionality_checklist=[
            "Istnieje minimum 1 działający, demonstrowalny fragment.",
            "Patryk (lub inny człowiek) faktycznie z tego korzysta w realnym scenariuszu.",
            "Brak otwartych krytycznych blokerów (lista TODO z 0 pozycjami P0).",
        ],
    )


_DREAM_CACHE: dict[str, DreamArchitecture] = {}


def _tenant_scope() -> str:
    """Granica tenanta dla cache (#4). Fallback 'default' gdy warstwa
    multi-tenant niedostępna (czyste testy domeny / tryb single-user)."""
    try:
        from db.tenant import current_tenant_id
        return current_tenant_id() or "default"
    except Exception:
        return "default"


def _cache_key(raw_brief: str) -> str:
    # Tenant w kluczu — dwóch użytkowników z tym samym briefem NIE współdzieli
    # obiektu marzenia w pamięci procesu (#4).
    return hashlib.sha256(
        f"{_tenant_scope()}:{raw_brief.strip()}".encode("utf-8")
    ).hexdigest()


def _extract_json_block(text: str) -> str:
    """
    Wyciąga pierwszy kompletny obiekt JSON z odpowiedzi LLM.

    Najpierw balansowanie nawiasów w stringach (poprawne przy `}` w treści pól);
    gdy to się nie uda — legacja: pierwszy «{» … ostatni «}» (np. po fence ```json).
    """
    balanced = _balanced_json_object_slice(text)
    if balanced is not None:
        return balanced

    t = text.strip().lstrip("\ufeff")
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Brak prawidłowego bloku JSON w odpowiedzi LLM.")
    return t[start : end + 1]


def _balanced_json_object_slice(text: str) -> Optional[str]:
    """Zwraca substring od pierwszego '{{' do pierwszego zamykającego '}}' na poziomie 0."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    i = start
    while i < len(text):
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        i += 1
    return None


def _strip_trailing_commas_json(s: str) -> str:
    """Usuwa przecinki końcowe tablic/obiektów — powszechny błąd modeli."""
    prev = None
    out = s.strip()
    while out != prev:
        prev = out
        out = re.sub(r",(\s*})", r"\1", out)
        out = re.sub(r",(\s*])", r"\1", out)
    return out


def _parse_llm_json_object(text: str) -> dict[str, Any]:
    """
    Parsuje JSON z odpowiedzi Architekta Marzenia — naprawy typowe dla LLM.

    Raises:
        ValueError: gdy nie da się uzyskać sensownego dict-a (wtedy wyżej: fallback).
        json.JSONDecodeError: rzadko — zwykle owinięte w ValueError.
    """
    raw_block = _extract_json_block(text)
    variants: list[str] = []
    seen: set[str] = set()
    for candidate in (raw_block, _strip_trailing_commas_json(raw_block)):
        if candidate not in seen:
            seen.add(candidate)
            variants.append(candidate)

    last_err: Optional[Exception] = None
    for blob in variants:
        try:
            data = json.loads(blob)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as e:
            last_err = e
            try:
                decoder = json.JSONDecoder()
                obj, _idx = decoder.raw_decode(blob.strip())
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError as e2:
                last_err = e2

    hint = ""
    if last_err is not None:
        hint = f" Ostatni błąd parsera: {last_err}"
    raise ValueError(f"JSON Architekta Marzenia nieparsowalny.{hint}") from last_err


def _inc_dream_distillation_metric(status: str) -> None:
    try:
        from api._metrics import dream_distillation_total

        dream_distillation_total.labels(status=status).inc()
    except Exception:  # pragma: no cover
        pass


def _fallback_after_dream_timeout(
    raw_brief: str,
    *,
    language: str,
    backend: str,
    model_name: str,
) -> DreamArchitecture:
    logger.warning(
        "adistill_dream: TIMEOUT po %ss (%s, model=%s) — fallback (bez cache).",
        DREAM_TIMEOUT_WAIT_SEC,
        backend,
        model_name,
    )
    _inc_dream_distillation_metric("timeout")
    return _fallback_dream(raw_brief, language=language)


def _build_dream_from_payload(raw_brief: str, payload: dict[str, Any]) -> DreamArchitecture:
    """Mapuje dict z LLM-a na DreamArchitecture (z walidacją Pydantic)."""
    return DreamArchitecture(
        raw_brief=raw_brief,
        core_dream=str(payload.get("core_dream", "")).strip(),
        value_anchor=str(payload.get("value_anchor", "")).strip(),
        pillars=list(payload.get("pillars", []) or []),
        milestones=[
            Milestone(**m) if not isinstance(m, Milestone) else m
            for m in (payload.get("milestones", []) or [])
        ],
        next_move=NextMove(**(payload.get("next_move") or {"action": "?", "when": "?"})),
        completion_criteria=list(payload.get("completion_criteria", []) or []),
        functionality_checklist=list(payload.get("functionality_checklist", []) or []),
        distillation_quality="llm",
    )


def distill_dream(raw_brief: str) -> DreamArchitecture:
    """
    Synchronous, deterministic fallback variant — używany w testach
    i jako bezpieczna ścieżka offline.
    """
    if not raw_brief or not raw_brief.strip():
        raise ValueError("distill_dream: pusty brief.")
    key = _cache_key(raw_brief)
    if key in _DREAM_CACHE:
        return _DREAM_CACHE[key]
    dream = _fallback_dream(raw_brief)
    _DREAM_CACHE[key] = dream
    return dream


async def adistill_dream(
    raw_brief: str,
    *,
    model: Optional[str] = None,
    max_tokens: int = 2400,
    temperature: float = 0.4,
    language: str = "pl",
) -> DreamArchitecture:
    """
    Asynchroniczna destylacja marzenia.

    Próbuje wywołać Anthropic albo xAI (OpenAI-compatible), zależnie od
    `LLM_BACKEND` i dostępnych kluczy.
    Jeśli LLM niedostępny / brak klucza → fallback deterministyczny (cache).
    Błąd po wywołaniu API (parsowanie / walidacja) → fallback **bez** cache, żeby
    kolejna próba z tym samym briefem mogła się udać po poprawce lub retry.
    """
    if not raw_brief or not raw_brief.strip():
        raise ValueError("adistill_dream: pusty brief.")

    key = f"{language}:{_cache_key(raw_brief)}"
    if key in _DREAM_CACHE:
        return _DREAM_CACHE[key]

    backend = effective_llm_backend()
    if backend == "none":
        logger.info(
            "adistill_dream: brak LLM (ustaw ANTHROPIC_API_KEY lub XAI_API_KEY w `src/.env`) "
            "— używam fallbacku."
        )
        dream = _fallback_dream(raw_brief, language=language)
        _DREAM_CACHE[key] = dream
        return dream

    model_name = model or os.getenv("MODEL_SONNET", "claude-sonnet-4-6")

    if language == "en":
        system_prompt = DREAM_DISTILLATION_SYSTEM_PROMPT_EN
        user_content = (
            "Patryk's brief — distill it into the full JSON schema.\n"
            "---\n"
            f"{raw_brief.strip()}\n"
            "---\n"
            "Return ONLY the JSON."
        )
    else:
        system_prompt = DREAM_DISTILLATION_SYSTEM_PROMPT
        user_content = (
            "Brief Patryka — zdestyluj w pełen JSON wg schematu.\n"
            "---\n"
            f"{raw_brief.strip()}\n"
            "---\n"
            "Zwróć WYŁĄCZNIE JSON."
        )

    if backend == "xai":
        try:
            xm = map_claude_model_to_xai(model_name)
            text, _, _ = await asyncio.wait_for(
                xai_chat_completion(
                    system=system_prompt,
                    user=user_content,
                    model=xm,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=float(DREAM_TIMEOUT_WAIT_SEC),
            )
            payload = _parse_llm_json_object(text)
            dream = _build_dream_from_payload(raw_brief, payload)
            _DREAM_CACHE[key] = dream
            logger.info("adistill_dream: marzenie zdestylowane (dream_id=%s)", dream.dream_id)
            return dream
        except asyncio.TimeoutError:
            return _fallback_after_dream_timeout(
                raw_brief, language=language, backend="xai", model_name=xm
            )
        except Exception as e:
            logger.warning("adistill_dream: błąd xAI (%s) — fallback (bez cache).", e)
            return _fallback_dream(raw_brief, language=language)

    if backend == "ollama":
        try:
            om = map_claude_model_to_ollama(model_name)
            text, _, _ = await asyncio.wait_for(
                ollama_chat_completion(
                    system=system_prompt,
                    user=user_content,
                    model=om,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=float(DREAM_TIMEOUT_WAIT_SEC),
            )
            payload = _parse_llm_json_object(text)
            dream = _build_dream_from_payload(raw_brief, payload)
            _DREAM_CACHE[key] = dream
            logger.info("adistill_dream: marzenie zdestylowane (dream_id=%s)", dream.dream_id)
            return dream
        except asyncio.TimeoutError:
            return _fallback_after_dream_timeout(
                raw_brief, language=language, backend="ollama", model_name=om
            )
        except Exception as e:
            logger.warning("adistill_dream: błąd Ollama (%s) — fallback (bez cache).", e)
            return _fallback_dream(raw_brief, language=language)

    try:
        from anthropic import AsyncAnthropic  # type: ignore
    except Exception:  # pragma: no cover
        logger.warning("adistill_dream: anthropic SDK niedostępne — fallback.")
        dream = _fallback_dream(raw_brief, language=language)
        _DREAM_CACHE[key] = dream
        return dream

    ak = anthropic_api_key()
    if not ak:
        logger.info("adistill_dream: brak ANTHROPIC_API_KEY — używam fallbacku.")
        dream = _fallback_dream(raw_brief, language=language)
        _DREAM_CACHE[key] = dream
        return dream

    logger.info(
        "adistill_dream: start (model=%s, brief_chars=%d, lang=%s)",
        model_name, len(raw_brief), language,
    )
    try:
        # SDK (AW_LLM_TIMEOUT_SDK) + wait_for belt+suspenders (AW_DREAM_TIMEOUT_WAIT).
        client = AsyncAnthropic(api_key=ak, timeout=float(LLM_TIMEOUT_SDK_SEC))
        create_kw: dict = {
            "model": model_name,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
        }
        if not anthropic_omits_temperature(model_name):
            create_kw["temperature"] = temperature
        msg = await asyncio.wait_for(
            client.messages.create(**create_kw),
            timeout=float(DREAM_TIMEOUT_WAIT_SEC),
        )
        text = msg.content[0].text  # type: ignore[index,union-attr]
        payload = _parse_llm_json_object(text)
        dream = _build_dream_from_payload(raw_brief, payload)
        _DREAM_CACHE[key] = dream
        logger.info("adistill_dream: marzenie zdestylowane (dream_id=%s)", dream.dream_id)
        return dream
    except asyncio.TimeoutError:
        return _fallback_after_dream_timeout(
            raw_brief,
            language=language,
            backend="anthropic",
            model_name=model_name,
        )
    except Exception as e:
        logger.warning(
            "adistill_dream: błąd LLM (%s: %s) — fallback (bez cache).",
            type(e).__name__, e,
        )
        return _fallback_dream(raw_brief, language=language)
