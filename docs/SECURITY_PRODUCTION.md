# Architekt Wolności — wdrożenie publiczne (bezpieczeństwo)

Ten dokument opisuje mechanizmy dodane, aby backend FastAPI mógł stać za publicznym reverse-proxy bez całkowicie otwartego dostępu do danych i kosztów LLM.

## Zmienne środowiskowe

| Zmienna | Wymagana | Opis |
|---------|----------|------|
| `ARCHITEKT_API_KEY` | Nie | Gdy ustawiona (niepusty string), każde żądanie poza ścieżkami publicznymi musi mieć nagłówek `Authorization: Bearer <wartość>`. Wyjątki: `GET /health`, `GET /health/ready`, `GET /`, `GET /assets/*`, `GET /docs`, `GET /redoc`, `GET /openapi.json` oraz preflight `OPTIONS`. |
| `ARCHITEKT_ADMIN_TOKEN` | Nie | Gdy ustawiona, `POST /admin/trigger-followups` wymaga `Authorization: Bearer <token>`. Gdy pusta — zachowanie developerskie (endpoint działa bez nagłówka), nadal ogranicz rate limitem i siecią. |
| `AW_CORS_ORIGINS` | Nie | Lista dozwolonych originów (np. `https://app.example.com`) zamiast `*`. |
| `AW_DISABLE_RATE_LIMIT` | Nie | Ustaw `1` / `true` aby wyłączyć SlowAPI (testy CI, lokalny smoke). |
| `AW_RATE_DEBATE_PER_MINUTE` | Nie | Limit `POST /debate/stream` i `POST /debate/continue/stream` na adres IP (domyślnie 30/min, clamp 5–120). |

## Frontend (Vite / Tauri)

- Build: `VITE_ARCHITEKT_API_KEY` — ten sam sekret co `ARCHITEKT_API_KEY` na serwerze (świadoma redundancja: sekret trafia do bundle JS; używaj tylko z dodatkową warstwą, np. Cloudflare Access, lub trzymaj aplikację desktopową).
- Lokalnie: modal „Połączenie” zapisuje opcjonalny token w `localStorage` pod kluczem `aw_architekt_api_key` (po „Zastosuj”).

## Reverse proxy

1. Wymuś TLS.
2. Opcjonalnie wstrzykuj `Authorization` po stronie serwera (BFF), żeby nie trzymać klucza w przeglądarce.
3. Ogranicz rozmiar body i timeouty na `/debate/stream`.
4. Dla `/admin/trigger-followups` rozważ allowlist IP albo osobny port sieciowy VPN.

## Limity zapytań API

- `GET /history`: `limit` ∈ [1, 200], `q` obcięte do 500 znaków.
- `GET /commitments/due`: `within_hours` ∈ [1, 8760].
- `GET /dreams`: `limit` ∈ [1, 100].

## Eksport PDF

- Endpoint: `GET /debate/{id}/export.pdf`.
- Font: `core/fonts/DejaVuSans.ttf` (pakiet DejaVu 2.37, patrz `core/fonts/SOURCE.txt`).
