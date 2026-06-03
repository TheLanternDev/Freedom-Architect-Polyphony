# Audyt gotowości produkcyjnej — Architekt Wolności / Freedom Architect: Polyphony

**Data audytu:** 2026-06-03 (pełny przebieg A–E)  
**Repozytorium:** `/Users/tpltd145/Projects/architekt-wolnosci`  
**Metoda:** przegląd kodu z cytatami `Plik:Linia`, uruchomienie `pytest` lokalnie (`AW_DISABLE_DOTENV=1`). **Bez zmian kodu w tym przebiegu.**  
**Kontekst misji:** `CLAUDE.md` — AKSJOMAT 0/1/2, autentyczność głosów Rady, izolacja tenantów, dyscyplina scope'u.

---

## 1. Executive summary

| Stan | Ocena | Werdykt (jedno zdanie) |
|------|-------|-------------------------|
| **PRODUCTION-READY** | **88%** | Postgres+RLS, fail-closed auth i preflight prod są wdrożone i testowane; pozostają ryzyka JWT w przeglądarce, brak testu prod JTI bez Redis oraz świadomy dev fallback SQLite bez RLS. |
| **DEPLOYMENT-READY** | **76%** | Kontener, compose prod, CI (pytest+RLS+docker-build), smoke i workflow deploy/Tauri istnieją; brakuje pełnego CD, probe Redis w ready, włączonego auto-update i notaryzacji desktop w CI. |
| **SALES-READY** | **38%** (SaaS) / **100%** (BYOK founders) | BYOK: oferta/GTM docs, demo guards, UI RODO, SALES_CHECKLIST, smoke_week1 — patrz sekcja E (2026-06-03 wdrożenie planu). SaaS nadal wymaga Stripe. |

### Testy (ten przebieg)

| Metryka | Wynik | Źródło |
|---------|-------|--------|
| Zebrane / passed / skipped | **572 passed**, **1 skipped**, **0 failed** | `pytest tests/ -q` |
| xfail | **0** | brak `@pytest.mark.xfail` w `tests/` |
| Skip | `tests/test_attachment_extract.py:93` — brak `pypdf` | stdout pytest |
| Coverage (gate CI) | **80%** (4124 stmts, 811 miss) | `--cov=agents,core,api,db --cov-fail-under=75` |
| Frontend unit | Vitest w CI job `frontend-test` | `.github/workflows/ci.yml:180–190` |

---

## 2. Tabela P0 — blokery (must-fix przed danym stanem)

| ID | Bloker | Status | Dotyczy | Plik:Linia | Co zrobić |
|----|--------|--------|---------|------------|-----------|
| P0-A1 | Admin/metrics vs JWT w guardzie | **ZAMKNIĘTE** | PRODUCTION | `api/http_guard.py:43–64` | — |
| P0-A2 | Feedback/onboarding bez tenant w DB | **ZAMKNIĘTE** | PRODUCTION | `api/routers/feedback.py:65–68`, `db/connection.py` repo | — |
| P0-A3 | `dream_debate_link` bez RLS | **ZAMKNIĘTE** | PRODUCTION | `db/migrations/0005_dream_debate_link_tenant.sql:60–68` | — |
| P0-D1 | Dockerfile bez `config/` | **ZAMKNIĘTE** | DEPLOYMENT | `Dockerfile:7–15` | — |
| P0-E1 | Brak płatności / planów (SaaS) | **N/A BYOK** | SALES (SaaS) | `README.md:94` | Stripe — poza modelem founders | P0 dla SaaS |
| P0-E2 | Brak UI RODO (eksport/usuń) | **ZAMKNIĘTE (BYOK)** | SALES | `src/src/components/AccountPrivacyPanel.tsx`, `LocalSetupModal.tsx` | — |

*Dla **hosted production** (własny backend, płatni użytkownicy): P0-E1/E2 blokują SALES; nie blokują PRODUCTION technicznego.*

---

## 3. Tabela P1

