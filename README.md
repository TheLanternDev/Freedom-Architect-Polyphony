# Architekt Wolności – Rada Nadzorcza „Mój Świat” (backend + Tauri UI)

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

## Frontend (Tauri / przeglądarka)

```bash
cd ui
npm install
npm run dev              # sam Vite — proxy API: VITE_API_URL=http://127.0.0.1:8000
npm run tauri:dev        # okno desktopowe Tauri (backend musi działać osobno)
```

Plik **`ui/.env`** trzyma sekrety i ustawienia wspólne dla UI i backendu: m.in. **`VITE_API_URL`** (adres FastAPI; domyślnie `http://localhost:8000`), **`ANTHROPIC_API_KEY`**, **`XAI_API_KEY`**. Python ładuje ten plik przy starcie (`env_bootstrap.py`); opcjonalnie drugi plik `.env` w korzeniu repo uzupełnia tylko puste klucze, albo ustaw **`AW_ENV_FILE`** na własną ścieżkę. Przy **`npm run build`** bez `VITE_API_URL`, frontend w produkcji używa pustego base URL — działa z API pod tą samą domeną.

### Jedna witryna: API + zbudowany React (`AW_SERVE_UI`)

Po `npm run build` w `ui/` ustaw `AW_SERVE_UI=1` i uruchom backend — FastAPI obsłuży `GET /` oraz `/assets/*` z `ui/dist` (jedna origin dla przeglądarki). Opcjonalnie `AW_UI_DIST=/ścieżka/do/dist`.

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
