# PRD — Architekt Wolności v3.3

**Wersja:** 3.3.0  
**Data:** 2026-05-18  
**Autor:** Patryk (na podstawie rzeczywistego kodu; wygenerowane przez Radę)  
**Status:** Wdrożony — wszystkie fazy 0–5 ukończone

---

## Problem Statement

Patryk (i docelowo inni właściciele firm i osoby budujące świadomie życie) podejmuje decyzje, projekty i marzenia w warunkach wewnętrznych sprzeczności: logika mówi jedno, emocje drugie, ciało — jeszcze inne. Klasyczne narzędzia (notatniki, coaching, AI chatboty) dają jedną perspektywę lub uśredniony konsensus, przez co pomijają napięcia, które są sednem problemu. Efekt: projekty są zaczynane i porzucane, decyzje podejmowane ze ślepymi plamkami, a marzenia pozostają na poziomie deklaracji.

Koszt braku rozwiązania: chroniczne niedokańczanie projektów, decyzje spójne z jedną perspektywą (np. tylko racjonalną), utrata energii i zaufania do siebie.

---

## Cele produktu

1. **10 równoległych perspektyw na każdy brief** — każda decyzja, projekt, marzenie lub blokada analizowana jednocześnie przez 9 wyspecjalizowanych agentów + Syez (synteza). Zero groupthink.
2. **Mechaniczne doprowadzanie do końca (AKSJOMAT 2)** — hard-lock przy próbie nowego projektu gdy stare są niedomknięte; commitments z follow-up 72h; brak możliwości cichego porzucenia.
3. **Architektura Marzenia jako punkt startowy (AKSJOMAT 1)** — każda debata poprzedzona destylacją `core_dream`, `value_anchor`, `pillars`, `milestones`, `next_move` ≤60 min.
4. **Koszt debaty < 0.60 USD** w trybie pełnym (hybryda Haiku / Sonnet / Opus), < 0.10 USD w trybie codziennym.
5. **Kompletna historia i ciągłość** — każda debata zapisana, wyszukiwalna, eksportowalna (MD + PDF), z możliwością kontynuacji wątku.
6. **Multi-user z izolacją danych** — JWT HS256, `tenant_id` na każdej tabeli, kompatybilność wsteczna (brak JWT → tenant `default`).

---

## Non-Goals (v3.3)

| Non-Goal | Uzasadnienie |
|----------|-------------|
| Pełna persystencja na Postgres | SQLite wystarcza dla 1–50 użytkowników; Postgres gotowe jako alternatywa przez `DATABASE_URL` |
| Coaching w czasie rzeczywistym / video | Poza scope'em — Architekt to system tekstowych briefów i syntezy, nie sesji live |
| Marketplace agentów / otwarta platforma | System jest intencjonalnie zamknięty — agenci mają ustalone osobowości; otwartość rozmyłaby filozofię |
| Mobile-first native app | Tauri zapewnia natywność na desktop; PWA (service worker) obsługuje mobilny dostęp offline |
| Automatyczna integracja z LLM innych niż Anthropic | xAI (Grok) jest jako alternatywa przez `LLM_BACKEND=xai`; reszta poza scope'em v3.3 |

---

## Architektura produktu

System składa się z dwóch trybów działania montowanych w jednej aplikacji FastAPI:

### Tryb Osobisty — Rada Nadzorcza „Mój Świat"
Główny produkt. 9 agentów + Syez analizuje brief Patryka.

### Tryb Biznesowy — Freedom Architect 2.0 (`/business`)
Zamontowany jako sub-aplikacja pod `/business`. Te same 9 agentów w rolach analityków biznesowych (rynek, monetyzacja, risk, GTM, operacje, benchmarki, innowacja, konkurencja, demand validation).

---

## Skład Rady Nadzorczej

| Agent | Emoji | Rola | Model | Temp |
|-------|-------|------|-------|------|
| **Syez** | 🌌 | Synteza (orchestrator) — lustro Rady | Claude Sonnet 4.6 | 0.5 |
| **Szow** | ⚫ | Cień Jungowski — mówi to, czego Patryk woli nie słyszeć | Claude Sonnet 4.6 | 1.0 |
| **Kogit** | 🧠 | Architekt Logiki i Struktury | Claude Sonnet 4.6 | 0.7 |
| **Tai** | 🟠 | Czasowy — pamięć i wizja | Claude Sonnet 4.6 | 0.6 |
| **Deega** | 🔴 | Głęboka Diagnoza (nieuświadomione wzorce) | Claude Sonnet 4.6 | 0.0 |
| **Relacjan** | 🔵 | Relacyjny — mapuje sieci wpływu | Claude Sonnet 4.6 | 0.8 |
| **Emojy** | 🟡 | Emocjonalny — wczuwa się w stan pre-werbalny | Claude Sonnet 4.6 | 0.8 |
| **Obver** | 🔷 | Obserwator zewnętrzny — meta-perspektywa | Claude Sonnet 4.6 | 0.8 |
| **Kidi** | 🧸 | Dziecięca Ciekawość — instynkt i fascynacja | Claude Sonnet 4.6 | 1.0 |
| **Smaty** | 🟤 | Somatyczny — sygnały ciała | Claude Sonnet 4.6 | 1.0 |

