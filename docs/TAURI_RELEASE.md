# Tauri — release, podpisywanie i auto-update

## 0. Backend jako sidecar (ZAWSZE pierwszy krok od 2026-07-07)

Od tego commita `.app`/`.msi` jest **samowystarczalny** — nie polega już na
tym, że tester ma zainstalowanego Pythona i sklonowane repo z `.venv` obok
binarki. `src-tauri/src/lib.rs` uruchamia backend jako **Tauri sidecar**:
zamrożoną binarkę PyInstaller zbindlowaną wprost do paczki
(`bundle.externalBin` w `tauri.conf.json`).

**Przed KAŻDYM `tauri build` / `tauri:dev` z pełnym testem trzeba zbudować
sidecara dla danego OS:**

```bash
# macOS / Linux
./scripts/build-backend-sidecar.sh

# Windows (PowerShell)
.\scripts\windows\build-backend-sidecar.ps1
```

Efekt: `src/src-tauri/binaries/architekt-backend-<target-triple>[.exe]`.
Skrypt sam robi smoke test (`GET /health`) na zbudowanej binarce — jeśli padnie,
zwykle brakuje `--hidden-import`/`--collect-submodules` dla nowo dodanej
zależności backendu (rozszerz listę w skrypcie).

**Ważne — PyInstaller NIE cross-kompiluje.** Binarkę macOS buduje się NA
macOS, binarkę Windows NA Windows. Nie da się zbudować obu paczek z jednej
maszyny bez CI (patrz `.github/workflows/tauri-release.yml`, który robi to
automatycznie na `macos-latest` + `windows-latest`).

**Dev (`npm run tauri:dev`) nie wymaga tego kroku** — jeśli sidecar nie jest
zbudowany, `lib.rs` spada na dev fallback (`python -m uvicorn main:app` z venva
obok repo). `AW_DISABLE_AUTOSPAWN=1` wyłącza obie ścieżki (gdy wolisz odpalić
backend ręcznie — launcher rozpozna twój uvicorn i użyje go bez spawnu).

Dev fallback leci **bez `--reload`** (review 2026-07-30): reloader uvicorna to
supervisor + worker, a przy zamykaniu appki zabijaliśmy tylko supervisora —
worker zostawał sierotą trzymającą port i był potem rozpoznawany jako
„działający backend", więc appka po cichu gadała ze starym kodem. Hot-reload
przy pracy nad backendem: `AW_DISABLE_AUTOSPAWN=1` + własny
`uvicorn main:app --reload` w terminalu.

## 0a. Guard świeżości sidecara (od 2026-07-30)

`npm run tauri:build` woła najpierw `node scripts/check-sidecar-fresh.mjs`,
który **przerywa build**, gdy binarka sidecara nie istnieje albo jest starsza
niż jakikolwiek plik `.py` wchodzący do paczki.

Powód: przez 8 dni `.app` uruchamiana z ikony serwowała backend zamrożony
22.07, mimo że kod Pythona zmieniono 23.07. `tauri build` nigdy nie
odbudowywał sidecara, `binaries/` jest gitignorowane, a `/health` zwracał
hardkod `version: "3.3"` — nie było ŻADNEGO sygnału. Aplikacja wyglądała na
działającą i tak też się zachowywała, tylko nie miała nowego kodu.

Dwa mechanizmy zamykają tę dziurę:

1. **guard** — stale build nie przejdzie (`AW_SKIP_SIDECAR_CHECK=1` żeby
   świadomie pominąć przy iteracji po samym froncie);
2. **stempel** — `config/build_info.py` jest nadpisywany przy freeze
   (`build_id` = krótki rev + timestamp, `-dirty` gdy freeze z niescommitowanych
   zmian) i wracany do wartości „dev" po buildzie. `GET /health` zwraca
   `build_id`, launcher loguje go do `logs/launcher.log`, a UI pokazuje
   w banerze stanu. Smoke test w skrypcie builda **weryfikuje**, że stempel
   faktycznie wszedł do binarki.

