# Architekt Wolności (Freedom Architect: Polyphony) — kompletny opis funkcjonalny

> **Stan:** zgodny z kodem na **2026-06-18**. Wersja API: **3.3.0** (`main.py`, `/health` zwraca `"3.3"`). Baseline bezpieczeństwa: **`CODE_REVIEW_2026-06-16.md`** (4 blokery z 2026-06-02 zamknięte). Strategia produktu: **`docs/roadmap/ROADMAP_2026-06-17.md`**.

---

## 1. Czym jest

Architekt Wolności to **desktopowa aplikacja z wieloperspektywicznym systemem multi-agentowym** — symulacja wewnętrznej Rady Nadzorczej „Mój Świat". Nie jest chatbotem ani asystentem zadaniowym: to dziewięciu wyspecjalizowanych agentów (każdy reprezentuje inną warstwę psychiki/inteligencji) plus **Syez** — syntezator, który nie dodaje własnego głosu, tylko uczciwie konsoliduje to, co Rada powiedziała, ujawniając napięcia i sprzeczności zamiast je wygładzać.

Aplikacja działa lokalnie na maszynie użytkownika (**Tauri 0.1.0** + React 19), z backendem FastAPI (Python). Model dystrybucji docelowy: **pudełko local-first BYOK** — klient ma własny klucz LLM i lokalną bazę; dane debat nie przechodzą przez infrastrukturę operatora. Warstwa multi-tenant/RLS pozostaje w kodzie jako defense-in-depth na przyszły hosting SaaS.

### Filozofia (aksjomaty — egzekwowane w kodzie)

- **AKSJOMAT 0 — Filozofia Fragmentu** (nadrzędny): samopodtrzymujący się układ **Uśmiech ↔ Perspektywa ↔ Droga**. Zaimplementowany w `core/dream_architect.py` (`weakest_element()`, `get_fragment_signal_focus()` — sugestia na 18h).
- **AKSJOMAT 1 — Architektura Marzenia**: kontekst marzenia/wartości/kierunku (`core/dream_architect.py`) oraz **Obraz Użytkownika** — destylat onboardingu (`core/obraz_uzytkownika.py`).
- **AKSJOMAT 2 — Domknięcie**: najmniejszy możliwy ruch (≤60 min). Egzekwowane przez `core/completion_enforcer.py` — audyt prozy syntezy Syeza + limity aktywnych projektów (`MAX_ACTIVE_PROJECTS`, domyślnie 1).

---

## 2. Architektura techniczna

| Warstwa | Technologia |
|---|---|
| Backend | Python **3.13**, FastAPI **3.3.0**, Uvicorn (`WEB_CONCURRENCY`) |
| Model LLM | Anthropic **claude-sonnet-4-6** dla wszystkich agentów i Syeza (`config/agent_models.py`) |
| Backends LLM | `LLM_BACKEND=auto\|anthropic\|xai\|ollama` (`config/llm_providers.py`); xAI: grok-3 / grok-3-mini; Ollama lokalnie |
| BYOK | Nagłówek `X-LLM-Key` → ContextVar; prod bez klucza usera → fail-closed |
| Desktop UI | Tauri **0.1.0** + React **19** + TypeScript + Vite 6 + Tailwind |
| Baza (dev / pudełko) | SQLite (aiosqlite), plik lokalny |
| Baza (hosted) | PostgreSQL + **RLS** (asyncpg, `db/pg_wrap.py`), migracje `0001`–`0009` |
| Cache / stan | Redis (JTI blocklist, rate-limit, refresh tokens, idempotency debat) |
| Transkrypcja głosu | Whisper (OpenAI API, `AW_WHISPER_BACKEND`) |
| Build | `requirements.lock` (deterministyczny, py3.13), Docker non-root uid 10001, CI z bramkami |

### Rdzeń agentów — `agents/base_agent.py`

Asynchroniczna komunikacja z LLM, retry z exponential backoff, cache odpowiedzi z **twardą izolacją per-user** (`_cache_key`), śledzenie kosztów tokenów, wstrzykiwanie Dream Architecture, postscriptum domknięcia.

---

## 3. Rada — 9 głosów + Syez

