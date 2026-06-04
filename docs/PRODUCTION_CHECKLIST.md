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
- **Preflight produkcyjny**: przy `AW_ENV=production` start odmawiany bez `DATABASE_URL` (Postgres), `ARCHITEKT_JWT_SECRET`, `AW_CORS_ORIGINS` (konkretna lista, nie `*`), `REDIS_URL`, `ANTHROPIC_API_KEY`, `ARCHITEKT_ADMIN_TOKEN`.
- **CORS fail-fast**: produkcja nie startuje z `AW_CORS_ORIGINS=*` ani bez zmiennej.

## Do wykonania ręcznie 🔧

### 1) Live test z realnym kluczem
```bash
cd /Users/tpltd145/Projects/architekt-wolnosci
source venv/bin/activate
# terminal 1:
uvicorn main:app --host 127.0.0.1 --port 8000
# terminal 2:
python scripts/smoke_live.py
# tylko health (bez kosztu LLM):
SMOKE_SKIP_DEBATE=1 python scripts/smoke_live.py
```
Sprawdź: `cost_log.jsonl` przyrasta (gdy pełny smoke), `agent_start` × 9, synteza po polsku.

### 2) Tauri build
```bash
cd src
npm install              # rollup-native dla Twojej platformy
npm run tauri:dev        # natywne okno dev
# dev bundle (bez weryfikacji certyfikatów):
npm run tauri:build
# release (podpis — patrz docs/TAURI_RELEASE.md):
npm run tauri:build:release
# lub lokalnie bez certów:
AW_TAURI_SKIP_SIGN_CHECK=1 npm run tauri:build:release
```
Wymaga: Rust toolchain (`rustc`, `cargo`), Xcode CLT na macOS. Podpisywanie i auto-update: **`docs/TAURI_RELEASE.md`**.

### 3) Konfiguracja produkcyjna (serwer publiczny)
Wymagane ENV (aplikacja **nie wystartuje** bez nich gdy `AW_ENV=production`):

| Zmienna | Cel |
|---------|-----|
| `DATABASE_URL` | PostgreSQL z RLS (`postgresql://…`) — **wymagany w prod** |
| `ARCHITEKT_JWT_SECRET` | Logowanie JWT, multi-tenant (≥32 znaki) |
| `AW_CORS_ORIGINS` | CSV konkretnych origins, np. `https://twoja-domena.pl` (nie `*`) |
| `REDIS_URL` | Refresh tokeny, globalny rate-limit, JTI revoke |
| `ANTHROPIC_API_KEY` | Rada / LLM |
| `ARCHITEKT_ADMIN_TOKEN` | `/admin/*`, `/metrics` |
| `SENTRY_DSN` | (opcjonalnie) agregacja błędów |
| `LOG_FORMAT=json` | (zalecane) logi strukturalne pod Loki/Datadog |

**Docker prod:** `docker compose -f docker-compose.prod.yml up --build` (wymaga `.env` + `POSTGRES_PASSWORD`).

**Dev compose:** `docker compose up` — tylko SQLite, `AW_ENV=development` (nie używać na prod).

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

---

## CD — automatyczny build+push obrazu (P1-D2)

Workflow `.github/workflows/deploy.yml` buduje i wypycha obraz Dockera **automatycznie po wypchnięciu tagu** `v*`:

```bash
git tag v1.2.3 && git push origin v1.2.3   # → build + push obrazu do rejestru
```

Obok tagu publikowany jest też ruchomy `latest`. Ręczne uruchomienie: zakładka **Actions → deploy → Run workflow** (`push_image=true`).

### Sekrety wymagane do push (ustaw w GitHub → Settings → Secrets and variables → Actions)

| Secret | Przykład | Opis |
|--------|----------|------|
| `REGISTRY` | `ghcr.io` / `registry.digitalocean.com/twoj-rejestr` | Host rejestru |
| `REGISTRY_USERNAME` | nazwa użytkownika / `oauth` | Login do rejestru |
| `REGISTRY_PASSWORD` | token / hasło | **Token** rejestru (nie hasło konta) |

**Bez tych sekretów** push na tagu jest **pomijany z ostrzeżeniem** (workflow nie czerwieni się — obraz i tak buduje się w runnerze, smoke-import przechodzi). To pozwala tagować wydania zanim skonfigurujesz rejestr.

Obraz: `$REGISTRY/architekt-wolnosci:<tag>`. Po deploy: `GET /health/ready` + `scripts/smoke_live.py`.
