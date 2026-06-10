# Architektura

> Źródło prawdy: kod (`config/agent_models.py`, `business_fa2/`, `agents/__init__.py`). Pełny opis: [`spec/SPEC_CURRENT.md`](spec/SPEC_CURRENT.md).

## personal_v1 (Rada Nadzorcza, osobista)
- 9 agentów (Relacjan, Kogit, Emojy, Deega, Smaty, Szow, Tai, Obver, Kidi) + Syez jako syntezator poza Radą
- Jednolity model: `claude-sonnet-4-6` dla wszystkich agentów i Syeza (`config/agent_models.py`); różnicowane tylko `temperature`/`max_tokens`
- Safety: frazy kryzysowe → halt + numer 116 123
- Tryby debaty: `pelna`, `marzen`, `schematy`, `codzienny`

## business_fa2 (Freedom Architect, biznesowa)
- Te same 9 agentów co edycja osobista — przeramowane promptami biznesowymi (`business_fa2/config/roles.py`), bez nowych ról
- Konteksty branżowe (rozszerzają Smaty + Obver): `produkt fizyczny`, `usługa B2B`, `SaaS`, `marketplace`
- Te same tryby co osobista (`pelna/marzen/schematy/codzienny`); proxy wymusza `council_mode="fa2"`
- Mount `/business`; **wspólna baza** z edycją osobistą — brak osobnej bazy FA2. Izolacja danych przez `tenant_id` (ContextVar + RLS/`pg_wrap`), izolacja kontekstów ewolucji agentów przez sufiks `:fa2`. (`FA2_DATABASE_PATH`/`get_fa2_settings` usunięte jako martwy klucz sugerujący separację — Faza 2.)

## Wspólne (shared)
- LLM wrapper (Anthropic SDK + fallback)
- Cache SHA256
- Config + budżety

## Zasady rozdzielenia
- Konteksty nie łączą się — osobny runner, osobna pamięć, osobne testy.
- Patryk świadomie wybiera tryb: osobisty albo biznesowy.
