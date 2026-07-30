# Code Review + Plan Paczki Testowej (macOS / Windows) — 2026-06-25

**Zakres:** przegląd kodu pod kątem dystrybucji do testerów + plan budowy paczki instalacyjnej.
**Metoda:** statyczny przegląd kodu na bazie `CODE_REVIEW_2026-06-16.md` (nie weryfikowano działającego deploymentu).
**Pliki kluczowe:** `src/src-tauri/src/lib.rs`, `tauri.conf.json`, `capabilities/default.json`, `api/http_guard.py`, `core/device_seal.py`, `INSTALL.md`, `scripts/pack-founders-archive.sh`, `docs/BETA_TESTER_WINDOWS.md`, `docs/TAURI_RELEASE.md`.

---

## CZĘŚĆ 1 — CODE REVIEW

### Podsumowanie
Warstwa izolacji/auth jest zdrowa: 4 blokery z 2026-06-02 zamknięte fail-closed (potwierdzone w `http_guard.py` i pełnym CSP w `tauri.conf.json`). **Blokery dystrybucji nie są blokerami bezpieczeństwa** — leżą w pakowaniu, podpisie i szyfrowaniu danych lokalnych. Werdykt dla wysyłki testerom: **Request Changes** (3 blokery niżej).

### Blokery dystrybucji (muszą paść przed wysyłką)

