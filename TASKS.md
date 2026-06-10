# Tasks

## Next

- [ ] **Doc: BFF musi sanityzować X-Tenant-Id / X-User-Id** - single-tenant honoruje nagłówki na bazie shared-key. (LOW)
- [ ] **Test prod path JTI fail-closed (P1-A3)** - `AW_ENV=production` + brak Redis → token z JTI odrzucony (kod jest, brakuje testu).
- [ ] **P1-A5: wymusić JWT na publicznym hoście** - `App.tsx` pozwala działać bez JWT gdy `aw_jwt_enabled != "1"`.
- [ ] **P1-E2: reset hasła / lifecycle konta** - przed otwarciem rejestracji na zewnątrz.
- [ ] **P1-E1: per-tenant metering kosztów** - `cost_log.jsonl` globalny, bez tenant_id (blokuje rozliczenia SaaS).
- [ ] **P1-C1/C2: coverage main.py + integracyjny job na żywym PG** - CI.
- [ ] **P2-C1: Vitest dla useDebate** - reconnect/retry guard (mock ReadableStream).

## Done

- [x] **P1-B1: Idempotency-Key dla POST /debate** (2026-06-10) - `api/idempotency.py` (Redis SET NX, fallback in-memory; klucz namespacowany tenant+user); guard w `/debate/stream` i `/debate/continue/stream` PRZED budżetem/DB; `useDebate` generuje klucz per logiczna debata (wspólny dla retry), 409 `duplicate_debate_request` bez panelu violation. Testy: `tests/test_idempotency_debate.py` (4/4).

- [x] **Code review + naprawy (2026-06-10)** - przywrócony `.gitignore` (usunięty w working tree — `.env` z sekretami była nieosłonięta!) + dodany `memory/`; regresja P0-2 domknięta od strony klienta (`apiAuth.ts` wysyła `X-Tenant-Id` na ścieżce legacy API key); maintenance Fazy 2 iteruje po wszystkich tenantach (wcześniej follow-upy dostawał tylko `default`); losowy `tenant_id` przy rejestracji (anty data-resurrection); refresh tokeny w Redis jako sha256 + reuse-detection (kill rodziny sesji) + odwrotny indeks per tenant; fix `rsplit` w dekodowaniu RT (refresh sesji demo odtwarzał zły sub/tenant); dummy Argon2-verify przy nieistniejącym userze (anty-enumeracja); `_ACTION_VERB` na poziom modułu.
- [x] **CSP bez `'unsafe-inline'` w script-src** (P2-A1) - tauri.conf.json; zweryfikowano brak inline scriptów w index.html/dist.
- [x] **Preflight: Redis wymagany w produkcji** - potwierdzone: `production_preflight_errors()` + `_production_startup_checks()` w main.py robią fail-fast (SystemExit) bez REDIS_URL.
- [x] **RLS: usunięto escape `OR current_setting(...)=''`** - 0002/0003/0004/0005/0007 + nowa migracja 0009 (re-aplikuje polityki na istniejących bazach); jawny bypass `architekt.migration_bypass='on'` ustawiany tylko przez runner migracji (db/backend.py). Runtime fail-closed.
- [x] **Atomowość pg_wrap** - dodano `transaction()` (PgConnection + oba `_Lite` SQLite); execute() reużywa otwartej transakcji; admin rebuild-evolution owinięty w `async with db.transaction()`. Domyślny execute() zostaje auto-commit (brak ryzyka długich tx w SSE).
- [x] **Hardening qmarks_to_pg** - skaner świadomy literałów `'...'`/`"..."`, dollar-quote i operatorów `?|`/`?&`; zwalidowane na przypadkach brzegowych.
- [x] **Code review warstwy auth/izolacja (2026-06-09)** - 4 krytyczne z 2026-06-02 potwierdzone jako domknięte (fail-closed no-secrets, legacy key odrzucony pod JWT, admin fail-closed, CSP ustawione).
