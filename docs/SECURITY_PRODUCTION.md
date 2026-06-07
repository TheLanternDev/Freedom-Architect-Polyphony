# Architekt Wolności — wdrożenie publiczne (bezpieczeństwo)

Ten dokument opisuje mechanizmy dodane, aby backend FastAPI mógł stać za publicznym reverse-proxy bez całkowicie otwartego dostępu do danych i kosztów LLM.

## Tożsamość i warstwy

| Mechanizm | Przeznaczenie |
|-----------|----------------|
| **JWT użytkownika** (`ARCHITEKT_JWT_SECRET`, opcjonalnie `ISS`/`AUD`) | Bearer `Authorization` z podpisem HS256 — `sub` (wymagane), opcjonalnie `tenant_id`. Sekret **nie** umieszczaj w bundle przeglądarki; token wydaje OAuth/OIDC lub Twój BFF po sesji. |
| **Nagłówek serwisowy BFF** (`ARCHITEKT_SERVICE_HEADER`, domyślnie `X-Architekt-Service-Key`) | Ten sam sekret co `ARCHITEKT_API_KEY`, ale dodawany **wyłącznie** przez zaufany proxy/BFF po zweryfikowaniu użytkownika. Na proxy **usuń** ten nagłówek z żądań przychodzących od klientów. |
| **Bearer `ARCHITEKT_API_KEY` (legacy)** | Nadal obsługiwany dla narzędzi operatorskich — **nie** przekazuj go z aplikacji SPA w produkcji. |

Publiczne bez auth (gdy skonfigurowano którykolwiek mechanizm powyżej): `GET /health`, `GET /health/ready`, `GET /` (SPA), `GET /assets/*`. Ścieżki OpenAPI są publiczne **tylko** poza produkcją lub gdy `AW_FORCE_OPENAPI=1`.

### Tenant

- Claim JWT `tenant_id` — logiczny separator najemców (pełna izolacja danych w DB wymaga osobnej migracji).
- `AW_REQUIRE_TENANT_JWT_CLAIM=1` — JWT bez `tenant_id` jest odrzucany.
- `AW_ENFORCE_TENANT_HEADER=1` — jeśli klient podaje `X-Tenant-Id` i JWT ma `tenant_id`, wartości muszą być zgodne (403).

### ADR-001: Model izolacji „tenant = user" (i ścieżka do team-planu)

**Status:** zaakceptowany · **Data:** 2026-06-06 · **Kontekst:** decyzja rozproszona dotąd w komentarzach (`db/tenant.py`, `api/http_guard.py`, `agents/base_agent.py::_cache_key`) — tu jest jej kanoniczny zapis.

**Decyzja.** W obecnym modelu **każdy użytkownik jest własnym tenantem**. Nie wspieramy jeszcze team-planu (wielu userów w jednym tenancie). Konsekwencje wynikają wprost z kodu:

- **Wyznaczanie tenanta.** `api/http_guard.py` ustawia ContextVar `tenant_id` = JWT claim `tenant_id`, z fallbackiem do `sub`. W produkcji `AW_REQUIRE_TENANT_JWT_CLAIM` jest domyślnie ON — JWT bez `tenant_id` jest odrzucany, by uniknąć kolizji `sub` między wydawcami.
- **RLS opiera się WYŁĄCZNIE na `tenant_id`.** Schemat ma kolumnę `tenant_id` per wiersz (nie `user_id`). Migracje `0001_add_tenant_isolation` + `0002_enable_rls` zakładają GUC `architekt.tenant_id` (ustawiany transaction-local w `db/pg_wrap.py`, fail-closed na pustym tenancie). Polityka `tenant_isolation` porównuje wiersz z tym GUC.
- **Cache LLM izolowany per `user_id` ORAZ `tenant_id`.** `BaseAgent._cache_key` (v8) zawiera oba ID. `user_id` (claim `sub`) ma sens nawet w przyszłym team-planie: różni userzy jednego tenanta mogą zadawać różne briefy, więc współdzielony klucz = wyciek odpowiedzi. Dlatego ścieżka BFF service-header **wymaga `X-User-Id`** (fail-closed) — patrz niżej.

**Niezmiennik bezpieczeństwa.** Dopóki obowiązuje ten model: `tenant_id` jest jedyną granicą trwałej izolacji danych, a `user_id` służy wyłącznie izolacji cache. **Nie** wolno wprowadzać współdzielenia tenanta między userami (np. fallback `user_id := tenant_id` w trybie multi-user) bez kroków z sekcji „Migracja" — inaczej userzy jednego tenanta zobaczą nawzajem swoje odpowiedzi/dane.