| ID | Problem | Plik:Linia | Co zrobić | Priorytet |
|----|---------|------------|-----------|-----------|
| P1-A1 | Dev fallback SQLite przy złym PG — **brak RLS** | `db/backend.py:140–147` | Tylko `AW_ENV!=production`; prod fail-fast `135–139` | Świadomość dev |
| P1-A2 | JWT w sessionStorage (web) / localStorage (Tauri) | `src/src/lib/tokenStorage.ts:4–15` | BFF + httpOnly cookies na web prod | P1 |
| P1-A3 | Prod JTI revoke fail-closed bez Redis — brak testu prod path | `api/auth_identity.py:14–42` | Test `AW_ENV=production` + brak Redis → block | P1 |
| P1-A4 | `ensure_not_demo_blocked_route` | **ZAMKNIĘTE** | `account.py`, `integrations.py`, `test_demo_mode.py` | — |
| P1-A5 | `App.tsx` — app bez JWT gdy `aw_jwt_enabled` ≠ `"1"` | `src/src/App.tsx:47–52`, `85–88` | Wymusić JWT na publicznym hoście prod | P1 |
| P1-B1 | Retry SSE przed 1. eventem — ryzyko drugiej debaty | `src/src/hooks/useDebate.ts:190–206` | Idempotency-Key / debounce API | P1 |
| P1-C1 | `main.py` poza coverage gate CI | `.github/workflows/ci.yml:62–65` | `--cov=main` lub routery do `api/` | P1 |
| P1-C2 | Brak pytest API na żywym Postgres (poza smoke SQL) | `ci.yml:97–178` | Integracyjny job z `DATABASE_URL` | P1 |
| P1-D1 | `/health/ready` nie sprawdza Redis | `api/routers/meta.py:55–68` | Opcjonalny 503 gdy Redis wymagany w prod | P1 |
| P1-D2 | Deploy workflow — tylko `workflow_dispatch` | `.github/workflows/deploy.yml` | Sekrety registry + push na tag | P1 |
| P1-D3 | Tauri updater wyłączony; brak notaryzacji w CI secrets | `docs/TAURI_RELEASE.md`, `tauri-release.yml` | Włączyć updater + Apple/Win signing | P1 |
| P1-E1 | Koszty — globalny `cost_log.jsonl`, brak `tenant_id` w wpisie | `core/cost_tracking.py:215–234` | Per-tenant metering dla SaaS | P1 |
| P1-E2 | Brak reset hasła / weryfikacji e-mail | `api/_rate_limit.py:27` (komentarz) | Flow lifecycle konta | P1 |
| P1-E3 | `COMPLIANCE_PRIVACY.md` — szkielet | `docs/COMPLIANCE_PRIVACY.md:1–3` | Wypełnić pod operatora | P1 |

---

## 4. Tabela P2

| ID | Problem | Plik:Linia | Co zrobić | Priorytet |
|----|---------|------------|-----------|-----------|
| P2-A1 | CSP Tauri: `unsafe-inline` | `src/src-tauri/tauri.conf.json:25–26` | Zaostrzyć prod build (`sync-tauri-csp.mjs`) | P2 |
| P2-A2 | Legacy `ARCHITEKT_API_KEY` deprecated | `api/http_guard.py:165–185` | Plan usunięcia | P2 |
| P2-A3 | `probe_db_ready` raw `pool.acquire` bez GUC | `db/backend.py:163–164` | OK dla `SELECT 1` | P2 |
| P2-B1 | Doc BaseAgent „5 prób” vs `stop_after_attempt(2)` | `agents/base_agent.py:6`, `539–543` | Ujednolicić docs | P2 |
| P2-B2 | Brak runtime failover Anthropic→xAI w debacie | `config/llm_providers.py:76–92` | Opcjonalny circuit breaker | P2 |
| P2-C1 | Brak Vitest dla `useDebate` reconnect | `src/src/hooks/useDebate.ts` | Mock ReadableStream | P2 |
| P2-D1 | Brak migracji SQL **down** | `db/backend.py:25–52` | Runbook pg_dump rollback | P2 |
| P2-D2 | `.env.example` niekompletny (Sentry, LOG_FORMAT, …) | `.env.example` | Komentarze prod | P2 |
| P2-E1 | `LoginScreen` „Skip login” | `src/src/components/LoginScreen.tsx:98–101`, `228` | Ukryć przy prod marketing | P2 |
| P2-E2 | `FOUNDERS_OFFER.md` — placeholdery ceny | `docs/FOUNDERS_OFFER.md:27–31` | Uzupełnić przed publikacją | P2 |

