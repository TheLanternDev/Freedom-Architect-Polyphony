# Code Review — Freedom Architect: Polyphony

**Data:** 2026-06-05
**Zakres:** Pełny przegląd codebase (auth, izolacja tenantów, orkiestracja, agenci, frontend, Tauri)
**Kontekst:** Weryfikacja statusu issues z code review 2026-06-02 + nowe znaleziska

---

## Podsumowanie

Postawa bezpieczeństwa **znacząco się poprawiła** od 2026-06-02. Cztery z pięciu krytycznych/wysokich issues z poprzedniego review są **zamknięte**: open-API path, legacy-key tenant isolation, admin token hardening i Tauri CSP. Warstwa auth (JWT HS256, Argon2id, refresh rotation, JTI revoke), izolacja tenantów (ContextVar + RLS Postgres + filtr `tenant_id` w każdym query repo) oraz orkiestracja SSE (cancel przy rozłączeniu, guard przeciw duplikatom debat) są dojrzałe i spójne z filozofią projektu.

Pozostałe znaleziska to głównie **latentne ryzyka do zachowania** (nie aktywne bugi) oraz drobne sugestie. Brak nowych krytycznych luk.

**Werdykt: Approve z uwagami.** Bezpieczne do dalszej pracy nad polyphonią; pilnować trzech latentnych ryzyk poniżej przy refaktorach.

---

## Status issues z 2026-06-02

| # | Issue | Severity (wtedy) | Status teraz | Dowód |
|---|-------|------------------|--------------|-------|
| 1 | Brak auth gdy brak sekretów (open API) | 🔴 Critical | ✅ **Zamknięte** | `http_guard.py:78-102` — fail-closed 401 gdy brak `api_key` i `jwt`; dev-bypass `AW_INSECURE_NO_AUTH` blokowany w produkcji |
| 2 | Legacy `ARCHITEKT_API_KEY` nie ustawia `tenant_id` z JWT → cross-user leak | 🟠 High | ✅ **Zamknięte** | `http_guard.py:165-177` — legacy bearer **odrzucany** gdy JWT aktywne; service-header w trybie multi-user wymaga `X-Tenant-Id` (`:116-128`) |
| 3 | Admin endpoint otwarty bez `ARCHITEKT_ADMIN_TOKEN` | 🟠 High | ✅ **Zamknięte** | `settings.py:108-112` — admin token wymagany **zawsze** w produkcji (usunięto wyjątek `not demo`); endpointy `/admin/*` mają self-auth fail-closed (`http_guard.py:43-49`) |
| 4 | Tauri `security.csp: null` | 🟠 High | ✅ **Zamknięte** | `tauri.conf.json:25-27` — pełna CSP: `default-src 'self'`, `object-src 'none'`, `base-uri 'self'` |
| 5 | Token revocation / JTI, RLS errors, API key we froncie, SSE reconnect | 🟡 Medium | ✅ **W większości zamknięte** | JTI blocklist fail-closed w prod (`auth_identity.py:14-42`); API key build-time tylko w DEV (`apiAuth.ts:94-103`); SSE retry z guardem (`useDebate.ts:190-207`) |

---

## Pozostałe znaleziska

### Latentne ryzyka (zachować przy refaktorach — nie aktywne bugi)

| # | Plik | Linia | Ryzyko | Severity |
|---|------|-------|--------|----------|
| L1 | `db/pg_wrap.py` | 146-159 | **Współdzielone połączenie asyncpg pod współbieżnością.** Każdy `execute` opakowuje query w `async with self._c.transaction()` z GUC transaction-local. asyncpg connection **nie jest concurrency-safe** — gdyby kiedyś dwa taski równolegle robiły DB-calls na tym samym `db`, transakcje by się zazębiły (błąd lub interleaving GUC → potencjalny cross-tenant). Dziś **bezpieczne**, bo `_phase_council` (`debate_orchestrator.py:463`) odpala równolegle tylko `acontribute` (czysty LLM, bez `db`); wszystkie operacje DB są sekwencyjne. | 🟡 Medium (latentne) |
| L2 | `db/migrations/0002_enable_rls.sql` | 53-60 | **RLS escape-hatch `current_setting(...) = ''`.** Pusty GUC przepuszcza wszystkie wiersze (potrzebne dla DDL/seed). `pg_wrap` już chroni to fail-closed (`:139-144` rzuca gdy pusty `tenant_id`), więc realnie nieosiągalne z warstwy HTTP — ale każdy nowy raw-SQL path omijający `PgConnection.execute` reaktywuje tę dziurę. | 🟡 Medium (latentne) |
| L3 | `api/http_guard.py` | 66-73 | **ContextVar nie jest resetowany w `finally`** (świadoma decyzja — reset przed wyprodukowaniem chunków SSE zepsułby strumień). Bezpieczne, bo guard ustawia `DEFAULT_TENANT`/`DEFAULT_USER` na **początku każdego requestu** (`:72-73`) zanim rozgałęzi auth — więc stała wartość poprzednika nie może wyciec. Zależność jest jednak niejawna: gdyby ktoś przesunął te dwa `set_*` poniżej rozgałęzień, pojawiłby się leak. Warto dodać test regresyjny. | 🟢 Low (latentne) |

