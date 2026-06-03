# Architekt Wolności — beta tester (Windows)

Wersja przeglądarkowa (bez instalatora `.msi`). Backend + UI na Twoim komputerze.

> **Paczka sponsorowana?** Gdy istnieje plik `BETA_SPONSOR.marker` w katalogu projektu — **pomiń §2**. Klucze API są wbudowane w backend; nie musisz ich wpisywać ani szukać w plikach.

## Wymagania

| Program | Wersja | Pobierz |
|---------|--------|---------|
| Python | 3.12+ | https://www.python.org/downloads/ |
| Node.js | LTS (20+) | https://nodejs.org/ |

Przy instalacji Pythona zaznacz **„Add python.exe to PATH”**.

Szacowany czas pierwszego uruchomienia: **20–40 min** (instalacja + konfiguracja).

## 1. Rozpakuj paczkę

1. Rozpakuj `architekt-wolnosci-beta-*.zip` np. do `C:\Architekt\`.
2. W środku powinien być katalog z plikami `main.py`, `src\`, `requirements.txt`.

## 2. Konfiguracja `.env`

**Paczka sponsorowana:** jeśli w katalogu głównym jest `BETA_SPONSOR.marker` — **pomiń cały ten krok** i przejdź do §3.

**Paczka BYOK (własny klucz):**

1. Skopiuj `env\src.env.example` → `src\.env`.
2. Uzupełnij:

```env
ANTHROPIC_API_KEY=sk-ant-...
ARCHITEKT_JWT_SECRET=<losowy ciąg>
VITE_API_URL=http://127.0.0.1:8000
```

**Klucz Anthropic:** https://console.anthropic.com/ → API Keys.

**JWT secret** (PowerShell, jednorazowo):

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Wklej wynik jako `ARCHITEKT_JWT_SECRET` w `src\.env`.

## 3. Zezwolenie na skrypty (jednorazowo)

W PowerShell:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 4. Uruchom backend

Otwórz **PowerShell** (zwykły użytkownik):

```powershell
cd C:\Architekt\architekt-wolnosci
.\scripts\windows\start-backend.ps1
```

Pierwsze uruchomienie instaluje zależności Pythona (`venv` + `pip install`). Zostaw to okno otwarte.

Sprawdzenie w przeglądarce: http://127.0.0.1:8000/health → `"status":"alive"`.

## 5. Uruchom UI

Drugie okno **PowerShell**:

```powershell
cd C:\Architekt\architekt-wolnosci
.\scripts\windows\start-ui.ps1
```

Pierwsze uruchomienie robi `npm install`. Otwórz adres z konsoli (zwykle http://localhost:1420).

## 6. Pierwszy test

1. **Zarejestruj konto** (nie używaj „pomiń logowanie” na beta).
2. W nagłówku: **Połączenie** → **Test /health** — powinien być zielony status.
3. Uruchom krótką debatę (tryb **codzienny** — tańszy).
4. Po zakończeniu: **kontynuuj wątek** (druga runda na ten sam temat).

## Co testować (checklista)

- [ ] Rejestracja i logowanie
- [ ] Ustawienia → **Prywatność i konto** → eksport JSON (po pierwszej debacie)
- [ ] Debata od briefu do syntezy
- [ ] Kontynuacja wątku (pamięć poprzednich rund)
- [ ] Połączenie /health po restarcie backendu
- [ ] Czytelność syntezy (Mermaid / structured synthesis)

## Koszty

- **Paczka sponsorowana:** koszty debat opłaca sponsor — nie musisz mieć konta Anthropic.
- **Paczka BYOK:** pełna debata w trybie codziennym to zwykle kilka groszy–kilku złotych; płacisz na koncie Anthropic.

## Bezpieczeństwo

- Nie wystawiaj backendu na internet (tylko `127.0.0.1`).
- Nie commituj ani nie wysyłaj `src\.env`.
- Dane (SQLite) są w `data\architekt.db` na Twoim PC.

## Problemy?

→ [`docs/TROUBLESHOOTING_WINDOWS.md`](TROUBLESHOOTING_WINDOWS.md)

## Feedback

Wyślij krótki raport:

1. Krok, na którym utknąłeś (jeśli utknąłeś)
2. Oczekiwane vs. rzeczywiste zachowanie
3. Zrzut ekranu lub log z terminala (bez kluczy API)