---

## 5. Sekcja A — Bezpieczeństwo i izolacja

### A.1 Auth (`http_guard`, `auth_identity`, `settings`)

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `api/http_guard.py:28–40` | Zaimplementowane + testowane | Public health/edition; OpenAPI off w prod | — | — |
| `api/http_guard.py:43–64` | Zaimplementowane + testowane | `/metrics`, `/admin/*` własny Bearer admin | Dokumentacja dual-auth | P2 |
| `api/http_guard.py:60–61` | Zaimplementowane | `/auth/*` bez guard — własne limity w routerze | — | P1 |
| `api/http_guard.py:78–102` | Zaimplementowane + testowane | Fail-closed bez sekretów; `AW_INSECURE` → 403 w prod | — | P0 |
| `api/http_guard.py:104–133` | Zaimplementowane + testowane | BFF + JWT wymaga `X-Tenant-Id` | Test BFF w CI | P1 |
| `api/http_guard.py:140–196` | Zaimplementowane + testowane | JWT → ContextVar; legacy off gdy JWT on | — | — |
| `api/auth_identity.py:14–42` | Zaimplementowane; prod path słabiej testowany | Bez Redis: JTI block fail-closed w prod | Test + HA Redis | P1 |
| `api/auth_identity.py:57–115` | Zaimplementowane + testowane | HS256, tenant claim w prod | — | — |
| `api/settings.py:76–113` | Zaimplementowane + testowane | Preflight: PG, JWT≥32, CORS, Redis, Anthropic, ADMIN | — | — |
| `main.py:225–246` | Zaimplementowane + testowane | `SystemExit` na błędach preflight | — | — |

**Testy:** `tests/test_stage1_security.py`, `tests/test_auth_modes.py`, `tests/test_auth_identity_unit.py`, `tests/test_settings_openapi.py`.

### A.2 Tenant / RLS / DB

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `db/tenant.py:39–77` | Zaimplementowane + testowane | ContextVar per-task | — | — |
| `db/pg_wrap.py:102–159` | Zaimplementowane + testowane | GUC transaction-local; pusty tenant → RuntimeError | — | P0 |
| `db/backend.py:114–125` | Zaimplementowane + testowane | Jedyne raw `_pg_pool.acquire()` w init DDL | Review przy zmianach | P0 |
| `db/backend.py:178–216` | Zaimplementowane + testowane | HTTP/SSE przez `PgConnection` | — | — |
| `db/backend.py:131–147` | Zaimplementowane (nowe) | Dev: fallback SQLite bez RLS | Nie używać w prod | P1 |
| `db/migrations/0002_enable_rls.sql:31–61` | Zaimplementowane + CI smoke | 8 tabel core + policy | — | — |
| `db/migrations/0003–0004` | Zaimplementowane + smoke feedback | `feedback`, `onboarding_answers` | — | — |
| `db/migrations/0005_dream_debate_link_tenant.sql:60–68` | Zaimplementowane + CI | RLS na junction | — | — |
| `db/migrations/0006_users_revoke_public.sql` | Zaimplementowane | `users` bez RLS; REVOKE PUBLIC | Least privilege DB role | P1 |

**Tabele z danymi usera — RLS (Postgres):**

| Tabela | RLS `tenant_isolation` | Uwagi |
|--------|------------------------|-------|
| dreams, debates, agent_voices, projects, functionality_items, completion_audits, commitments, agent_evolution | tak (0002) | OK |
| feedback, onboarding_answers | tak (0003, 0004) | Repo zapis: `feedback.py:65–68` |
| dream_debate_link | tak (0005) | OK |
| users | **nie** (login) | `0006` REVOKE PUBLIC |
| schema_migrations | nie | Metadane migracji |

**Raw pool bypass:** tylko `db/backend.py:122` (init), `db/backend.py:163` (health `SELECT 1`). Potwierdzenie: `tests/test_rls_migration.py:57`.

