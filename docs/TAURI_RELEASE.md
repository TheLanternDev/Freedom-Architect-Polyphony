# Tauri — release, podpisywanie i auto-update

Build desktopa: `cd src && npm run tauri:build` (sync CSP z `VITE_API_URL`).

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
- **Tauri release:** `.github/workflows/tauri-release.yml` (workflow_dispatch, macOS runner)

## CSP produkcyjny

Przed buildem ustaw `VITE_API_URL=https://api.twoja-domena.pl` — `sync-tauri-csp.mjs` wstrzykuje origin do `connect-src`.
