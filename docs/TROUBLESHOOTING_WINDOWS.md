# Rozwiązywanie problemów — Windows (beta)

## `python` nie jest rozpoznawany

- Zainstaluj Python 3.12+ z https://www.python.org/downloads/
- Zaznacz **Add python.exe to PATH**
- Zamknij i otwórz PowerShell ponownie
- Sprawdź: `python --version`

## Nie można uruchomić skryptu `.ps1`

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Potem ponownie: `.\scripts\windows\start-backend.ps1`

## HTTP 500 przy rejestracji / „ARCHITEKT_JWT_SECRET nie ustawiony”

1. Upewnij się, że istnieje plik `src\.env` (nie tylko `env\src.env.example`).
2. W `src\.env` musi być niepusty `ARCHITEKT_JWT_SECRET`.
3. Zrestartuj backend (Ctrl+C w oknie uvicorn, uruchom skrypt ponownie).

## „Load failed” / debata się nie startuje

1. Czy backend działa? http://127.0.0.1:8000/health
2. W UI: **Połączenie** → adres API = `http://127.0.0.1:8000`
3. Sprawdź logi w oknie backendu w momencie wysłania briefu.
4. Wyłącz VPN na próbę.

## Błąd 401 / model / Anthropic

- Sprawdź `ANTHROPIC_API_KEY` w `src\.env`
- Sprawdź limity i saldo na https://console.anthropic.com/
- Po zmianie `.env` **zrestartuj backend**

## `npm` nie jest rozpoznawany

- Zainstaluj Node.js LTS z https://nodejs.org/
- Zamknij i otwórz PowerShell
- Sprawdź: `node --version` i `npm --version`

## Port 8000 lub 1420 zajęty

- Zamknij poprzednie okna z uvicorn / `npm run dev`
- Lub w Task Manager zakończ wiszące procesy `python` / `node`

## Firewall / antywirus

Backend nasłuchuje tylko na `127.0.0.1` — zwykle nie wymaga wyjątków. Jeśli antywirus blokuje Pythona, dodaj wyjątek dla katalogu projektu.

## SmartScreen (gdy kiedyś dostaniesz `.msi`)

Niepodpisany instalator: **Więcej informacji** → **Uruchom mimo tego**. Na obecną betę przeglądarkową instalator nie jest potrzebny.