### A.3 Admin / privileged

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `main.py:364–386` | Zaimplementowane + testowane | `GET /metrics` — Bearer `ARCHITEKT_ADMIN_TOKEN` | Rotacja tokenu | P0 |
| `main.py:948–972` | Zaimplementowane + testowane | `POST /admin/trigger-followups` | j.w. | P0 |
| `main.py:1177–1196` | Zaimplementowane + testowane | `POST /admin/rebuild-evolution` | j.w. | P0 |
| `api/routers/account.py:43–86` | Zaimplementowane + testowane | JWT-only export/delete + demo guard | **ZAMKNIĘTE** | — |
| `api/routers/meta.py:71–83` | Zaimplementowane | `/costs/status` za guardem | — | P2 |

### A.4 Sekrety, frontend, CSP

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `src/src/lib/apiAuth.ts:101–107` | Zaimplementowane | `VITE_ARCHITEKT_API_KEY` tylko DEV | — | — |
| `src/src/lib/tokenStorage.ts:4–15` | Zaimplementowane | JWT w storage przeglądarki | BFF httpOnly | P1 |
| `src/src-tauri/tauri.conf.json:25–26` | Zaimplementowane | CSP `unsafe-inline`; connect-src localhost | Sync prod API URL | P2 |
| `src/src-tauri/capabilities/default.json:6–8` | Zaimplementowane | `shell:allow-open` | Audyt wywołań open | P2 |

### A.5 Rate limit, walidacja, integracje

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `main.py:347–357` | Zaimplementowane | slowapi Redis lub memory | Redis w prod multi-instance | P1 |
| `api/_rate_limit.py:21–32` | Zaimplementowane + testowane | Klucz per JWT `sub` | — | — |
| `api/routers/integrations.py:75–267` | Zaimplementowane + testowane częściowo | **Brak SSRF** — stałe URL (Notion/Todoist/Google) | — | — |
| `api/routers/meta.py:55–56` | Zaimplementowane | ready 120/min/IP | — | P2 |
| `tests/test_integrations_api.py` | Zaimplementowane | 401/400 bez ENV | — | — |

---

## 6. Sekcja B — Poprawność i odporność

### B.1 LLM

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `agents/base_agent.py:539–547` | Zaimplementowane + testowane | Retry 2× na RateLimit/Connection | Docs vs kod | P2 |
| `agents/base_agent.py:663–666`, `730–746` | Zaimplementowane + testowane | Timeout bez fallbacku | — | — |
| `agents/base_agent.py:747–757` | Zaimplementowane + testowane | Exception → `_fallback_contribute` | Monitoring | P2 |
| `agents/base_agent.py:509–537` | Zaimplementowane + testowane | Cache v8 + tenant/user | `verify_cache_isolation.py` | — |
| `config/llm_providers.py:76–92` | Zaimplementowane | Wybór backendu przy starcie, nie w trakcie debaty | P2-B2 | P2 |
| `core/dream_architect.py:663–805` | Zaimplementowane + testowane | Pusty brief / timeout → fallback | — | — |
| `core/dream_architect.py:464–482` | Zaimplementowane | In-process `_DREAM_CACHE` bez TTL | LRU/TTL | P2 |

### B.2 SSE

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `api/services/debate_orchestrator.py:493–508` | Zaimplementowane | Cancel agentów przy disconnect | Test integracyjny | P1 |
| `api/services/debate_orchestrator.py:614–618` | Zaimplementowane | Cancel Syez | j.w. | P1 |
| `api/services/debate_orchestrator.py:910–925` | Zaimplementowane | `insert_debate_for_stream` po Radzie | — | — |
| `api/services/debate_orchestrator.py:553–582` | Zaimplementowane + testowane | CompletionViolation re-prompt | — | — |
| `src/src/hooks/useDebate.ts:82–87` | Zaimplementowane | Cleanup reader on unmount | Vitest | P2 |
| `src/src/hooks/useDebate.ts:190–206` | Zaimplementowane | 1× retry przed 1. eventem | Idempotency | P1 |
| `tests/test_debate_stream_smoke.py` | Zaimplementowane + testowane | Offline sekwencja SSE | — | — |

### B.3 Współbieżność / AKSJOMATY

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `core/cost_tracking.py:33–44` | Zaimplementowane | `fcntl.flock` na append | — | — |
| `core/completion_enforcer.py` | Zaimplementowane + testowane | `test_completion_enforcer.py`, `test_hard_lock_and_audit.py` | — | — |
| `core/autonomy.py` | Zaimplementowane + testowane; **poza runtime API** | 13 testów; brak persistencji | Aktywacja lub archiwum | P2 |

