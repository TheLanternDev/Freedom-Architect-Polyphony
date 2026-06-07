# Code Review — Architekt Wolności (Freedom Architect: Polyphony)
**Data:** 2026-06-07 · **Zakres:** pełny przegląd pod kątem *sales-ready* i *deployment-ready* · **Baseline:** review 2026-06-02

## Streszczenie

Od review z 2026-06-02 nastąpił duży, realny skok jakości warstwy bezpieczeństwa. **Wszystkie cztery zgłoszone wtedy problemy Critical/High zostały zamknięte** — i to nie obejściem, ale poprawnym, fail-closed projektem z testami i bramkami CI. Kod jest dyscyplinowany, dobrze skomentowany w miejscach krytycznych (decyzje izolacji opisane wprost w `db/tenant.py`, `pg_wrap.py`, `http_guard.py`) i ma nietypowo silny pipeline CI.

**Werdykt deploy-ready:** TAK dla wdrożenia jednoosobowego/desktop oraz dla kontrolowanego soft-launchu multi-user na Postgres — **pod warunkiem** poprawnej konfiguracji ENV (którą start wymusza fail-fast) i domknięcia 3 punktów operacyjnych niżej.

**Werdykt sales-ready:** TAK warunkowo. Posturę auth/izolacji można już uczciwie przedstawić klientowi. Przed sprzedażą multi-tenant/team warto domknąć kwestie operacyjne (runtime jako root, brak workerów, hardening kontenera) — to nie blokery bezpieczeństwa danych, ale pozycje, o które zapyta każdy due-diligence.

---

## Status czterech znanych problemów (2026-06-02 → 2026-06-07)

| # | Problem z poprzedniego review | Status | Dowód w kodzie |
|---|---|---|---|
| 1 | **Critical** — brak sekretów = brak auth (wszystko przechodzi) | ✅ Zamknięte | `http_guard.py:123-147` — fail-closed 401 przy braku sekretów; dev-bypass `AW_INSECURE_NO_AUTH` twardo blokowany w produkcji (`:127`) |
| 2 | **High** — legacy `ARCHITEKT_API_KEY` nie ustawia `tenant_id` z JWT (cross-user leak) | ✅ Zamknięte | `http_guard.py:224-236` — legacy bearer **odrzucony 401**, gdy JWT aktywne; service-header wymaga `X-Tenant-Id` i `X-User-Id` (`:161-187`) |
| 3 | **High** — `POST /admin/trigger-followups` otwarty bez `ARCHITEKT_ADMIN_TOKEN` | ✅ Zamknięte | `admin.py:34-50` — `_require_admin` fail-closed (403 bez tokenu, 401 zły token), `hmac.compare_digest`; token wymagany w preflight (`settings.py:108`) |
| 4 | **High** — Tauri `security.csp: null` | ✅ Zamknięte | `tauri.conf.json:25-27` — pełna, restrykcyjna CSP (`object-src 'none'`, `base-uri 'self'`, jawna allowlista connect-src) |

Pozostałe medium z poprzedniego review również adresowane: token revocation (JTI blocklist w Redis, `auth_identity.py`), API keys we frontendzie (brak — JWT przez `tokenStorage`, web→sessionStorage), SSE reconnection (`useDebate.ts` — jeden bezpieczny retry chroniony przed duplikatem debaty).

---

## Mocne strony (co trzymać)

- **Defense-in-depth izolacji tenantów.** Trzy warstwy składają się poprawnie: (a) `http_guard` ustawia ContextVar z JWT `tenant_id`/`sub`; (b) `PgConnection.execute` ustawia transaction-local GUC `architekt.tenant_id` przed **każdym** query i **fail-closed `RuntimeError`** przy pustym tenant_id (`pg_wrap.py:139-159`); (c) RLS `FORCE ROW LEVEL SECURITY` + CHECK `tenant_id <> ''` w Postgresie (`0002_enable_rls.sql`).
- **Fail-fast startu produkcyjnego.** `production_preflight_errors()` blokuje start (`SystemExit`) bez Postgres/JWT/CORS/Redis/Anthropic/admin-token; brak cichego fallbacku SQLite w prod (`db/backend.py:135-139`).
- **Izolacja cache LLM per-user.** `_cache_key` (v8) wplata `tenant_id` + `user_id` w hash — zweryfikowane empirycznie (`scripts/verify_cache_isolation.py` → klucze rozdzielne). Zamyka subtelny wyciek odpowiedzi między userami jednego tenanta.
- **CI jako bramka, nie ozdoba.** Grep-gate blokujący raw `db.execute()` w handlerach (wymusza repo+tenant), `pip-audit`, `detect-secrets` po całej historii, coverage floor 75%, dedykowany krok weryfikacji izolacji cache. 76 plików testów, 10 wprost o tenant/RLS/auth.
- **Higiena sekretów.** `.env` w `.gitignore`, nigdy nie był commitowany; w repo tylko `.env.example`. Hasła: Argon2id z transparentną migracją z PBKDF2 (`auth.py:247-271`).
- **Rate limiting odporny na NAT/VPN** — keyed po JWT `sub` z fallbackiem na IP (`_rate_limit.py`).