| # | Plik / dowód | Problem | Waga |
|---|---|---|---|
| B1 | `src-tauri/src/lib.rs` (`spawn_backend`, `resolve_repo_root`, `resolve_python`) | **Bundle nie jest samowystarczalny.** Desktop startuje backend przez `python -m uvicorn main:app`, szukając repo (`AW_REPO_ROOT` → `~/Projects/architekt-wolnosci` → cwd) i venv (`.venv`/`venv`). `.app`/`.msi` **nie zawiera** Pythona, repo ani zależności → u testera bez dev-stacku po prostu nie wystartuje (autospawn zwraca „could NOT locate repo root"). To jest **główny** blocker paczki, ważniejszy niż podpis. | 🔴 Critical |
| B2 | `tauri.conf.json` → `macOS.signingIdentity: null`, `windows.certificateThumbprint: null` | **Buildy niepodpisane.** macOS Gatekeeper blokuje uruchomienie (notaryzacja wymagana), Windows SmartScreen straszy. Bez podpisu instalacja u testera = ostrzeżenia / blokada. | 🔴 Critical (GTM) |
| B3 | `grep`: brak `sqlcipher`/`Fernet`/`keyring` przy bazie; `INSTALL.md §5` — `data/architekt.db` plaintext | **SQLite niezaszyfrowane at-rest.** Dane debat = wrażliwe dane osobowe, leżą jawnie na dysku. Jeśli testerzy wprowadzają **realne** dane → trzeba albo szyfrować (SQLCipher), albo jawny disclaimer + zgoda. | 🔴 Critical (jeśli realne dane) |

### Pozostałe znaleziska (nie blokują testów, do uprzątnięcia)

| # | Plik | Uwaga | Waga |
|---|---|---|---|
| S1 | `tauri.conf.json` `shell.open: true` + `capabilities/default.json` `shell:allow-open` | `open` bez allowlisty URL. W modelu pudełkowym ryzyko niskie, ale zawęź do potrzebnych schematów przed szerszą dystrybucją. | 🟡 |
| S2 | `lib.rs` — keychain BYOK (`store/get/clear_llm_key`) | Klucz LLM trafia do keychaina OS (dobrze), ale **zweryfikuj e2e**, że dociera do backendu (`X-LLM-Key`) i że bez klucza backend jest fail-closed. Test ręczny przed wysyłką. | 🟡 (do weryfikacji) |
| S3 | `core/device_seal.py` | Soft device-binding po stronie klienta — OK dla pudełka, ale to **nie** ochrona danych. Świadome, udokumentowane. Zostaw. | 🔵 Info |
| S4 | `http_guard.py` admin jako `DEFAULT_TENANT` (znalezisko A z 06-16) | Bez znaczenia dla single-tenant pudełka. Zamknąć dopiero przed team-planem. | 🔵 Info |
| S5 | `lib.rs` `stdout/stderr = null` | Logi backendu są wyrzucane → przy zgłoszeniu testera brak diagnostyki. Przekieruj do pliku w katalogu danych. | 🟡 (wsparcie) |

### Co jest dobre
CSP pełne; fail-closed bez sekretów; RLS/GUC parametryzowane; BYOK przez keychain; istniejący pipeline pakowania (`pack-founders-archive.sh`, tryb sponsor) i dokumentacja beta (`BETA_TESTER_WINDOWS.md`, `TROUBLESHOOTING_WINDOWS.md`).

---

## CZĘŚĆ 2 — PLAN PACZKI TESTOWEJ

### Decyzja architektoniczna (źródło 90% pracy)
Tester nie może instalować Pythona/Node. Trzeba **zamrozić backend w binarkę** (PyInstaller: `main:app` → jeden plik) i wpiąć ją do Tauri jako **sidecar** (`bundle.externalBin`), zamiast wołać `uvicorn` z repo. Wtedy `.dmg`/`.msi` jest samowystarczalny. To zamyka B1 i jest warunkiem każdego kolejnego kroku.

### Ścieżki (wybór wg tego, ilu testerów i czy realne dane)

**Tor A — „repo + launcher" (najtańszy, dziś).** Zostaw obecną paczkę przeglądarkową, dołóż one-click launcher. Tester i tak instaluje Pythona (20–40 min). Tylko dla 1–3 technicznych testerów. Zero nowej pracy inżynierskiej.

**Tor B — paczka desktop self-contained (REKOMENDOWANY dla realnych testerów).** PyInstaller + sidecar + podpis. Tester: pobierz → zainstaluj → działa.

### Fazy Toru B

**N1. Spike: zamrożenie backendu (≤1 dzień)**
- PyInstaller `main.py` → binarka, uruchom standalone, potwierdź `GET /health = 200`.
- Pułapki: dynamiczne importy agentów/routerów (dodaj `--hidden-import` / `--collect-all`), ścieżki `data/`, `config/`, migracje.

**N2. Integracja sidecar w Tauri (1–2 dni)**
- `bundle.externalBin` na binarkę per-platforma (`-x86_64-apple-darwin`, `-aarch64-apple-darwin`, `-x86_64-pc-windows-msvc`).
- W `lib.rs`: zamień `spawn_backend()` (uvicorn z repo) na `tauri_plugin_shell` sidecar; zachowaj kill-on-exit.
- Ścieżka danych: wymuś `ARCHITEKT_DB_PATH` w katalogu app-data OS (nie cwd).
- **S5:** przekieruj logi backendu do pliku w katalogu danych.

**N3. Szyfrowanie at-rest — B3 (1–2 dni; wymagane jeśli realne dane)**
- SQLCipher (klucz w keychaina OS, jak BYOK) **lub** — jeśli faza testowa na danych nie-wrażliwych — wyraźny disclaimer + zgoda w onboardingu i EULA. Decyzja zależna od tego, czy testerzy wprowadzają realne sprawy osobiste.

**N4. Podpis i notaryzacja — B2 (zależne od kont)**
- macOS: Developer ID + `notarytool` + `stapler` (konto Apple Dev $99/rok). Sekrety i komendy gotowe w `docs/TAURI_RELEASE.md`; `tauri-release-env-check.mjs` już waliduje ENV.
- Windows: podpis cert (OV/EV) → znika SmartScreen. Bez certu: dla zamkniętej grupy testerów akceptowalne ostrzeżenie + instrukcja „Więcej → Uruchom mimo to".
- **Most na teraz, jeśli brak certów:** macOS ad-hoc + udokumentowany „prawy klik → Otwórz"; Windows niepodpisany + instrukcja. OK dla <~10 zaufanych testerów, nie do publicznej dystrybucji.

**N5. Smoke + pakiet (0,5 dnia)**
- `pytest tests/ -q` jako bramka, ręczny e2e: instalacja na czystej maszynie/VM per OS → rejestracja → 1 debata → historia.
- Dołącz `BETA_TESTER_*` (zaktualizowane: bez kroku Pythona), kanał zgłoszeń, jak wysłać log z N2.

### Macierz blokerów → faz
| Blocker | Faza zamykająca |
|---|---|
| B1 samowystarczalność | N1 + N2 |
| B2 podpis | N4 (lub most ad-hoc) |
| B3 at-rest | N3 (lub disclaimer) |

---

## NAJMNIEJSZY KOLEJNY RUCH (≤60 min)
Spike PyInstaller na jednym OS: `pip install pyinstaller && pyinstaller --onefile --collect-all api --collect-all agents --collect-all core main.py`, uruchom binarkę, sprawdź `curl http://127.0.0.1:8000/health`. Jeśli `/health=200` → cała ścieżka B jest realna i można planować N2. Jeśli padnie na importach → masz dokładną listę `--hidden-import` do uzupełnienia. To de-ryzykuje 90% planu najmniejszym kosztem.
