# Tasks

## Next

- [ ] **Doc: BFF musi sanityzować X-Tenant-Id / X-User-Id** - single-tenant honoruje nagłówki na bazie shared-key. (LOW)
- [ ] **P1-C1/C2: coverage main.py + integracyjny job na żywym PG** - CI.
- [ ] **P2-C1: Vitest dla useDebate** - reconnect/retry guard (mock ReadableStream).

## Done

- [x] **Bramka B — gotowość handlowa (2026-06-11)** - (1) P1-E1: `build_cost_entry` dopisuje `tenant_id` z ContextVar (lazy import, defensywnie — log kosztów nie wywraca ścieżki LLM); 2 testy w `test_cost_budget.py`; agregacja per-tenant możliwa offline z JSONL, warstwa billingowa = P0-E1 (N/A dla BYOK). (2) P1-E3 i P2-E2 zweryfikowane jako już zamknięte w plikach (compliance wypełnione pod model A/BYOK; cena 149 EUR + PRICING.md) — audyt zaktualizowany.
- [x] **Bramka A — multi-user hardening (2026-06-11)** - (1) P1-A5: `/health` zwraca `auth_required` (serwer = źródło prawdy), `App.tsx` wymusza ekran logowania gdy backend ma JWT a klient nie ma tokenu — lokalna flaga `aw_jwt_enabled` przestała decydować; (2) P1-A3: 2 testy prod fail-closed JTI (brak Redis + błąd Redis) w `tests/test_auth_identity_unit.py` — 24/24 pass; (3) P1-E2 (minimalny, BYOK): `POST /admin/users/password-reset-token` (za `_require_admin`, sha256 tokenu w Redis, TTL 30 min, fail-closed 503 bez Redis) + `POST /auth/password-reset/confirm` (GETDEL single-use, generyczny 401 anty-enumeracja, Argon2, kill refresh tokenów tenanta, rate-limit 5/min); (4) P2-E1 potwierdzone jako już zamknięte (`import.meta.env.DEV`). Pełny e-mailowy self-service reset = osobny task przed otwartą rejestracją.

- [x] **P1-B1: Idempotency-Key dla POST /debate** (2026-06-10) - `api/idempotency.py` (Redis SET NX, fallback in-memory; klucz namespacowany tenant+user); guard w `/debate/stream` i `/debate/continue/stream` PRZED budżetem/DB; `useDebate` generuje klucz per logiczna debata (wspólny dla retry), 409 `duplicate_debate_request` bez panelu violation. Testy: `tests/test_idempotency_debate.py` (4/4).

- [x] **Code review + naprawy (2026-06-10)** - przywrócony `.gitignore` (usunięty w working tree — `.env` z sekretami była nieosłonięta!) + dodany `memory/`; regresja P0-2 domknięta od strony klienta (`apiAuth.ts` wysyła `X-Tenant-Id` na ścieżce legacy API key); maintenance Fazy 2 iteruje po wszystkich tenantach (wcześniej follow-upy dostawał tylko `default`); losowy `tenant_id` przy rejestracji (anty data-resurrection); refresh tokeny w Redis jako sha256 + reuse-detection (kill rodziny sesji) + odwrotny indeks per tenant; fix `rsplit` w dekodowaniu RT (refresh sesji demo odtwarzał zły sub/tenant); dummy Argon2-verify przy nieistniejącym userze (anty-enumeracja); `_ACTION_VERB` na poziom modułu.
- [x] **CSP bez `'unsafe-inline'` w script-src** (P2-A1) - tauri.conf.json; zweryfikowano brak inline scriptów w index.html/dist.
- [x] **Preflight: Redis wymagany w produkcji** - potwierdzone: `production_preflight_errors()` + `_production_startup_checks()` w main.py robią fail-fast (SystemExit) bez REDIS_URL.
- [x] **RLS: usunięto escape `OR current_setting(...)=''`** - 0002/0003/0004/0005/0007 + nowa migracja 0009 (re-aplikuje polityki na istniejących bazach); jawny bypass `architekt.migration_bypass='on'` ustawiany tylko przez runner migracji (db/backend.py). Runtime fail-closed.
- [x] **Atomowość pg_wrap** - dodano `transaction()` (PgConnection + oba `_Lite` SQLite); execute() reużywa otwartej transakcji; admin rebuild-evolution owinięty w `async with db.transaction()`. Domyślny execute() zostaje auto-commit (brak ryzyka długich tx w SSE).
- [x] **Hardening qmarks_to_pg** - skaner świadomy literałów `'...'`/`"..."`, dollar-quote i operatorów `?|`/`?&`; zwalidowane na przypadkach brzegowych.
- [x] **Code review warstwy auth/izolacja (2026-06-09)** - 4 krytyczne z 2026-06-02 potwierdzone jako domknięte (fail-closed no-secrets, legacy key odrzucony pod JWT, admin fail-closed, CSP ustawione).
