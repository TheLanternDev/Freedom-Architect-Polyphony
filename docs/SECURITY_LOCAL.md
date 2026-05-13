# Bezpieczeństwo — instalacja lokalna (model A)

## Sekrety

- `ANTHROPIC_API_KEY` trzymaj wyłącznie w **`ui/.env`** (lub pliku wskazanym przez `AW_ENV_FILE`). Pliki `.env` są w `.gitignore` — **nie commituj** ich ani logów z treścią briefów.
- Backend nie powinien logować pełnych briefów ani kluczy — przy diagnozie używaj redakcji.

## Sieć

- Domyślny profil: **localhost / zaufane LAN**.  
- **Nie** wystawiaj `uvicorn` na 0.0.0.0 w internecie bez reverse proxy, TLS i uwierzytelniania — endpointy nie są zaprojektowane pod anonimowy dostęp z sieci (por. `docs/spec/SPEC_CURRENT.md`, admin bez auth).

## Telemetria

- Aplikacja frontendowa ma stałą `APP_TELEMETRY_ENABLED = false` — brak domyślnej telemetrii do operatora produktu. Zmiana na zbieranie danych wymagałaby **osobnego opt-in** w UI i aktualizacji dokumentacji.

## Backup

- Kopia zapasowa = plik bazy SQLite (domyślnie `data/architekt.db`). Przy usunięciu aplikacji lub katalogu danych **historia debat znika**, o ile nie masz kopii.