---

## Flow debaty (SSE pipeline)

```
Brief → Walidacja (kategoria + hard-lock projektów) → 
  [Faza A0] DreamArchitect → SSE: dream_architecture →
  [Faza 1]  9 agentów równolegle → SSE: agent_chunk × N → agent_done × 9 →
  [Faza 1b] LiveTensions (heurystyka leksykalna napięć między parami) → SSE: live_tensions →
  [Faza 2]  Syez synteza + walidacja audytu domknięcia → SSE: synthesis_chunk →
  [Faza 2b] Re-prompt naprawczy (max 1x, jeśli brak audytu AKSJOMAT 2) →
            SSE: synthesis_done → debate_done (z debate_id, cost_usd)
```

### Faza A0 — Architektura Marzenia (AKSJOMAT 1)
Z briefu destylowane są:
- `core_dream` — co naprawdę chcesz
- `value_anchor` — kotwica wartości
- `pillars` — 3–5 filarów
- `milestones` — kamienie milowe z datami
- `next_move` — najmniejszy konkretny ruch (≤60 min)
- `functionality_checklist` — lista odhaczalnych funkcjonalności (źródło prawdy dla AKSJOMATU 2)

W trybie `codzienny` faza A0 jest uproszczona (bez LLM — `_fallback_dream`) dla oszczędności kosztu.

---

## Tryby działania

| Tryb | Agenci | Opis |
|------|--------|------|
| `pelna` | 9 + Syez | Standardowa pełna Rada |
| `marzen` | 9 + Syez | Wzmocniona Faza A0, ekspansja wizji przed kompresją |
| `schematy` | 9 + Syez | Agresywne przełamywanie blokad; obowiązkowe `Dziś zrobię...`; auto-commitment 72h |
| `codzienny` | 4 + Syez | Check-in ~5 min (Kogit, Emojy, Smaty, Obver); tańsze max_tokens |

**Kategorie briefu:** `decyzja` / `projekt` / `marzenie` / `schemat`

---

## User Stories

### Persona: Patryk (właściciel, użytkownik główny)

**Decyzje i marzenia**
- Jako Patryk, chcę wysłać brief (min. 20 znaków, min. 5 słów) i dostać 9 równoległych perspektyw w czasie rzeczywistym (SSE), żeby nie podejmować decyzji ze ślepą plamką jednej perspektywy.
- Jako Patryk, chcę żeby każda debata zaczynała się od destylacji marzenia (DreamArchitect), żeby agenci mieli wspólny kompas przed analizą.
- Jako Patryk, chcę żeby Szow mówił bez cenzury to, czego inni agenci milczą — włącznie z tym, co ukrywam sam przed sobą.
- Jako Patryk, chcę żeby Syez był tylko lustrem 9 głosów (nie dodawał własnej perspektywy), żeby synteza była integracją a nie kolejną opinią.

**Projekty i doprowadzanie do końca**
- Jako Patryk, chcę żeby system blokował mi nowy projekt (HTTP 409), gdy mam aktywne niedomknięte projekty, żeby przestać zaczynać zamiast kończyć.
- Jako Patryk, chcę odznaczać elementy functionality_checklist (z opcjonalnym dowodem URL), żeby mieć mierzalny postęp projektu.
- Jako Patryk, chcę żeby projekt nie dał się zamknąć jako COMPLETED, gdy checklist nie jest 100% (HTTP 422 z listą zaległości).
- Jako Patryk, chcę archiwizować projekt świadomie (z uzasadnieniem ≥50 znaków) zamiast po cichu go porzucać — DELETE jest celowo zablokowany (HTTP 422).
- Jako Patryk, chcę żeby tryb `schematy` automatycznie tworzył commitment z follow-up 72h, żeby przełamywanie wzorców miało mechanizm egzekucji.
- Jako Patryk, chcę żeby przeterminowane follow-upy dokleiły prefix głosu Szowa/Deegi (konfrontacja, nie przypomnienie), żeby nie dało się milczeć.

