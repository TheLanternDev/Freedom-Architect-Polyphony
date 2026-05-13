# Changelog

Format oparty na [Keep a Changelog](https://keepachangelog.com/pl/1.0.0/).

## [Unreleased]

### Dodane (Tydzień 2 — onboarding, docs, repo)

- UI: modal **Połączenie** (`LocalSetupModal`) — test `GET /health`, nadpisanie URL API w `localStorage` (`aw_api_base_override`), pierwsze uruchomienie do momentu „Nie pokazuj przy starcie” (`aw_setup_v2_done`).
- `ui/src/config/product.ts` — jawna flaga braku telemetrii (`APP_TELEMETRY_ENABLED`).
- `docs/SECURITY_LOCAL.md`, `docs/SUPPORT_PLAYBOOK.md`.
- `INSTALL.md` + `README.md` — odnośniki; sekcja pierwszego uruchomienia UI.
- `.gitignore` w korzeniu repo — sekrety i typowe artefakty Python/frontend.

### Dodane (Tydzień 1 — pakiet founders / instalacja)

- `INSTALL.md` — ścieżka instalacji lokalnej (BYOK).
- `docs/FOUNDERS_OFFER.md` — szkielet oferty produktowej (nie umowa prawna).
- `docs/LEGAL_PRIORITIES_FOR_COUNSEL.md` — tematy pod konsultację prawną.
- `scripts/smoke_week1.sh` — smoke przed wysyłką: `pytest tests/ -q`.
