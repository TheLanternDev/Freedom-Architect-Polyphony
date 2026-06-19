# Architektura

> **Stan:** 2026-06-18. Źródło prawdy: kod (`config/agent_models.py`, `business_fa2/`, `agents/__init__.py`). Pełny opis: [`ARCHITEKT_WOLNOSCI_OPIS.md`](ARCHITEKT_WOLNOSCI_OPIS.md). Kontrakt API: [`spec/SPEC_CURRENT.md`](spec/SPEC_CURRENT.md).

## Model dystrybucji

**Docelowy:** pudełko **local-first BYOK** — jedna instalacja, lokalny SQLite, klucz LLM użytkownika, device-seal. Dane debat nie przechodzą przez infrastrukturę operatora.

**W repo (uśpione do hostingu):** multi-tenant PostgreSQL + RLS (migracje `0001`–`0009`), JWT per-user. Aktywuje się przy decyzji o hosted SaaS (roadmap Later L1).

## personal_v1 (Rada Nadzorcza, osobista)

- 9 agentów (Relacjan, Kogit, Emojy, Deega, Smaty, Szow, Tai, Obver, Kidi) + Syez jako syntezator poza Radą
- Jednolity model: `claude-sonnet-4-6` dla wszystkich agentów i Syeza (`config/agent_models.py`); różnicowane tylko `temperature` / `max_tokens`
- Safety: frazy kryzysowe → `safety_halt` + numer 116 123
- Tryby debaty: `pelna`, `marzen`, `schematy`, `codzienny`
- A0 destylacja marzenia + Obraz Użytkownika wstrzykiwany do agentów

## business_fa2 (Freedom Architect, biznesowa)

- Te same 9 agentów — przeramowane promptami biznesowymi (`business_fa2/config/roles.py`), bez nowych ról
- Konteksty branżowe (rozszerzają Smaty + Obver): produkt fizyczny, usługa B2B, SaaS, marketplace
- Te same tryby debaty; proxy wymusza `council_mode="fa2"`
- Mount `/business` (`POST /business/debate/stream`, `GET /business/health`); alternatywa: nagłówek `X-Council-Mode: fa2` na głównym `/debate/stream`
- **Wspólna baza** z edycją osobistą — brak osobnej bazy FA2. Izolacja przez `tenant_id` (ContextVar + RLS). FA2: bez A0 i bez Obrazu; Syez `max_tokens=5000`, `temperature=0.6`

## Wspólne (shared)

- LLM: `config/llm_providers.py` — `auto|anthropic|xai|ollama`; BYOK przez `X-LLM-Key`
- Cache SHA256 per-user (`BaseAgent._cache_key`)
- Idempotency-Key na debacie (`api/idempotency.py`)
- Config + budżety (`core/cost_tracking.py`)

## Desktop (Tauri)

- Tauri **0.1.0**, React **19**, CSP restrykcyjne (`script-src 'self'`, `object-src 'none'`)
- Buildy **niepodpisane** (bloker GTM N4, nie luka security)
- Hook `useDebate.ts` + reduktor SSE z testami w CI

## Zasady rozdzielenia

- Konteksty personal i fa2 nie mieszają się — osobne prompty, osobna ewolucja agentów (`:fa2` suffix)
- Operator świadomie wybiera tryb w UI (`config/product.ts`)

## Poza aplikacją

- `tools/reels-generator/` — skrypt wideo/social (zastąpił usunięty `tools/ig-reels/`)
- `polyphony-site/` — marketing (Vercel)
