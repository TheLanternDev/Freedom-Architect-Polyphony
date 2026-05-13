# Instalacja lokalna (model A — BYOK)

Krótka ścieżka „od repozytorium do działającego API + UI”. Szczegóły endpointów: `README.md`, kontrakt: `SPEC_CURRENT.md`.

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

Skonfiguruj **`ui/.env`** (ładuje go też backend przez `env_bootstrap.py`), min.:

```env
ANTHROPIC_API_KEY=sk-ant-...
VITE_API_URL=http://127.0.0.1:8000
```

Opcjonalnie: `REDIS_URL`, `ARCHITEKT_DB_PATH` (domyślnie `data/architekt.db`), `DAILY_BUDGET_USD`, `AW_CORS_ORIGINS`.

Uruchomienie:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Sprawdzenie: `GET http://127.0.0.1:8000/health` → `200`, pole `status`: `alive`.

**Nie wystawiaj** tego procesu na publiczny internet bez reverse proxy i uwierzytelnienia — endpointy nie są zaprojektowane pod anonimowy dostęp z sieci.

## 2. UI (przeglądarka)

```bash
cd ui
npm install
npm run dev
```

Otwórz URL z konsoli Vite; API musi być na `VITE_API_URL`.

## 3. UI (Tauri — desktop)

```bash
cd ui
npm install
npm run tauri:dev
```

Backend jak w §1 musi działać równolegle (Tauri domyślnie woła `http://127.0.0.1:8000`).

### Build instalacyjny (founders)

```bash
cd ui
npm ci
npm run tauri:build
```

Artefakty platformowe w `ui/src-tauri/target/release/bundle/`. Podpis binarek (Apple / Microsoft) załatwiasz we własnym pipeline — poza zakresem tego pliku.

## 4. Jedna origin (opcjonalnie)

Po `npm run build` w `ui/`: ustaw `AW_SERVE_UI=1`, uruchom `uvicorn` — statyczny frontend z `ui/dist` pod tym samym hostem co API (`README.md`).

## 5. Dane i backup

- Baza SQLite: domyślnie **`data/architekt.db`** (katalog względem cwd przy starcie uvicorn).
- Kopia zapasowa = skopiuj ten plik przy zamkniętej aplikacji lub w przerwie w zapisie.
- Koszty LLM (jeśli włączone): `cost_log.jsonl` — ścieżka z `COST_LOG_PATH` lub domyślna w repo (`README.md`).

**Skrót:** bez kopii pliku bazy **nie odzyskasz** historii debat po utracie dysku lub odinstalowaniu katalogu danych.

## 6. Pierwsze uruchomienie (UI)

Po uruchomieniu Tauri / Vite: przycisk **Połączenie** w nagłówku — **Test /health**, opcjonalnie zmiana adresu API (nadpisanie w `localStorage` w przeglądarce). Klucz Anthropic **nadal tylko** w `ui/.env` na maszynie z backendem.

## 7. Bezpieczeństwo i support (model lokalny)

- [`docs/SECURITY_LOCAL.md`](docs/SECURITY_LOCAL.md) — sekrety, sieć, telemetria, backup.
- [`docs/SUPPORT_PLAYBOOK.md`](docs/SUPPORT_PLAYBOOK.md) — szablony odpowiedzi dla kanału supportu.

## 8. Smoke przed wydaniem / wysyłką binarki

```bash
./scripts/smoke_week1.sh
```

Bez wywołań sieciowych do modeli — tylko testy jednostkowe.