**Historia i eksport**
- Jako Patryk, chcę przeszukiwać historię debat (full-text po briefie, syntezie i głosach), żeby wracać do wcześniejszych analiz.
- Jako Patryk, chcę eksportować debatę do Markdown lub PDF (UTF-8, DejaVu font), żeby mieć offline lub drukowany zapis.
- Jako Patryk, chcę kontynuować wątek debaty (kontekst poprzednich głosów + syntezy), żeby pogłębiać temat zamiast zaczynać od zera.

**Personalizacja**
- Jako Patryk, chcę żeby agenci uczyli się z moich poprzednich debat (rolling notatka ewolucyjna per agent), żeby kolejne debaty były bardziej trafione.
- Jako Patryk, chcę dodać brief głosem (ciągłe nagrywanie Web Speech API + fallback Whisper), żeby nie musieć pisać gdy myślę głośno.

**Dostęp i prywatność**
- Jako Patryk, chcę żeby moje debaty były izolowane od innych użytkowników (tenant_id + JWT), żeby dane były prywatne.
- Jako Patryk, chcę żeby aplikacja działała offline (service worker + kolejkowanie briefów), żeby nie tracić dostępu bez internetu.

### Persona: Drugi użytkownik (multi-user, Faza 4+)
- Jako nowy użytkownik, chcę zarejestrować konto (pbkdf2, JWT HS256) i mieć swoją izolowaną historię debat.
- Jako użytkownik, chcę żeby moje dane nie były widoczne dla innych, nawet jeśli korzystamy z tego samego backendu.

---

## Wymagania — Must-Have (P0)

Wszystkie poniższe są **wdrożone w v3.3**.

| Wymaganie | Kryterium akceptacji |
|-----------|---------------------|
| SSE streaming debaty | `dream_architecture → agent_voice ×9 → live_tensions → synthesis_chunk → debate_done` w czasie rzeczywistym |
| AKSJOMAT 1 — DreamArchitect | Każda debata (poza `codzienny`) zaczyna się od destylacji marzenia przez LLM |
| AKSJOMAT 2 — hard-lock projektów | `category=projekt` + ≥MAX_ACTIVE_PROJECTS aktywnych → HTTP 409 z listą blokujących |
| AKSJOMAT 2 — audyt domknięcia w syntezie | Syez musi zawrzeć audyt w prozie; brak → 1 re-prompt; nadal brak → SSE `completion_audit_violation` |
| AKSJOMAT 2 — commitments z follow-up | INSERT commitment z follow_up_at; tryb `schematy` → auto 72h; DELETE → HTTP 422 |
| Hybrydowe modele LLM | Opus (Syez, Szow), Sonnet (5 agentów), Haiku (Kidi, Smaty); override przez ENV |
| Retry z backoffem | tenacity, 5 prób, exp backoff + jitter 1–30s; tylko na RateLimitError + APIConnectionError |
| Cache Redis | SHA256(context[:400] + model + temp + dream_id + language + mode), TTL 3600s |
| Cost log | Append-only `data/cost_log.jsonl`; DAILY_COST_LIMIT_USD → HTTP 402 |
| Historia + wyszukiwanie | `GET /history?q=` full-text, limit 1–200 |
| Eksport MD + PDF | `/debate/{id}/export.md` i `.pdf`, UTF-8, DejaVu font |
| Multi-user + JWT | `tenant_id` per tabela, middleware JWT HS256, rejestracja + login |
| Rate limiting | slowapi, per-IP na POST `/debate/stream`; wyłącznik `AW_DISABLE_RATE_LIMIT` |
| Auth (produkcja) | JWT / BFF / legacy Bearer; admin endpoints wymagają `ARCHITEKT_ADMIN_TOKEN` |
| Tryb biznesowy FA2 | 9 agentów w rolach analityków biznesowych, sub-app pod `/business` |

---

## Wymagania — Nice-to-Have (P1)

| Wymaganie | Status |
|-----------|--------|
| Agent evolution (rolling notatka per agent) | ✅ wdrożone (`core/agent_learner.py`) |
| Tryb Marzeń — DreamWizard multi-step | ✅ wdrożone (`DreamWizard.tsx`) |
| NotificationsPanel z browser Notification API | ✅ wdrożone |
| Integracje: Notion / Todoist / Google Calendar | ✅ wdrożone (status + export endpoints) |
| Voice input — Web Speech API + Whisper | ✅ wdrożone |
| Offline-first — service worker + queue | ✅ wdrożone |
| LiveTensions — heurystyka leksykalna | ✅ wdrożone (`core/live_tensions.py`) |
| Continuacja wątku debaty | ✅ wdrożone (`POST /debate/continue/stream`) |
| Tryb FA2 z oddzielnymi rolami biznesowymi | ✅ wdrożone |