**Migracja do team-planu (gdy będzie potrzebny).** Kolejność, twardo wymagana zanim wpuścimy >1 usera do tenanta:

1. Dodaj kolumnę `user_id` do tabel z danymi osobistymi: `dreams`, `debates`, `projects`, `commitments` (i pochodnych z `tenant_id`).
2. Backfill `user_id` z istniejących danych (w modelu „tenant = user" `user_id := tenant_id`).
3. Nowa migracja RLS: rozszerz politykę o predykat `user_id = current_setting('architekt.user_id')` tam, gdzie dane są prywatne; zostaw tylko `tenant_id` tam, gdzie współdzielone w teamie. Ustawiaj GUC `architekt.user_id` analogicznie do `tenant_id` w `db/pg_wrap.py`.
4. `http_guard`: rozdziel `tenant_id` (z claim `tenant_id`) od `user_id` (z `sub`) — dziś oba mogą zbiegać się do `sub`.
5. Dopiero wtedy „moje" oddziela się od „współdzielone w teamie".

**Stan migracji DB (czerwiec 2026):** `0001`–`0006` zastosowane; `0006_users_revoke_public` zabiera domyślny `PUBLIC` grant na `users`. Team-plan = nowa migracja `0007+`, nie modyfikacja powyższych.

## Zmienne środowiskowe

| Zmienna | Wymagana | Opis |
|---------|----------|------|
| `ARCHITEKT_API_KEY` | Nie | Współdzielony sekret serwisu (legacy). Gdy ustawiony i/lub JWT — patrz middleware w `api/http_guard.py`. |
| `ARCHITEKT_JWT_SECRET` | Nie | Sekret HS256 dla tokenów użytkownika w nagłówku `Authorization: Bearer <jwt>`. |
| `ARCHITEKT_JWT_ISSUER` / `ARCHITEKT_JWT_AUDIENCE` | Nie | Opcjonalna walidacja `iss` / `aud`. |
| `ARCHITEKT_SERVICE_HEADER` | Nie | Nazwa nagłówka z kluczem serwisowym (BFF). Domyślnie `X-Architekt-Service-Key`. |
| `AW_ENV` | Nie | `production` — wyłącza `/docs`, `/redoc`, `/openapi.json` (chyba że `AW_FORCE_OPENAPI=1`). |
| `ARCHITEKT_ADMIN_TOKEN` | W produkcji **tak** | Bramkuje wszystkie trasy `/admin/*` (`api/routers/admin.py`: `trigger-followups`, `rebuild-evolution`) oraz `/metrics`. **Fail-closed**: brak tokenu → endpointy zwracają 403 (wyłączone), zły token → 401. |
| `AW_CORS_ORIGINS` | Nie | Lista originów zamiast `*`. |
| `AW_DISABLE_RATE_LIMIT` | Nie | Wyłącza SlowAPI (np. CI). |
| `AW_RATE_DEBATE_PER_MINUTE` | Nie | Limit `POST /debate/stream` na IP (5–120). |

Pełniejsza lista placeholderów: `.env.example`.

## Sekrety i CI

- Nie commituj `.env` — repozytorium ignoruje `.env*` z wyjątkiem `.env.example`.
- Produkcja: sekrety z Vault / sealed secrets / zmienne CI zaszyfrowane; rotacja kluczy wg polityki (JWT: krótki `exp`; po rotacji sekretu unieważnij stare tokeny).

## Frontend (Vite / Tauri)

- **Unikaj** `VITE_ARCHITEKT_API_KEY` w publicznym SPA — preferuj sesję → BFF → nagłówek serwisowy lub JWT krótkotrwały.
- Desktop (Tauri): sekret w bundlu nadal ekspozycją — rozważ osobny kanał lub proxy lokalny.

## Reverse proxy

1. Wymuś TLS.
2. Wstrzykuj `Authorization` lub nagłówek serwisowy **po stronie serwera**, nie z przeglądarki.
3. Ogranicz rozmiar body i timeouty na `/debate/stream`.
4. Endpoint administracyjny: osobna sieć / VPN / allowlist IP (`POST /admin/trigger-followups`).

## Limity zapytań API

- `GET /history`: `limit` ∈ [1, 200], `q` obcięte do 500 znaków.
- `GET /commitments/due`: `within_hours` ∈ [1, 8760].
- `GET /dreams`: `limit` ∈ [1, 100].

## Eksport PDF

- Endpoint: `GET /debate/{id}/export.pdf`.
- Font: `core/fonts/DejaVuSans.ttf` (pakiet DejaVu 2.37, patrz `core/fonts/SOURCE.txt`).

## Zgodność

- Szablon pod RODO i dostawców LLM: `docs/COMPLIANCE_PRIVACY.md`.