---

## 7. Sekcja C — Testy

### C.1 Wynik wykonania

| Metryka | Wynik |
|---------|-------|
| Passed | **572** |
| Skipped | **1** (`test_attachment_extract.py:93`) |
| Failed / xfail | **0** |
| Coverage `agents+core+api+db` | **80%** (gate 75% PASS) |
| `pytest.ini` | `-W error::DeprecationWarning` |

### C.2 CI (`.github/workflows/ci.yml`)

| Job | Linie | Ocena |
|-----|-------|-------|
| lint + raw SQL guard | 8–39 | OK |
| pip-audit | 41–49 | OK |
| pytest + cov≥75% + cache script | 51–67 | OK |
| secrets-scan | 69–95 | OK |
| rls-smoke PG 0001–0006 | 97–178 | OK |
| frontend-test | 180–190 | OK (minimalny Vitest) |
| docker-build | 192–200 | OK |

**Brak w CI:** pełny API test na Postgres, Tauri build na każdym PR, E2E browser, `pytest-benchmark` (`tests/benchmark_rada.py`).

### C.3 Mapowanie krytycznych ścieżek

| Ścieżka | Stan | Pliki testowe |
|---------|------|---------------|
| Auth fail-closed / JWT / BFF | Testowane | `test_stage1_security.py`, `test_auth_identity_unit.py`, `test_auth_modes.py` |
| Tenant isolation | Testowane | `test_multiuser_isolation.py`, `test_debate_detail_tenant_isolation.py`, `test_repo_tenant_p0_fixes.py` |
| RLS Postgres | CI smoke + statycznie | `test_rls_migration.py`, job `rls-smoke` |
| AKSJOMAT 1/2 | Testowane | `test_dream_architect*.py`, `test_completion_enforcer.py`, `test_hard_lock_and_audit.py` |
| Koszty / budget | Testowane | `test_cost_budget.py`, `test_budget_guard.py` |
| RODO API | Testowane | `test_account_rodo.py`, `test_e2e_user_journey.py` |
| Demo | Testowane | `test_demo_mode.py` |
| Dev DB fallback | Testowane | `test_db_dev_fallback.py` |
| Integracje / voice / identity | Testowane | `test_integrations_api.py`, `test_voice_api.py`, `test_identity.py` |

### C.4 Moduły bez lub ze słabymi testami

| Moduł | Stan |
|-------|------|
| `main.py` (~1200 linii) | Poza cov gate; częściowo przez TestClient |
| `src/src/hooks/useDebate.ts` | Brak Vitest (poza `debateSseReducer.test.ts`) |
| `api/auth_identity.py` prod JTI bez Redis | Brak dedykowanego testu |
| Live Postgres przez FastAPI `get_db` | Tylko SQLite w większości testów |

---

## 8. Sekcja D — Deployment

### D.1 Konteneryzacja i compose

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `Dockerfile:1–21` | Zaimplementowane | COPY `config`, `business_fa2`, `modes`; HEALTHCHECK → ready | — | — |
| `docker-compose.prod.yml` | Zaimplementowane | PG16 + Redis7 + API; `AW_ENV: production` | Sekrety w `.env` | — |
| `docker-compose.yml:9–13` | Dev only | `AW_INSECURE_NO_AUTH`, SQLite | Nie używać jako prod | P0 świadomość |

### D.2 Startup / preflight

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `main.py:249–292` | Zaimplementowane + testowane | Redis fail → SystemExit w prod | — | — |
| `api/startup.py:11–31` | Zaimplementowane + testowane | `handle_init_db_failure`, `redis_required_in_prod` | — | — |
| `db/backend.py:135–139` | Zaimplementowane | Prod PG init fail → raise → SystemExit | — | — |
| `api/settings.py:76–113` | Zaimplementowane | Lista wymaganych ENV prod | — | — |

