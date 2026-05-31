# Architekt Wolności – Rada Nadzorcza „Mój Świat” (backend + Tauri UI)

**Dla użytkownika (czym to jest, jak używać, czego unikać):** [`USER_README.md`](USER_README.md)

**Instalacja lokalna (model founders / BYOK):** [`INSTALL.md`](INSTALL.md) · **dokumentacja:** [`docs/README.md`](docs/README.md) · kontrakt: [`docs/spec/SPEC_CURRENT.md`](docs/spec/SPEC_CURRENT.md) · oferta: [`docs/FOUNDERS_OFFER.md`](docs/FOUNDERS_OFFER.md) · bezpieczeństwo lokalne: [`docs/SECURITY_LOCAL.md`](docs/SECURITY_LOCAL.md) · support: [`docs/SUPPORT_PLAYBOOK.md`](docs/SUPPORT_PLAYBOOK.md) · smoke: `./scripts/smoke_week1.sh`

Silnik FastAPI (SSE, SQLite, Redis opcjonalnie) oraz aplikacja **Tauri v2 + React 19 + Vite + Tailwind** zgodnie ze specyfikacją MVP v1.1 (historia debat, strukturalna synteza Syeza, zobowiązania, alert budżetu LLM).

## Wymagania

- Python 3.12+ (w projekcie często używany jest venv z Pythonem 3.13 — kompatybilny)
- Node.js + npm (frontend)
- Opcjonalnie: Redis lokalnie, `ANTHROPIC_API_KEY` dla prawdziwych wywołań modeli

## Backend