---

## Znaleziska

### Critical
Brak. (Wszystkie wcześniejsze Critical zamknięte.)

### High
Brak nowych. Jeden punkt do świadomego potwierdzenia, nie bug:

| # | Plik | Opis | Rekomendacja |
|---|---|---|---|
| H-1 | `pg_wrap.py` / cała warstwa db | Gwarancja izolacji opiera się na tym, że **każdy** request-time query idzie przez `PgConnection.execute`. Każdy przyszły raw `_pg_pool.acquire()` poza `init_database` ominąłby GUC → przy pustym GUC RLS przepuszcza wszystko (`OR current_setting(...)=''`). | Utrzymać. CI grep-gate już to pilnuje dla `db.execute(`; rozważyć rozszerzenie gate o `_pg_pool.acquire(` poza `db/backend.py`. |

### Medium

| # | Plik | Opis | Rekomendacja |
|---|---|---|---|
| M-1 | `Dockerfile` | Kontener uruchamia uvicorn **jako root**, brak `USER`. | Dodać non-root user (`useradd` + `USER app`) — standardowe pytanie due-diligence. |
| M-2 | `Dockerfile` / compose | Jeden worker uvicorn, brak `--workers`/Gunicorn. Rate-limit i Redis są już multi-instance-ready, ale runtime nie skaluje. | Dla soft-launchu OK; przed sprzedażą skalowalną dodać `--workers` lub Gunicorn+UvicornWorker. |
| M-3 | `core/completion_enforcer.py:395-433` | `validate_syez_prose_completion_audit` to **regex po polskiej prozie** (klastry słów + czasownik akcji). Ryzyko false-negative/positive na naturalnym języku — może blokować poprawną syntezę albo przepuszczać niepełną. | Zgodne z notą projektu o ryzyku heurystyk. Trzymać próg konserwatywnie; rozważyć log telemetryczny trafień/pudeł zamiast twardego 422 na granicznych przypadkach. |
| M-4 | `auth_identity.py:45-54` `block_jti` | Przy braku Redis `block_jti` cicho nie robi nic (revoke = no-op), mimo że `revoke_token` zwraca `{"revoked": true}` jeśli Redis padł *po* sprawdzeniu. | W prod Redis jest wymagany (preflight), więc realnie niegroźne; dla spójności rozważyć zwrot `revoked:false` gdy `get_redis() is None`. |

### Low / Nits

- `auth.py /me` to placeholder zwracający hint zamiast danych usera — niespójne z resztą API (kosmetyka).
- `feedback.py` dev-fallback do JSONL zapisuje `tenant_id` do pliku poza RLS — tylko dev (prod = 503), ale warto pilnować, by `AW_FEEDBACK_DIR` nie trafił na współdzielony wolumen.
- CORS bez `allow_credentials` — poprawne (auth przez Bearer, nie cookie), ale udokumentować decyzję, by ktoś nie „naprawił" tego dodając cookie-auth bez przemyślenia.

---

## Weryfikacja empiryczna (w tej sesji)

- ✅ `scripts/verify_cache_isolation.py` — klucze cache user-A ≠ user-B, prefix `v8`. (Transport Redis nie sprawdzony — brak Redis w sandboxie.)
- ⚠️ `tests/test_stage1_security.py` — ERROR w sandboxie z powodu quirku fixture pytest-asyncio (nie błąd logiki).
- ⚠️ `tests/test_multiuser_isolation.py` — FAIL w sandboxie wyłącznie przez brak `aiosqlite`/Postgres (`ModuleNotFoundError`), nie przez wyciek. CI uruchamia je z pełnymi zależnościami.

> Uwaga: pełnego zestawu testów nie dało się uruchomić w tym środowisku (brak części zależności i brak Postgres/Redis). Werdykt opiera się na lekturze kodu + bramkach CI + jednym teście, który udało się wykonać. Przed wdrożeniem: `pytest tests/ --cov-fail-under=75` na maszynie z Postgres+Redis (tak jak robi CI).

---

## Werdykt

**Request Changes (drobne) — nie blokujące bezpieczeństwa danych.**

- **Desktop / single-user:** deployment-ready. CSP, device-binding, fail-closed auth są na miejscu.
- **Multi-user soft-launch (Postgres):** deployment-ready przy poprawnym ENV (start to wymusza). Izolacja tenantów ma trzy niezależne warstwy + testy.
- **Sprzedaż team/multi-tenant na skalę:** domknąć M-1 (non-root) i M-2 (workers) przed pełnym GA; to pozycje operacyjne, nie wycieki.

**Najmniejszy następny krok (60 min):** dodać `USER app` w `Dockerfile` (M-1) oraz rozszerzyć CI grep-gate o `_pg_pool.acquire(` poza `db/backend.py` (H-1). Obie zmiany są chirurgiczne i podnoszą posturę bez dotykania logiki Rady.