Pliki: `agents/{kogit,szow,kidi,tai,obver,relacjan,emojy,smaty,deega,syez}.py`. Kolejność w `COUNCIL`: Relacjan, Kogit, Emojy, Deega, Smaty, Szow, Tai, Obver, Kidi. Syez jest **poza** listą Rady.

| Agent | Rola | Temp. | max_tokens |
|---|---|:--:|:--:|
| **Kogit** | Kognitywny — ukryte przekonania, założenia | 0.7 | 4000 |
| **Szow** | Cień (Jung) — wyparte, sabotujące | 1.0 | 1500 |
| **Kidi** | Dziecko — ciekawość sprzed ograniczeń | 1.0 | 1500 |
| **Tai** | Czasowy — pętle i wzorce | 0.6 | 4000 |
| **Obver** | Obserwator — meta-perspektywa bez ocen | 0.8 | 2000 |
| **Relacjan** | Relacyjny — sieć relacji i lojalności | 0.8 | 2000 |
| **Emojy** | Emocjonalny — emocja jako informacja | 0.8 | 2000 |
| **Smaty** | Somatyczny — sygnały ciała | 1.0 | 1500 |
| **Deega** | Głęboka diagnoza — wzorce z przeszłości | 0.0 | 2000 |
| **Syez** | Syntezator — lustro Rady + Marzenia | 0.5 (3000) / FA2: 0.6 (5000) |

---

## 4. Tryby pracy

### Tryby debaty (`VALID_MODES` w `business_fa2/config/modes.py`)

| Tryb API | Znaczenie |
|---|---|
| `pelna` | 9 agentów + Syez |
| `codzienny` | 4 agentów (Kogit, Emojy, Smaty, Obver) + Syez; tańszy check-in ~5 min |
| `marzen` | 9 + Syez; wzmocniona faza A0 |
| `schematy` | 9 + Syez; agresywniejszy Szow/Deega; wymuszone commitments |

Kategorie briefu: `decyzja`, `projekt`, `marzenie`, `schemat`.

### Tryby kontekstu (`council_mode`)

- **personal** (domyślny) — A0 destylacja marzenia, Obraz Użytkownika, ton transformacyjny.
- **fa2** — nagłówek `X-Council-Mode: fa2` lub endpoint `/business/debate/stream`; bez A0 i Obrazu; prompty biznesowe (`business_fa2/prompts/`); scenariusze Base/Bull/Bear w syntezie.

---

## 5. Przepływ debaty — `api/services/debate_orchestrator.py`

Pipeline SSE: **safety_check → A0 (personal) → agenci równolegle → napięcia → Syez → audyt domknięcia → commitments → zapis**.

1. `debate_pending` · BYOK precheck · `safety_halt` przy ideacji samobójczej
2. **A0** — `distill_dream` → `dream_architecture` (pominięte w `fa2`)
3. Persist marzenia/projektu (`dream_service.py`) — marzenia i projekty powstają **w trakcie debaty**, nie przez osobne REST POST
4. **Faza Rady** — równoległe agenty, chunki SSE (`agent_chunk`)
5. **live_tensions** + **tension_axis** (frontend: `TensionAxis.tsx`)
6. **Syez** — synteza prozą; `completion_enforcer` audytuje domknięcie
7. **Kontynuacja** — `POST /debate/continue/stream` z kontekstem poprzedniej syntezy

**Idempotency:** `Idempotency-Key` na `/debate/stream` i `/debate/continue/stream` (`api/idempotency.py`); frontend wysyła ten sam klucz przy jednym retry SSE (`useDebate.ts`).

**Konfrontacja (druga tura):** prototyp za `AW_COUNCIL_DEBATE_ROUNDS` — nie włączony domyślnie (`confrontation.py`).

---

## 6. Warstwa danych i izolacja

- **ContextVar** `tenant_id` / `user_id` (`db/tenant.py`) — per-request w `http_guard`; model hosted: **user = tenant** (`tenant_id := JWT sub`).
- **RLS Postgres** — migracje `0001`–`0009`; **`0009`** usuwa bypass pustego GUC → fail-closed; `FORCE ROW LEVEL SECURITY` na 12 tabelach.
- **Cache LLM** — izolacja per `user_id`; bramka CI: `scripts/verify_cache_isolation.py`.
- **Model pudełkowy** — SQLite lokalnie bez RLS; izolacja = jeden user na instalację + device seal.