---

## Wymagania — Future (P2)

| Wymaganie | Uzasadnienie |
|-----------|-------------|
| Pełna migracja do Postgres w prod | SQLite wystarczy do ~50 użytkowników; `DATABASE_URL` gotowe |
| Rozbicie `main.py` na routers | SSE/debate nadal w monolicie; `api/routers/debate.py` do zrobienia |
| Synchroniczny `_log_cost` → async | Blokuje event loop pod obciążeniem; niskopriorytetowe przy obecnej skali |
| Marketplace agentów / custom personas | Wymaga rearchitektury filozofii produktu — celowo poza scope'em |
| Billing i monetyzacja SaaS | Plik `docs/FOUNDERS_OFFER.md` — model BYOK (Bring Your Own Key); Stripe do dodania |

---

## Sukces — metryki

### Wskaźniki wiodące (zmiana w dniach od debaty)
| Metryka | Cel |
|---------|-----|
| Czas do pierwszej syntezy (pełny tryb) | < 35s (Opus cold start) |
| Koszt debaty — tryb `pelna` | < 0.60 USD |
| Koszt debaty — tryb `codzienny` | < 0.10 USD |
| Cache hit rate | > 20% (powtarzalne briefs) |
| Odsetek debat z commitment | > 50% w trybie `schematy` |

### Wskaźniki opóźnione (zmiana w tygodniach)
| Metryka | Cel |
|---------|-----|
| % projektów z completion_ratio = 1.0 | > 60% z aktywnych |
| % commitments z `status=completed` (nie `released`) | > 70% |
| Średni `days_since_progress` w aktywnych projektach | < 7 dni |
| Subiektywna ocena syntezy (skala 1–10) | > 8/10 |

---

## API — pełna lista endpointów

### Debata
| Method | Path | Opis |
|--------|------|------|
| POST | `/debate/stream` | Główna debata SSE |
| POST | `/debate/continue/stream` | Kontynuacja wątku |
| GET | `/history` | Historia debat (limit 1–200, `?q=` search) |
| GET | `/debate/{id}` | Szczegóły debaty |
| GET | `/debate/{id}/export.md` | Eksport Markdown |
| GET | `/debate/{id}/export.pdf` | Eksport PDF |

### Commitments
| Method | Path | Opis |
|--------|------|------|
| POST | `/commitment` | Utwórz zobowiązanie |
| GET | `/commitments/due` | Przeterminowane (within_hours ≤8760) |
| PATCH | `/commitment/{id}/complete` | Odznacz jako done |
| POST | `/commitment/{id}/release` | Zwolnij z uzasadnieniem (≥30 znaków) |
| DELETE | `/commitment/{id}` | **Celowo zablokowane — HTTP 422** |

### Dreams + Projects
| Method | Path | Opis |
|--------|------|------|
| GET | `/dreams` | Lista marzeń z projektami |
| GET | `/dreams/{id}` | Szczegóły marzenia |
| GET | `/projects` | Aktywne projekty (completion_ratio, days_since_progress) |
| GET | `/projects/{id}` | Szczegóły projektu |
| GET | `/projects/{id}/commitments` | Oś commitments projektu |
| PATCH | `/projects/{id}/functionality/{item_id}` | Odhacz element checklisty |
| POST | `/projects/{id}/complete` | Zamknij (wymaga 100% checklist) |
| POST | `/projects/{id}/archive` | Archiwizuj świadomie (uzasadnienie ≥50 znaków) |

### Admin + Meta
| Method | Path | Opis |
|--------|------|------|
| POST | `/admin/trigger-followups` | Ręczny wyzwalacz Fazy 2 (wymaga Bearer token) |
| POST | `/admin/rebuild-evolution` | Przebuduj rolling notatki agentów |
| GET | `/health` | Liveness |
| GET | `/health/ready` | Readiness (DB ping) |
| GET | `/edition` | Lista dostępnych trybów (personal + business) |

