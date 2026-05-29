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
- **RODO (konto)**: `GET /account/export`, `DELETE /account` (JWT, potwierdzenie `USUŃ MOJE KONTO`), purge tenanta w repo.
- **Observability**: opcjonalny Sentry (`SENTRY_DSN`), globalny handler 500 bez stacktrace, logi bez PII (metadane: path, tenant_id).
- **Preflight produkcyjny**: przy `AW_ENV=production` start odmawiany bez `ARCHITEKT_JWT_SECRET`, `AW_CORS_ORIGINS` (konkretna lista, nie `*`), `REDIS_URL`, `ANTHROPIC_API_KEY`, `ARCHITEKT_ADMIN_TOKEN`.
- **CORS fail-fast**: produkcja nie startuje z `AW_CORS_ORIGINS=*` ani bez zmiennej.

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
cd src
npm install              # rollup-native dla Twojej platformy
npm run tauri:dev        # natywne okno dev
# albo:
npm run tauri:build      # bundle (.app / .dmg / .msi)
```
Wymaga: Rust toolchain (`rustc`, `cargo`), Xcode CLT na macOS.

### 3) Konfiguracja produkcyjna (serwer publiczny)
Wymagane ENV (aplikacja **nie wystartuje** bez nich gdy `AW_ENV=production`):

| Zmienna | Cel |
|---------|-----|
| `ARCHITEKT_JWT_SECRET` | Logowanie JWT, multi-tenant |
| `AW_CORS_ORIGINS` | CSV konkretnych origins, np. `https://twoja-domena.pl` (nie `*`) |
| `REDIS_URL` | Refresh tokeny, globalny rate-limit, JTI revoke |
| `ANTHROPIC_API_KEY` | Rada / LLM |
| `ARCHITEKT_ADMIN_TOKEN` | `/admin/*` |
| `SENTRY_DSN` | (opcjonalnie) agregacja błędów |

Dodatkowo w `src/.env` (dev) lub sekretach deployu:
- UI: klucz JWT z `POST /auth/login` w nagłówku `Authorization: Bearer`
- `business_fa2`: `AW_FA2_RATE=10` (zaostrz limit)

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