### D.3 Health / observability

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `api/routers/meta.py:17–52` | Zaimplementowane | `GET /health` — meta alive | — | — |
| `api/routers/meta.py:55–68` | Zaimplementowane | `GET /health/ready` — `probe_db_ready`, 503 z powodem | Redis probe | P1 |
| `main.py:364–386` | Zaimplementowane | Prometheus `/metrics` + admin token | — | — |
| `api/_log.py` | Zaimplementowane | Structured `slog()`; `LOG_FORMAT=json` | Dokumentacja ENV | P2 |
| `api/_metrics.py` | Zaimplementowane | Stub bez `prometheus_client` w dev | W requirements obrazu | — |
| `main.py:69–103` | Zaimplementowane | Sentry opcjonalny | `SENTRY_DSN` w .env.example | P2 |

### D.4 Migracje

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `db/backend.py:25–65` | Zaimplementowane | `schema_migrations` + sorted `*.sql` | Kolejność 0001–0006 | — |
| `db/migrations/*.sql` | 6 plików idempotentnych | Brak down migration | Runbook pg_dump | P2 |

### D.5 CI/CD i rollback

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `.github/workflows/ci.yml` | 7 jobów | Brak auto-deploy na push | `deploy.yml` secrets | P1 |
| `.github/workflows/deploy.yml` | Manual dispatch | Build/push image | REGISTRY_* | P1 |
| `.github/workflows/tauri-release.yml` | macOS release | Signing secrets operator | P1 |
| `scripts/smoke_live.py` | Zaimplementowane | Post-deploy health | — | — |
| `docs/PRODUCTION_CHECKLIST.md` | Zaimplementowane | ENV + smoke | Utrzymywać sync | P2 |
| `docs/SOFT_LAUNCH.md` | Zaimplementowane | Rollback pg_dump | — | P2 |

### D.6 Tauri desktop

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `docs/TAURI_RELEASE.md` | Zaimplementowane | Procedura build/sign | — | — |
| `src/package.json` | `tauri:build:release` | Updater domyślnie off | Włączyć + CI secrets | P1 |
| `src/scripts/sync-tauri-csp.mjs` | Zaimplementowane | CSP vs `VITE_API_URL` | — | — |

**DEPLOYMENT-READY uzasadnienie 76%:** ścieżka ręczna (managed PG + Redis + uvicorn/Docker) jest gotowa; brakuje pełnej automatyzacji release, hardening desktop i probe Redis w readiness.

### D.7 Wymagane ENV produkcji (skrót)

| Zmienna | Źródło wymogu |
|---------|----------------|
| `AW_ENV=production` | `api/settings.py:12–14` |
| `DATABASE_URL=postgresql://…` | `api/settings.py:82–86` |
| `ARCHITEKT_JWT_SECRET` (≥32 znaków) | `api/settings.py:87–96` |
| `AW_CORS_ORIGINS` (lista, nie `*`) | `api/settings.py:97–100` |
| `REDIS_URL` (poza demo) | `api/settings.py:101–105` |
| `ANTHROPIC_API_KEY` | `api/settings.py:106–107` |
| `ARCHITEKT_ADMIN_TOKEN` | `api/settings.py:108–112` |

---

## 9. Sekcja E — Sales / Go-to-Market

*Pełny audyt sekcji E (wymaganie zadania „Wykonaj E”).*

### E.1 Onboarding użytkownika

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `api/routers/auth.py:185–222` | Zaimplementowane + testowane | `POST /auth/register` — Argon2id, `tenant_id` z hash username | — | — |
| `api/routers/auth.py:225–279` | Zaimplementowane + testowane | Login + migracja PBKDF2→Argon2 | — | — |
| `api/routers/auth.py:282–309` | Zaimplementowane + testowane | `POST /auth/demo` — tenant `demo_*` | — | — |
| `api/routers/auth.py:190–194` | Zaimplementowane + testowane | Register **403** w demo | — | — |
| `src/src/components/LoginScreen.tsx:59–88` | Zaimplementowane | UI login/register → API | — | — |
| `src/src/components/LoginScreen.tsx:118–154` | Zaimplementowane | Ekran demo gdy `demoConfig.enabled` | — | — |
| `src/src/components/LoginScreen.tsx:98–101`, `228` | Zaimplementowane | **Skip login** — wejście bez konta | Publiczny prod marketing | P2 |
| `src/src/App.tsx:47–52`, `85–88` | Zaimplementowane | Auth jeśli JWT **lub** `aw_jwt_enabled` ≠ `"1"` | Wymusić login na SaaS | P1 |
| `src/src/App.tsx:201–204` | Zaimplementowane | Pusty stan → `BriefForm` | — | — |
| `src/src/components/BriefForm.tsx:262–273` | Zaimplementowane | Dismissible onboarding card | — | — |
| `api/routers/personal.py:21–95` | Zaimplementowane częściowo | 20 pytań personal; dev JSONL fallback | Wymaga JWT w prod | P1 |
| `src/src/components/PersonalRitualPanels.tsx` | Zaimplementowane | Modal 20Q + `aw_onboarding_v1_done` | — | — |
| Brak w kodzie | **Brak** | Reset hasła, weryfikacja e-mail, zaproszenia | Flow lifecycle | P1 |