```bash
cd /Users/tpltd145/Projects/architekt-wolnosci
source venv/bin/activate
pip install -r requirements.txt   # jeśli jeszcze nie
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Migracje bazy

Dwa backendy, dwa mechanizmy — oba uruchamiane automatycznie przy starcie (`init_db`):

- **SQLite** (domyślnie): migracje w kodzie (`db/connection.py`, funkcje `_migrate_*`), idempotentne `ALTER`/`CREATE IF NOT EXISTS`.
- **PostgreSQL** (`DATABASE_URL`): `db/schema_postgres.sql` to *current desired state* (tylko `CREATE ... IF NOT EXISTS` — **nie** zmienia istniejących tabel). Zmiany strukturalne na działających bazach idą przez wersjonowane pliki `db/migrations/*.sql`, śledzone w tabeli `schema_migrations`.

Każda strukturalna zmiana w `schema_postgres.sql` **musi** mieć odpowiadającą migrację w `db/migrations/`, inaczej istniejące bazy jej nie dostaną.

**Dodanie nowej migracji:** utwórz plik `db/migrations/NNNN_opis.sql` (kolejny numer), wyłącznie idempotentny SQL (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE/INDEX IF NOT EXISTS`, bloki `DO $$ ... $$` z warunkami). Plik wykonywany jest w transakcji jako całość.

**Uruchomienie:**

```bash
# Dev i produkcja — migracje aplikują się same przy starcie aplikacji:
DATABASE_URL=postgresql://user:pass@host/db uvicorn main:app
# (schema_migrations rejestruje wykonane wersje; ponowny start nie powtarza ich)
```

Nowa baza dostaje pełny schemat od razu (schema), a tracking w `schema_migrations` i tak oznacza migracje jako wykonane przy pierwszym przebiegu. Przed produkcyjnym deployem zrób backup bazy — migracje strukturalne są idempotentne, ale backup to standard.

### Architektura (v3.3+)

`main.py` pełni rolę routera FastAPI — logika biznesowa jest wydzielona do modułów w `api/services/`:

| Moduł | Odpowiedzialność |
|-------|-----------------|
| `api/services/debate_orchestrator.py` | Orkiestracja SSE: agenci → Syez → audyt → zapis |
| `api/services/dream_service.py` | Faza A0: destylacja marzenia + zapis DB |
| `api/services/completion_service.py` | AKSJOMAT 2: stale nudges, follow-upy, limit projektów |
| `api/services/budget_guard.py` | Twardy budżet LLM (402) + warning SSE |
| `api/services/project_service.py` | CRUD projektów, complete, archive, enrichment |
| `api/services/_sse.py` | Shared SSE helper |

Rdzeń domenowy: `core/` (dream_architect, completion_enforcer, safety, live_tensions). Persistencja: `db/` (repo pattern, SQLite/Postgres).

> Refaktoryzacja modularna jest w toku (v3.3+). Docelowo main.py → czysto routing, zero logiki biznesowej.

### Endpointy MVP v1.1 (wybrane)

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| POST | `/debate/stream` | SSE: marzenie → agenci → Syez → zapis |
| GET | `/history` | Ostatnie debaty + opcjonalne `q` (wyszukiwanie) |
| GET | `/debate/{id}` | Głosy + synteza + JSON strukturalny |
| GET | `/debate/{id}/export.md` | Eksport Markdown |
| GET | `/debate/{id}/export.pdf` | Eksport PDF |
| POST | `/commitment` | Zapis zobowiązania powiązanego z debatą |

**Alarm kosztów:** ustaw `DAILY_BUDGET_USD` (np. `0.5`). Gdy suma dzisiejszych wpisów w `data/cost_log.jsonl` (UTC; `COST_LOG_PATH` nadpisuje lokalizację) ≥ próg, pierwszy event SSE to `budget_warning` (debata i tak trwa).

**Publiczna produkcja:** opcjonalny klucz HTTP `ARCHITEKT_API_KEY` (Bearer na API), token `ARCHITEKT_ADMIN_TOKEN` dla `/admin/trigger-followups`, rate limit debat (`AW_RATE_DEBATE_PER_MINUTE`) — szczegóły: [`docs/SECURITY_PRODUCTION.md`](docs/SECURITY_PRODUCTION.md).

**Demo interaktywne (wersja próbna z własnym briefem):** [`docs/DEMO.md`](docs/DEMO.md) — `AW_DEMO_MODE=1`, sesje gościa `/auth/demo`, limity debat.

## Frontend (Tauri / przeglądarka)

```bash
cd src
npm install
npm run dev              # sam Vite — proxy API: VITE_API_URL=http://127.0.0.1:8000
npm run tauri:dev        # okno desktopowe Tauri (backend musi działać osobno)
```

Plik **`src/.env`** trzyma sekrety i ustawienia wspólne dla UI i backendu: m.in. **`VITE_API_URL`** (adres FastAPI; domyślnie `http://localhost:8000`), **`ANTHROPIC_API_KEY`**, **`XAI_API_KEY`**. Python ładuje ten plik przy starcie (`env_bootstrap.py`); opcjonalnie drugi plik `.env` w korzeniu repo uzupełnia tylko puste klucze, albo ustaw **`AW_ENV_FILE`** na własną ścieżkę. Przy **`npm run build`** bez `VITE_API_URL`, frontend w produkcji używa pustego base URL — działa z API pod tą samą domeną.

### Jedna witryna: API + zbudowany React (`AW_SERVE_UI`)

Po `npm run build` w `src/` ustaw `AW_SERVE_UI=1` i uruchom backend — FastAPI obsłuży `GET /` oraz `/assets/*` z `src/dist` (jedna origin dla przeglądarki). Opcjonalnie `AW_UI_DIST=/ścieżka/do/dist`.

Stripe/sign-in nie są w kodzie — ten punkt to fundament wdrożenia web bez osobnego serwera plików.

## Testy

```bash
pytest -q
./scripts/smoke_week1.sh   # to samo przez venv; przed paczką founders
```

## Skrypty pomocnicze

- `python3 scripts/cost_dashboard.py` — podsumowanie kosztów z domyślnego logu (`data/cost_log.jsonl` lub `COST_LOG_PATH`; także `--today`, `--all`, `--brief HASH`).
- `python3 scripts/run_acb.py` — szybki smoke równoległych głosów + dashboard + synteza (dev).

## Strona marketingowa (Polyphony)

Statyczna witryna w katalogu `polyphony-site/` (`vercel.json`, `index.html`, `en.html`, …). W Vercelu ustaw **Root Directory** na `polyphony-site`, żeby nie duplikować plików w głównym katalogu repo.

## Projekt poboczny

`extras/wolny_rynek_mvp` — osobny pakiet Python (automatyzacja marketingu); nie jest importowany przez backend Rady.

## v3.0 Performance (legacy)

Benchmark `full_synthesis()` — historyczne wyniki w `data/benchmark_results.json` (opcjonalnie); po podłączeniu LLM czasy rosną proporcjonalnie do modeli.
