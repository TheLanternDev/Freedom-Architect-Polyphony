# Production Checklist — Architekt Wolności v1.0

## Gotowe ✅
- **Backend per-request mode**: `_council_mode_ctx` (contextvars) + middleware czyta `X-Council-Mode: personal|fa2`. UI toggle → header → backend dispatchuje per-request, **bez restartu**.
- **UI wysyła header**: `getApiAuthHeaders()` w `src/src/lib/apiAuth.ts` dokleja `X-Council-Mode` do każdego fetcha (Authorization + Mode w jednym miejscu).
- **Health spójność**: `/health` zwraca `council_mode` zgodnie z headerem; UI baner ostrzega gdy niespójność.
- **Onboarding (20 pytań)** — `GET /personal/onboarding/questions` + UI modal (`OnboardingPanel`, localStorage `aw_onboarding_v1_done`).
- **Daily ritual** — `GET /personal/ritual/daily` + sidebar collapsible (`DailyRitualPanel`, dobiera blok poranek/wieczór po godzinie).
- **Rate-limit FA2**: sliding-window 60s/IP-lub-token (`AW_FA2_RATE`, default 30/min) — zwraca 429 po przekroczeniu.
- **Encrypted cache**: personal RAM-only, FA2 Fernet w `~/.architekt/`.
- **Cost log**: `cost_log.jsonl` przy każdym callu (tier/model/tokens/$).
- **Safety**: word-boundary regex + Unicode-normalize.
- **TypeScript**: `tsc --noEmit` clean.

## Do wykonania ręcznie 🔧

### 1) Live test z realnym kluczem
```bash
cd /Users/tpltd145/Projects/architekt-wolnosci
source venv/bin/activate
python scripts/smoke_live.py
# koszt ~$0.001-0.005 (wszyscy agenci wymuszeni na Haiku)
```
Sprawdź: `cost_log.jsonl` przyrasta, `perspectives` ma 9 wpisów, synteza po polsku.

### 2) Tauri build
```bash
cd ui
npm install              # rollup-native dla Twojej platformy
npm run tauri:dev        # natywne okno dev
# albo:
npm run tauri:build      # bundle (.app / .dmg / .msi)
```
Wymaga: Rust toolchain (`rustc`, `cargo`), Xcode CLT na macOS.

### 3) Konfiguracja produkcyjna (jeśli serwer publiczny)
- W `src/.env`: ustaw `AW_API_TOKEN=<silny-token>` + `ARCHITEKT_API_KEY=<ten-sam>`
- UI: w modal „Połączenie" (LocalSetupModal) podaj klucz dla `Authorization: Bearer`.
- W `business_fa2`: ustaw `AW_FA2_RATE=10` (zaostrz limit), `AW_CORS_ORIGINS=https://twoja-domena.pl`.

## Architektura per-request mode

```
UI toggle ─┐
           ▼
     localStorage["aw_council_mode"]
           │
           ▼  (każdy fetch)
     getApiAuthHeaders() ──► X-Council-Mode: personal|fa2
                                    │
                                    ▼
                       main.py middleware
                                    │
                                    ▼
                      _council_mode_ctx (ContextVar)
                                    │
            ┌───────────────────────┴────────────────────┐
            ▼                                            ▼
   personal_v1.* (v1)                       business_fa2.* (fa2)
```
Globalny `AW_COUNCIL_MODE` env nadal działa jako fallback gdy header pusty.
