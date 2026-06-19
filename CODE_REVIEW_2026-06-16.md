# Code Review — Architekt Wolności (2026-06-16)

**Zakres:** warstwa auth/izolacji od krawędzi po bazę, na tle review z 2026-06-02.
**Metoda:** przegląd statyczny kodu (nie działającego deploymentu).
**Pliki:** `api/http_guard.py`, `api/auth_identity.py`, `db/tenant.py`, `db/pg_wrap.py`,
`db/backend.py`, `db/migrations/0002_enable_rls.sql`, `0009_harden_rls_bypass.sql`,
`api/routers/admin.py`, `src/src-tauri/tauri.conf.json`, `src/src/hooks/useDebate.ts`,
`src/src/lib/apiAuth.ts`, `core/completion_enforcer.py`.

---

## Podsumowanie

Wszystkie cztery blokery z review 2026-06-02 są w kodzie **zamknięte**. Warstwa
izolacji jest egzekwowana mechanizmem (fail-closed + RLS w Postgresie), nie
konwencją „pamiętaj, żeby ustawić tenant przed query". Pozostałe znaleziska to
głównie poprawność w trybie multi-tenant oraz gotowość dystrybucyjna — nie wycieki
danych między użytkownikami.

---

## Status oryginalnych blokerów (2026-06-02)

| # | Problem | Status | Dowód |
|---|---------|--------|-------|
| 1 | 🔴 Brak sekretów = brak auth | ✅ Zamknięty | `http_guard.py:133-158` — fail-closed 401; `AW_INSECURE_NO_AUTH` zablokowany w prod (403) |
| 2 | 🟠 Legacy `ARCHITEKT_API_KEY` nie ustawia tenant_id → cross-user | ✅ Zamknięty | `http_guard.py:237-280` — odrzucany gdy JWT aktywne; bez `X-Tenant-Id` → 403 fail-closed |
| 3 | 🟠 Admin endpoint otwarty bez tokenu | ✅ Zamknięty | `admin.py:37-53` — `_require_admin` 403 gdy brak `ARCHITEKT_ADMIN_TOKEN` |
| 4 | 🟠 Tauri `csp: null` | ✅ Zamknięty | `tauri.conf.json:25-27` — pełne CSP, `object-src 'none'`, `base-uri 'self'` |
| 5 | 🟡 Token revocation / JTI | ✅ Zaadresowany | `auth_identity.py` — `jti` wymagany, blocklist Redis, fail-closed w prod |
| 6 | 🟡 RLS error handling | ✅ Zaadresowany | migracja `0009` + `pg_wrap.py:236-260` — pusty GUC nie otwiera policy, CHECK `tenant_id<>''` |
| 7 | 🟡 API key we froncie | ✅ Złagodzony | `apiAuth.ts:130-139` — prod ignoruje build-time klucz (nie inline'uje do bundle) |
| 8 | 🟡 SSE reconnection | ✅ Zaadresowany | `useDebate.ts:213-230` — 1 retry, tylko gdy `!receivedFirstEvent` (brak duplikatu debaty) |

**Dodatkowo dobrze rozwiązane**
- GUC `architekt.tenant_id` jest transaction-local i **parametryzowany**
  (`set_config(..., $1, true)` — brak SQL injection przez tenant_id).
- Brak cichego fallbacku na SQLite w produkcji (`backend.py:169-173`) — SQLite nie
  ma RLS, więc fallback maskowałby brak izolacji. Fail-closed.
- `qmarks_to_pg` w `pg_wrap.py` poprawnie pomija literały/dollar-quoting przy
  translacji placeholderów (brak psucia zapytań z `?` w treści).

---

## Pozostałe / nowe znaleziska

### A — Handlery admin działają jako `DEFAULT_TENANT` 🟡 Medium (poprawność, nie wyciek)
`http_guard.py:109-127` zwraca dla ścieżek admin/`/auth/`/public **przed**
ustawieniem ContextVar tenanta. Handlery admin idą więc przez normalne repo z
`tenant_id = 'default'`. `POST /admin/trigger-followups` i `/admin/rebuild-evolution`
operują **tylko na tenancie `default`**, nie na wszystkich.
- Single-tenant (obecny model): OK.
- Multi-tenant (team-plan): zadania batch po cichu pomijają pozostałych tenantów.
- **Działanie:** udokumentować ograniczenie; przed team-planem przeprojektować
  zadania admin tak, by iterowały tenantów jawnie (pętla + `set_current_tenant_id`).

### B — Buildy desktop niepodpisane 🟡 Medium (go-to-market, nie luka)
`tauri.conf.json:40,44` — `signingIdentity: null` (macOS), `certificateThumbprint: null`
(Windows). Bez podpisu + notaryzacji Apple instalka pokazuje ostrzeżenia, a Gatekeeper
blokuje uruchomienie. **Twarda blokada legalnej dystrybucji desktopa.** Patrz checklista
sprzedażowa.

### C — `migration_bypass` session-level 🔵 Low / Info
`backend.py:154-156` ustawia `migration_bypass='on'` jako session-level (`false`),
licząc na reset GUC przy zwrocie połączenia do puli asyncpg. Domyślnie asyncpg to
robi, ale zależność jest niejawna.
- **Działanie:** test integracyjny potwierdzający czysty GUC na kolejnym `acquire()`
  po migracjach.

### D — Tauri `shell.open: true` 🔵 Low (do weryfikacji)
`tauri.conf.json:47-51`. Zweryfikować zakres w `src/src-tauri/capabilities/default.json` —
`open` bez wąskiej allowlisty URL bywa wektorem, jeśli niezaufany string trafi do
`shell.open`.

### E — Heurystyka audytu domknięcia 🔵 Low (znany, poza tematem izolacji)
`completion_enforcer.py:12-13` — audyt domknięcia przeszedł z pola JSON na „prozę".
Detekcja prozą niesie ryzyko false negative/positive. Sama regex-detekcja nie była
przedmiotem tego przeglądu — wart osobnego spojrzenia.

---

## Werdykt

**Request Changes — ale blokery izolacji NIE są już blokerami.** Cztery
krytyczne/wysokie pozycje z 2026-06-02 zamknięte fail-closed. Znaleziska A–E są
niskiej/średniej wagi i nie dotyczą wycieku danych zdrowotnych między userami.

**Zastrzeżenia, zanim potraktujesz to jako „zielone":**
1. Przegląd dotyczy kodu, nie działającego deploymentu. Gwarancje zależą od runtime:
   Postgres (nie SQLite), ustawione `ARCHITEKT_JWT_SECRET` + `ARCHITEKT_ADMIN_TOKEN`,
   Redis w prod. Potwierdzić testem integracyjnym multi-user na realnym Postgresie.
2. Znalezisko A zamknąć **przed** wejściem team-planu.
3. Znalezisko B (podpisywanie) to blokada sprzedaży niezależna od bezpieczeństwa.