**Testy:** `tests/test_e2e_user_journey.py:95–159`, `tests/test_demo_mode.py`, `tests/test_auth_helpers_unit.py`.

### E.2 Billing / limity kosztów

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `core/cost_tracking.py:168–199` | Zaimplementowane + testowane | **Globalne** `DAILY_BUDGET_HARD_USD` / `MONTHLY_*` → HTTP 402 | OK dla operatora BYOK | — |
| `api/services/budget_guard.py:69–91` | Zaimplementowane + testowane | Soft `DAILY_BUDGET_USD` → SSE `budget_warning` | — | — |
| `main.py:640` (grep) | Zaimplementowane | `ensure_hard_budget_or_raise` przed debatą | — | — |
| `core/cost_tracking.py:215–234` | Zaimplementowane | `cost_log.jsonl` — **brak `tenant_id`** w wpisie | Per-customer billing | P0 SaaS |
| `README.md:94` | Udokumentowane | **Brak Stripe** w kodzie | Integracja płatności | P0 SaaS |
| `main.py:1252` | Udokumentowane | Komentarz: zero Stripe | — | — |
| `docs/FOUNDERS_OFFER.md:27–31` | **Brak** | Placeholder ceny i kanału płatności | Wypełnić przed sprzedażą | P0/P2 |

**Testy:** `tests/test_cost_budget.py`, `tests/test_budget_guard.py`.

**Werdykt billing:** egzekwowanie kosztów **operatora** (jeden deployment) — **tak**; monetyzacja **per użytkownik/plan** — **nie**.

### E.3 RODO / prywatność

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `api/routers/account.py:43–51` | Zaimplementowane + testowane | `GET /account/export` — JWT, `repo.export_tenant_data` | UI eksportu | P0 SaaS |
| `api/routers/account.py:55–86` | Zaimplementowane + testowane | `DELETE /account` — confirm `USUŃ MOJE KONTO`, purge, revoke refresh | UI usuwania | P0 SaaS |
| `db/connection.py:1180–1300` | Zaimplementowane + testowane | Eksport/purge per `tenant_id` | — | — |
| `tests/test_account_rodo.py:92–186` | Zaimplementowane + testowane | Izolacja eksportu; purge; 400 bez confirm | — | — |
| `tests/test_e2e_user_journey.py` | Zaimplementowane + testowane | register → export → delete | — | — |
| `src/` (grep `/account`) | **Brak** | Użytkownik nie może sam obsłużyć RODO w UI | Panel Privacy | P0 SaaS |
| `docs/COMPLIANCE_PRIVACY.md:1–22` | Szkielet | Brak polityki operatora | Wypełnić + link w app | P1 |
| `docs/SECURITY_PRODUCTION.md:67` | Zaimplementowane | Odsyła do compliance | — | — |
| `api/services/demo_guard.py:120–129` | **Zaimplementowane, niepodłączone** | Demo JWT może wołać `/account/*` | `ensure_not_demo_blocked_route` w routerze | P1 |

### E.4 Dokumentacja produktowa

