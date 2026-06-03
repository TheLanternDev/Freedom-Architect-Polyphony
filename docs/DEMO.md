# Demo interaktywne — Architekt Wolności

Publiczna (lub wewnętrzna) wersja próbna: użytkownik **wpisuje własny brief** i dostaje **prawdziwą debatę Rady** (LLM), z twardymi limitami kosztów i nadużyć.

## Włączenie

W `src/.env` (lub ENV serwera):

```env
AW_DEMO_MODE=1
ARCHITEKT_JWT_SECRET=<losowy-ciag-min-32-znakow>
ANTHROPIC_API_KEY=<klucz-hosta-demo>
DAILY_BUDGET_USD=5
AW_RATE_DEBATE_PER_MINUTE=10

# Opcjonalnie — domyślne wartości w nawiasach
AW_DEMO_MAX_DEBATES=2
AW_DEMO_MAX_BRIEF_CHARS=800
AW_DEMO_ALLOWED_MODES=codzienny
AW_DEMO_ALLOWED_CATEGORIES=decyzja
AW_DEMO_JWT_TTL_SEC=86400
```

Uruchom backend + UI jak w [`INSTALL.md`](../INSTALL.md). Użytkownik na ekranie startowym klika **„Rozpocznij demo”** → `POST /auth/demo` → JWT sesji gościa (`tenant_id` = `demo_*`).

## Zachowanie

| Obszar | Demo |
|--------|------|
| Rejestracja | Wyłączona (`403`) |
| Logowanie klasyczne | Działa (dla operatorów) |
| Debaty | Limit per sesja (`AW_DEMO_MAX_DEBATES`) |
| Tryb | Domyślnie tylko `codzienny` (4 agentów — tańszy) |
| Brief | Max `AW_DEMO_MAX_BRIEF_CHARS` znaków |
| Integracje / FA2 | Ukryte w UI; API: `403 demo_feature_disabled` na `/integrations/*` |
| RODO (`/account/export`, `DELETE /account`) | Zablokowane w API dla `demo_*` |
| Dane | Izolacja tenanta `demo_*` (nie trwałe konto użytkownika) |

## API

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| POST | `/auth/demo` | Nowa sesja gościa + JWT |
| GET | `/demo/status` | Zużycie limitu (wymaga JWT demo) |
| GET | `/edition` | Pole `demo` gdy `AW_DEMO_MODE=1` |

## Wdrożenie web (jedna domena)

```bash
cd src && npm run build
AW_SERVE_UI=1 AW_DEMO_MODE=1 AW_ENV=production \
  AW_CORS_ORIGINS=https://demo.twoja-domena.pl \
  uvicorn main:app --host 0.0.0.0 --port 8000
```

W produkcji z `AW_DEMO_MODE=1` nie wymagamy `ARCHITEKT_ADMIN_TOKEN` ani `REDIS_URL` (patrz `production_preflight_errors`), ale **JWT i klucz Anthropic są obowiązkowe**.

## Testy

```bash
pytest tests/test_demo_mode.py -q
```