### Sugestie (jakość / robustness)

| # | Plik | Linia | Sugestia | Kategoria |
|---|------|-------|----------|-----------|
| S1 | `api/routers/auth.py` | 251-260 | `check_needs_rehash` w bloku `try/except: pass` — cichy fail przy re-hashu Argon2 jest OK, ale warto zalogować `debug`, żeby nie maskować systemowego problemu z argon2-cffi. | Maintainability |
| S2 | `api/routers/auth.py` | 204 | `tenant_id = sha256(username)[:16]` — 64-bitowa przestrzeń. Kolizja username→tenant jest astronomicznie mało prawdopodobna, ale przy modelu „tenant == user" kolizja = **współdzielenie danych**. Rozważ pełne 32 znaki lub UNIQUE constraint na `tenant_id`. | Security (defensive) |
| S3 | `db/connection.py` | 414-427 | Repo metody na ścieżce SQLite polegają wyłącznie na `WHERE tenant_id = ?` (brak RLS w SQLite — świadome). Spójne i poprawne we wszystkich ~40 metodach, które sprawdziłem. Zero raw-SQL bez filtra tenanta. Brak akcji — odnotowane jako pozytyw. | — |
| S4 | `api/services/debate_orchestrator.py` | 19, 740 | `_background_tasks` (analytics, webhooki) jako fire-and-forget set — poprawnie trzymane referencje + `discard` callback (brak GC-cancellation). Dobre. Rozważ tylko bounded limit, żeby burst nie urósł w nieskończoność. | Performance (minor) |

---

## Co wygląda dobrze (pozytywy)

- **Izolacja cache LLM per user+tenant** (`base_agent.py:509-537`) — klucz `llm:v8` zawiera `tenant_id` i `user_id`; eliminuje cross-user wyciek odpowiedzi z Redisa przy wspólnym prefiksie briefu. Komentarz wprost tłumaczy zagrożenie.
- **Migracja haseł PBKDF2 → Argon2id transparentnie przy logowaniu** (`auth.py:261-271`) — bez wymuszania resetu, z `compare_digest`.
- **RLS `FORCE ROW LEVEL SECURITY`** (`0002:48`) — enforce nawet dla owner-roli aplikacji; defense-in-depth ponad warstwą repo.
- **SSE resilience** — cancel tasków LLM przy rozłączeniu klienta (`debate_orchestrator.py:494-509`), żeby nie palić tokenów Anthropic; ręczny UTF-8 decode obchodzący bug WebKit/Tauri 2 (`useDebate.ts:158-189`); retry z guardem `receivedFirstEvent` przeciw duplikacji debat.
- **Brak PII w logach i odpowiedziach błędów** — orchestrator loguje tylko typ wyjątku + tenant_id; klient SSE dostaje `error_type`, nigdy `str(e)` (`debate_orchestrator.py:772-779`).
- **Integralność głosów Rady** — uszkodzony/timeoutowany głos agenta NIE trafia do Syeza jako pełnoprawny i degradacja jest widoczna w UI (`agent_error` SSE) — zgodne z AKSJOMATEM 1.

---

## Domknięcie (najmniejszy następny ruch)

Jeśli chcesz zamknąć latentne ryzyka jednym ruchem ≤60 min: **dodaj test regresyjny dla L3** — dwa kolejne requesty na jednym worker-loopie (pierwszy z JWT tenant A, drugi anonimowy/inny), asercja że drugi nie widzi `tenant_id` pierwszego. To zamraża niejawną zależność z `http_guard.py:72-73` w teście, więc przyszły refaktor nie reaktywuje wycieku po cichu.