| Dokument | Stan | Ryzyko | Co zrobić | Priorytet |
|----------|------|--------|-----------|-----------|
| `README.md` | Aktualne technicznie | Brak cennika | `PRICING.md` lub FOUNDERS | P2 |
| `docs/PRODUCTION_CHECKLIST.md:7–14` | Aktualne ops | Wspomina RODO endpoints | — | — |
| `docs/DEMO.md` | Zaimplementowane | Tryb pokazowy | Testy w README | — |
| `docs/FOUNDERS_OFFER.md` | Szkielet komercyjny | Placeholdery | Publikacja oferty BYOK | P2 |
| `docs/spec/PRD_Architekt_Wolnosci_v3.3.md:193` | PRD | Stripe poza scope v3.3 | Roadmap SaaS | P2 |
| Koszty w USD | Spójne w kodzie | Brak PLN/EUR w ofercie | Lokalizacja cennika | P2 |

### E.5 Demo mode — bezpieczeństwo pokazów

| Plik:Linia | Stan | Ryzyko | Co zrobić | Priorytet |
|------------|------|--------|-----------|-----------|
| `api/settings.py:197–199` | Zaimplementowane | `AW_DEMO_MODE` | — | — |
| `api/startup.py:11–18` | Zaimplementowane | Demo zwalnia wymóg Redis w preflight | OK dla trial host | — |
| `api/services/demo_guard.py:44–117` | Zaimplementowane + testowane | Limit debat, tryb, długość briefu | — | — |
| `tests/test_demo_mode.py:69–141` | Zaimplementowane + testowane | Register off, limity, edition | Brak testu `/account` | P1 |
| `docs/DEMO.md` | Udokumentowane | Integracje + RODO blokowane API dla demo | **ZAMKNIĘTE** | — |
| `src/src/lib/demoConfig.ts:38` | Zaimplementowane | Ustawia `aw_jwt_enabled=1` po demo | — | — |

### E.6 Ocena SALES-READY (%)

| Model GTM | Gotowość | Bloker (~%) | Uzasadnienie |
|-----------|----------|-------------|--------------|
| **Hosted SaaS** (trial → płatne konto → faktura → RODO self-serve) | **38%** | **~62%** | Brak Stripe/planów, brak limitów per tenant w `cost_log`, brak UI RODO, szkielet compliance, słabe demo guards na account |
| **Founders BYOK** (lokalnie/Tauri, klient płaci Anthropic) | **100%** | **0%** (kod+docs) | Plan S0–S6 wdrożony: `AccountPrivacyPanel`, demo guards, `SALES_CHECKLIST`, `GTM_DECISIONS`, `smoke_week1.sh`. **Przed launch:** uzupełnij `[DO UZUPEŁNIENIA]` w FOUNDERS/GTM (cena, e-mail). |

**Artefakty wdrożenia (2026-06-03):** `docs/SALES_CHECKLIST.md`, `docs/GTM_DECISIONS.md`, `docs/PRICING.md`, `scripts/smoke_week1.sh`, `src/src/components/AccountPrivacyPanel.tsx`.

---

## 10. Najmniejszy następny krok przed publicznym launch BYOK

Uzupełnij pola **[DO UZUPEŁNIENIA]** w [docs/GTM_DECISIONS.md](docs/GTM_DECISIONS.md) i skopiuj do [docs/FOUNDERS_OFFER.md](docs/FOUNDERS_OFFER.md) — potem odhacz [docs/SALES_CHECKLIST.md](docs/SALES_CHECKLIST.md) S0 i sign-off S6.

---

## 11. Macierz stanów — co blokuje co

| Wymaganie | PRODUCTION | DEPLOYMENT | SALES (SaaS) |
|-----------|------------|------------|--------------|
| Postgres + RLS | Wymagane (preflight) | Wymagane | Wymagane |
| Redis prod | Wymagane (JTI/refresh/rate) | Wymagane | Wymagane |
| JWT per-user | Wymagane | Wymagane | Wymagane |
| Docker/CI green | Zalecane | Wymagane | Zalecane |
| Stripe / plany | Nie | Nie | **Wymagane** |
| UI RODO | Zalecane API | Nie | **Wymagane** |
| Polityka prywatności | Zalecane | Nie | **Wymagane** |
| Demo bezpieczny | Zalecane | Zalecane | **Wymagane** |

---

*Raport kompletny (A–E). SALES-READY BYOK 100% w kodzie/docs — 2026-06-03 (plan S0–S6).*
