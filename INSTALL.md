# Instalacja lokalna (model A — BYOK)

Krótka ścieżka „od repozytorium do działającego API + UI”. Szczegóły endpointów: `README.md`, kontrakt: `docs/spec/SPEC_CURRENT.md` (skrót w korzeniu: `SPEC_CURRENT.md`).

**Beta Windows (przeglądarka):** [`docs/BETA_TESTER_WINDOWS.md`](docs/BETA_TESTER_WINDOWS.md) · skrót: `CZYTAJ_MNIE.txt`

## Wymagania

- Python 3.12+ (w repo często 3.13 w `venv/`)
- Node.js + npm (UI / Tauri)
- **Własny** `ANTHROPIC_API_KEY` (Ty jesteś płatnikiem u Anthropic)
- Redis — opcjonalny (cache; bez niego aplikacja działa w trybie bez cache)

## 1. Backend

```bash
git clone <repo-url> architekt-wolnosci
cd architekt-wolnosci
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Skonfiguruj **`src/.env`** (ładuje go też backend przez `env_bootstrap.py`), min.:

```env
ANTHROPIC_API_KEY=sk-ant-...
ARCHITEKT_JWT_SECRET=<losowy-ciąg-min-32-znaki>
VITE_API_URL=http://127.0.0.1:8000
```

Szablon: `env/src.env.example` lub `src/.env.example`. Rejestracja/logowanie wymaga `ARCHITEKT_JWT_SECRET`.

Opcjonalnie: `REDIS_URL`, `ARCHITEKT_DB_PATH` (domyślnie `data/architekt.db`), `DAILY_BUDGET_USD`, `AW_CORS_ORIGINS`.

### Tryb w pełni lokalny (Ollama)

Bez wysyłania promptów do dostawców chmurowych — LLM działa na Twojej maszynie przez [Ollama](https://ollama.com):

1. Zainstaluj Ollama (macOS / Linux / Windows — instrukcja na stronie projektu).
2. Pobierz model, np. `ollama pull llama3.3:70b`.
3. Upewnij się, że serwer działa (`ollama serve` — na wielu systemach startuje automatycznie).
4. W **`src/.env`** (bez `ANTHROPIC_API_KEY` / `XAI_API_KEY`):

```env
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.3:70b
OLLAMA_MODEL_FAST=llama3.2:3b
```

Opcjonalnie: ustaw tylko `OLLAMA_BASE_URL` (bez kluczy chmurowych) — przy `LLM_BACKEND=auto` backend wybierze Ollama.

**Uwaga:** w tym trybie dane debaty i marzeń nie opuszczają komputera w kierunku Anthropic ani xAI (koszt LLM w logu = 0).

Uruchomienie:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Windows (skrypt):** `.\scripts\windows\start-backend.ps1`

Sprawdzenie: `GET http://127.0.0.1:8000/health` → `200`, pole `status`: `alive`.

**Nie wystawiaj** tego procesu na publiczny internet bez reverse proxy i uwierzytelnienia — endpointy nie są zaprojektowane pod anonimowy dostęp z sieci.

## 2. UI (przeglądarka)

```bash
cd src
npm install
npm run dev
```

**Windows (skrypt):** `.\scripts\windows\start-ui.ps1` (z katalogu głównego repo)

Otwórz URL z konsoli Vite; API musi być na `VITE_API_URL`.

## 3. UI (Tauri — desktop)

```bash
cd src
npm install
npm run tauri:dev
```

Backend jak w §1 musi działać równolegle (Tauri domyślnie woła `http://127.0.0.1:8000`).

### Build instalacyjny (founders)

```bash
cd src
npm ci
npm run tauri:build
```

Artefakty platformowe w `src/src-tauri/target/release/bundle/`. Podpis binarek (Apple / Microsoft) załatwiasz we własnym pipeline — poza zakresem tego pliku.

## 4. Jedna origin (opcjonalnie)

Po `npm run build` w `src/`: ustaw `AW_SERVE_UI=1`, uruchom `uvicorn` — statyczny frontend z `src/dist` pod tym samym hostem co API (`README.md`).

## 5. Dane i backup

- Baza SQLite: domyślnie **`data/architekt.db`** (katalog względem cwd przy starcie uvicorn).
- Kopia zapasowa = skopiuj ten plik przy zamkniętej aplikacji lub w przerwie w zapisie.
- Koszty LLM (jeśli włączone): domyślnie **`data/cost_log.jsonl`** — nadpisz `COST_LOG_PATH`, jeśli trzymasz log gdzie indziej (np. stary plik `cost_log.jsonl` w korzeniu repo).

**Skrót:** bez kopii pliku bazy **nie odzyskasz** historii debat po utracie dysku lub odinstalowaniu katalogu danych.

## 6. Pierwsze uruchomienie (UI)

Po uruchomieniu Tauri / Vite: przycisk **Połączenie** w nagłówku — **Test /health**, opcjonalnie zmiana adresu API (nadpisanie w `localStorage` w przeglądarce). Klucz Anthropic **nadal tylko** w `src/.env` na maszynie z backendem.

## 7. Bezpieczeństwo i support (model lokalny)

- [`docs/SECURITY_LOCAL.md`](docs/SECURITY_LOCAL.md) — sekrety, sieć, telemetria, backup.
- [`docs/SUPPORT_PLAYBOOK.md`](docs/SUPPORT_PLAYBOOK.md) — szablony odpowiedzi dla kanału supportu.

## 8. Struktura backendu (v3.3+)

```
main.py                         ← routing FastAPI (thin wrappers)
api/services/
  debate_orchestrator.py        ← orkiestracja SSE debaty
  dream_service.py              ← faza A0 (destylacja marzenia)
  completion_service.py         ← AKSJOMAT 2 (stale, follow-upy)
  budget_guard.py               ← twardy budżet LLM
  project_service.py            ← CRUD projektów
  _sse.py                       ← shared SSE helper
core/                           ← logika domenowa (bez HTTP)
db/                             ← persistencja (repo pattern)
agents/                         ← 9 agentów + Syez
```

> Refaktoryzacja modularna w toku (v3.3+). Pełna specyfikacja: [`docs/spec/SPEC_CURRENT.md`](docs/spec/SPEC_CURRENT.md).

## 9. Smoke przed wydaniem / wysyłką paczki beta

```bash
python -m pytest tests/ -q
./scripts/pack-founders-archive.sh          # BYOK — bez klucza
make pack-sponsor                           # beta — klucze zakodowane w config/sponsor_payload.py (nie w .env)
```

Bez wywołań sieciowych do modeli — tylko testy jednostkowe + AKSJOMATY v3.3.

**Paczka sponsorowana** — klucze nie trafiają do `src/.env`; są w generowanym `config/sponsor_payload.py`. Nie commituj archiwum.