### Auth + Voice + Integrations
| Method | Path | Opis |
|--------|------|------|
| POST | `/auth/register` | Rejestracja (pbkdf2, JWT) |
| POST | `/auth/login` | Login → JWT |
| POST | `/voice/transcribe` | Transkrypcja audio (Whisper) |
| GET | `/integrations/status` | Status konfiguracji Notion/Todoist/GCal |

---

## Stack techniczny

| Warstwa | Technologia |
|---------|-------------|
| Backend | Python 3.10+ + FastAPI (async) |
| LLM | Anthropic SDK (`AsyncAnthropic`), model: `claude-sonnet-4-6` (wszyscy agenci); fallback xAI Grok |
| Cache | Redis asyncio, TTL 3600s |
| DB | aiosqlite (SQLite) → Postgres przez `DATABASE_URL` |
| Retry | tenacity, 5 prób, exp backoff |
| Streaming | SSE (`StreamingResponse`) |
| Rate limit | slowapi |
| Frontend | Tauri + React 19 + Vite + Tailwind CSS |
| PDF export | DejaVuSans (wbudowany font UTF-8) |
| Auth | JWT HS256 (PyJWT), pbkdf2 haseł |
| Voice | Web Speech API (ciągłe) + OpenAI Whisper fallback |
| Offline | Service Worker (`public/sw.js`) + localStorage queue |
| Deployment | Docker + docker-compose; Dockerfile w repo |

---

## Znane ograniczenia (v3.3)

1. `_log_cost` — synchroniczny `open()` blokuje event loop pod wysokim obciążeniem
2. 10 bezpośrednich `aiosqlite.connect()` w generatorach SSE (poza `Depends(get_db)`)
3. `main.py` — SSE/debate nadal jako monolit; planowany router `api/routers/debate.py`
4. Klucz API w przeglądarce (`VITE_ARCHITEKT_API_KEY` / localStorage) — niezalecane w prod; preferuj BFF + JWT

---

## Pytania otwarte

| Pytanie | Owner | Priorytet |
|---------|-------|-----------|
| Kiedy migracja do Postgres staje się konieczna? (ilu userów / ile debat dziennie) | Patryk | Nieblokujące |
| Model monetyzacji: BYOK + one-time fee vs. SaaS subskrypcja? | Patryk (+ prawnik) | Blokujące przy launch publicznym |
| Czy `business_fa2` powinien być osobnym produktem z osobnym brandingiem? | Patryk | Strategiczne |
| Czy agent evolution notes powinny być widoczne dla użytkownika w UI? | Design | P1 |
| Telemetria (usage analytics) — opt-in model do zdefiniowania przed publicznym launchem | Prawnik + Patryk | Blokujące |

---

## Roadmap — status

| Faza | Zakres | Status |
|------|--------|--------|
| **Faza 0** | MVP: orkiestracja 9+Syez, SSE, SQLite, eksport MD/PDF | ✅ |
| **Faza 1** | Redis cache, agent_evolution, historia + wyszukiwanie, TensionMeter | ✅ |
| **Faza 2** | Tryb `schematy`, commitments 72h, AKSJOMAT 2, NotificationsPanel | ✅ |
| **Faza 3** | Personalizacja agentów, `core/agent_learner.py`, rolling notatki | ✅ |
| **Faza 4** | Multi-user, JWT, UI logowania, izolacja `tenant_id`, Postgres alternatywa | ✅ |
| **Faza 5** | Notion/Todoist/GCal, voice (Web Speech + Whisper), offline-first (SW) | ✅ |
| **Faza 6** | Refaktoryzacja `main.py`, async cost log, pełny Postgres w prod | 🔴 planowane |

---

## Filozofia produktu (niezmienne)

Architekt Wolności nie jest kolejnym chatbotem. Jego przewaga to **struktura napięcia** — 9 perspektyw celowo wybranych tak, żeby wchodziły w konflikt (Kogit vs Emojy, Szow vs Kidi, Deega vs Obver). Syez nie łagodzi tych napięć — wskazuje na nie i zadaje pytania otwarte. Użytkownik dostaje zwierciadło, które nie kłamie.

Dwa AKSJOMATY (Architektura Marzenia + Doprowadzanie Do Końca) są nieusuwalne z kodu — nie przez framework, ale przez filozofię produktu. DELETE commitment → HTTP 422. Brak audytu domknięcia → re-prompt. Hard-lock aktywnych projektów → HTTP 409. System **nie daje się obejść po cichu**.

---

*Wygenerowane na podstawie kodu v3.3 — `main.py`, `agents/`, `core/`, `db/schema.sql`, `ui/src/App.tsx`, `docs/spec/SPEC_CURRENT.md`.*