Pełna paczka jednym poleceniem (buduje sidecara → guard → tauri build → dmg):

```bash
cd src && npm run dist:mac
```

Backend w trybie sidecar generuje sam `ARCHITEKT_JWT_SECRET` i ścieżki danych
przy pierwszym uruchomieniu (`env_bootstrap.py` → `app_data_dir()`) — tester
nie dotyka `.env`. Szczegóły: `docs/PACZKA_TESTOWA_STATUS_2026-07-07.md`.

Klucz LLM (BYOK) nadal idzie przez Keychain/Credential Manager OS (UI →
Ustawienia), nie przez sidecara — bez zmian.

## Build desktopa

`cd src && npm run tauri:build` (sync CSP z `VITE_API_URL`) — **po** kroku 0.

Release produkcyjny: `npm run tauri:build:release` — weryfikuje zmienne podpisu przed buildem.

## macOS — codesign i notaryzacja

Wymagane zmienne (GitHub Secrets / lokalnie przed buildem):

| Zmienna | Opis |
|---------|------|
| `APPLE_CERTIFICATE` | Base64 pliku `.p12` (Developer ID Application) |
| `APPLE_CERTIFICATE_PASSWORD` | Hasło do `.p12` |
| `APPLE_SIGNING_IDENTITY` | Np. `Developer ID Application: Twoja Firma (TEAMID)` |
| `APPLE_ID` | Apple ID do notaryzacji |
| `APPLE_PASSWORD` | Hasło aplikacji (app-specific password) |
| `APPLE_TEAM_ID` | Team ID |

Tauri CLI używa powyższych automatycznie przy `tauri build`. W `tauri.conf.json` ustawiono `hardenedRuntime: true` (wymagane przez notaryzację).

Po buildzie:

```bash
xcrun notarytool submit target/release/bundle/macos/*.dmg \
  --apple-id "$APPLE_ID" --password "$APPLE_PASSWORD" --team-id "$APPLE_TEAM_ID" --wait
xcrun stapler staple target/release/bundle/macos/*.app
```

## Windows — podpis

| Zmienna | Opis |
|---------|------|
| `WINDOWS_CERTIFICATE` | Base64 pliku `.pfx` |
| `WINDOWS_CERTIFICATE_PASSWORD` | Hasło certyfikatu |

Opcjonalnie w `tauri.conf.json` → `bundle.windows.certificateThumbprint` (SHA-1 thumbprint w store).

## Auto-update (Tauri Updater)

Domyślnie **wyłączone** (`createUpdaterArtifacts: false`). Włączenie przed pierwszym release z updaterem:

1. Wygeneruj parę kluczy:

```bash
cd src
npm run tauri signer generate -w ~/.tauri/architekt-wolnosci.key
```

2. Skopiuj **public key** do `src/src-tauri/tauri.conf.json` → `plugins.updater.pubkey`.

3. Ustaw endpoint (hosting manifestów JSON):

```json
"endpoints": ["https://releases.twoja-domena.pl/{{target}}/{{arch}}/{{current_version}}"]
```

4. Ustaw `bundle.createUpdaterArtifacts: true` i dodaj plugin (patrz komentarz w `Cargo.toml`).

5. CI: workflow `.github/workflows/tauri-release.yml` (workflow_dispatch) — sekrety signing + upload artefaktów.

**Private key** (`TAURI_SIGNING_PRIVATE_KEY`) — tylko w CI Secrets, nigdy w repo.

## CI

- **Lint/test:** `.github/workflows/ci.yml` (backend)
- **Deploy backend:** `.github/workflows/deploy.yml` (workflow_dispatch)
- **Tauri release:** `.github/workflows/tauri-release.yml` (workflow_dispatch, `macos-latest` + `windows-latest` — buduje sidecar PyInstaller na każdym OS przed `tauri build`)

## CSP produkcyjny

Przed buildem ustaw `VITE_API_URL=https://api.twoja-domena.pl` — `sync-tauri-csp.mjs` wstrzykuje origin do `connect-src`.