---

## 7. Bezpieczeństwo i autoryzacja

Baseline: **`CODE_REVIEW_2026-06-16.md`** — 4 blokery 2026-06-02 zamknięte.

- **JWT** HS256 (`ARCHITEKT_JWT_SECRET`); claimy `exp`, `sub`, `jti` wymagane; revoke przez Redis blocklist (fail-closed w prod).
- **Legacy `ARCHITEKT_API_KEY`** — deprecated; odrzucony gdy JWT aktywne.
- **Admin** — `ARCHITEKT_ADMIN_TOKEN`; `/admin/*`, `/metrics`.
- **Device Seal** (`core/device_seal.py`) — `~/.architekt-wolnosci/device.seal`; kopia na inny komputer → **423**; reset: `python -m tools.device_reset`.
- **CSP Tauri** — pełna polityka, `script-src 'self'` (bez unsafe-inline), `object-src 'none'`.
- **RODO** — `GET /account/export`, `DELETE /account`.
- **Safety** — `core/safety.py`; SSE `safety_halt` + numer 116 123 w UI.

**Blokery GTM (nie luki security):** buildy desktop **niepodpisane** (`signingIdentity: null`); SQLite **plaintext** at-rest w paczce — patrz roadmap N1, N4.

---

## 8. Mapa API

### Debata (`main.py`)

| Metoda | Endpoint |
|---|---|
| POST | `/debate/stream` |
| POST | `/debate/continue/stream` |
| GET | `/history` |
| GET | `/debate/{id}` · `/debate/{id}/thread` |
| GET | `/debate/{id}/export.md` · `/debate/{id}/export.pdf` |

### Zobowiązania (AKSJOMAT 2)

| Metoda | Endpoint |
|---|---|
| POST | `/commitment` |
| GET | `/commitments/due` |
| POST | `/commitment/{id}/release` (reason ≥30 znaków) |
| PATCH | `/commitment/{id}/complete` |
| DELETE | `/commitment/{id}` (zablokowany — `shadow_no_silent_release`) |

### Marzenia i projekty (odczyt + zarządzanie cyklem)

| Metoda | Endpoint | Uwaga |
|---|---|---|
| GET | `/dreams` · `/dreams/{id}` | Tworzenie w pipeline debaty |
| GET | `/projects` · `/projects/{id}` · `/projects/{id}/commitments` | Projekt przy brief `projekt` |
| PATCH | `/projects/{id}/functionality/{item_id}` | Checklista funkcjonalności |
| POST | `/projects/{id}/complete` | Wymaga checklisty 100% |
| POST | `/projects/{id}/archive` | Wymaga `reason` ≥50 znaków |

### Personal (`/personal` — `api/routers/personal.py`)

| Metoda | Endpoint |
|---|---|
| GET | `/personal/onboarding/questions` |
| POST | `/personal/onboarding/save` |
| GET | `/personal/onboarding/answers` |
| POST | `/personal/onboarding/synthesize` |
| GET | `/personal/onboarding/obraz` |
| GET | `/personal/ritual/daily` |

### Auth, konto, urządzenie

| Prefix | Kluczowe endpointy |
|---|---|
| `/auth` | register, login, demo, me, refresh, password-reset/confirm, revoke |
| `/account` | export (RODO), DELETE (usunięcie konta) |
| `/device` | status |
| `/demo` | status |

### Multimodalne i integracje

| Prefix | Endpointy |
|---|---|
| `/voice` | POST transcribe (Whisper, do 25 MB) |
| `/attachment` | POST extract (PDF/DOCX/TXT → extra_context) |
| `/integrations` | status, notion/todoist/gcal export |

### Meta / admin

| Endpoint | Opis |
|---|---|
| GET `/health` · `/health/ready` · `/costs/status` | Meta router |
| GET `/edition` | Dostępne edycje (`personal`, `business`) |
| GET `/metrics` | Prometheus (admin token) |
| POST `/feedback` | Soft-launch feedback |
| POST `/generate` | **Legacy** — UI używa `/debate/stream` |
| POST `/admin/*` | password-reset-token, trigger-followups, rebuild-evolution |

### Business FA2 (`app.mount("/business", …)`)

| Metoda | Endpoint |
|---|---|
| POST | `/business/debate/stream` (wymusza `council_mode=fa2`) |
| GET | `/business/health` |

---

## 9. Moduły rdzenia (`core/`)

| Moduł | Rola |
|---|---|
| `dream_architect.py` | AKSJOMAT 1 + Fragment + Daily Signal |
| `completion_enforcer.py` | AKSJOMAT 2 — audyt prozy, limity projektów |
| `obraz_uzytkownika.py` | Destylat onboardingu |
| `agent_learner.py` | Notatki ewolucyjne agentów (Faza 3) |
| `live_tensions.py` | Heurystyka napięć między parami agentów |
| `autonomy.py` | Mechanizm Autonomii Rady v1.2 |
| `safety.py` | Protokół bezpieczeństwa życia |
| `device_seal.py` | Pieczęć urządzenia |
| `cost_tracking.py` | Koszty tokenów |
| `analytics.py` | Eventy produktowe (`data/events.jsonl`) |
| `debate_export.py` / `debate_export_pdf.py` | Eksport MD/PDF |
| `identity.py` | Kontekst tożsamości użytkownika |

---

## 10. Frontend (Tauri desktop)

Hook: `src/src/hooks/useDebate.ts` + reduktor `debateSseReducer.ts` (testy jednostkowe w CI).

**Odporność SSE:** manualny `TextDecoder` (workaround WebKit/Tauri), 1 retry tylko gdy `!receivedFirstEvent`, `Idempotency-Key`, cleanup readera na unmount, obsługa `safety_halt`.

**BYOK:** `llmKeyStorage.ts` — gate przed startem debaty; w prod wymagany klucz LLM użytkownika.

**Główne komponenty:** `BriefForm`, `VoiceBriefButton`, `CouncilCircle`, `SyezPanel`, `TensionAxis`, `FragmentCompass`, `DreamsPanel`, `DreamWizard`, `DebateCommitments`, `CommitmentsTimeline`, `DebateHistory`, `MojObrazPanel`, `PersonalRitualPanels`, `LoginScreen`, `AccountPrivacyPanel`, `DeviceLockScreen`, `LocalSetupModal`, `IntegrationsModal`, `WorkspaceHeader`, `MermaidBlock`.

**`App.tsx`:** JWT auth, device lock, toggle `personal`/`fa2`, health check, offline banner.

---

## 11. Infrastruktura i CI

- **Docker** — `python:3.13-slim`, `requirements.lock`, non-root, healthcheck `/health/ready`
- **CI** (`.github/workflows/ci.yml`) — ruff, pip-audit, pytest coverage ≥75%, verify_cache_isolation, detect-secrets, grep-gate DB, RLS smoke Postgres 16, **frontend-test** (`npm run test:unit`), docker-build
- **Deploy** — tag `v*` → build obrazu; Tauri release workflow (manual, wymaga certyfikatów Apple)
- **Preflight** — prod wymusza sekrety, Redis, Postgres

### Stan wdrożenia

**Security:** brak otwartych blokerów z audytu 2026-06-02/16. **GTM:** płatna paczka zablokowana przez N1–N6 (roadmap). Hosted multi-tenant wymaga migracji `0001`–`0009` + konfiguracji operacyjnej (JWT, Redis, admin token).

---

## 12. Poza zakresem aplikacji

- **`tools/reels-generator/`** — minimalny skrypt do produkcji reelów (Ollama + ElevenLabs + ffmpeg); nie część aplikacji ani pipeline'u bezpieczeństwa.
- **`tools/ig-reels/`** — **usunięty** z repo (zastąpiony przez reels-generator).
- **`polyphony-site/`** — strona marketingowa (Vercel), osobny od aplikacji desktop.

---

## 13. Pakiet kontekstu dla zewnętrznych modeli (np. Grok)

Najmniejszy zestaw odzwierciedlający aktualny stan:

1. `CLAUDE.md` — filozofia i zasady pracy
2. Ten plik — funkcjonalny opis kodu
3. `docs/roadmap/ROADMAP_2026-06-17.md` — strategia i blokery

Kontrakt API szczegółowy: `docs/spec/SPEC_CURRENT.md`. Użytkownik końcowy: `USER_README.md`. Instalacja BYOK: `INSTALL.md`.
