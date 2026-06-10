"""FA2 — konfiguracja trybu biznesowego.

IZOLACJA / DB: FA2 **współdzieli jedną bazę** z trybem personal. Nie ma
osobnej bazy FA2 — izolacja danych jest realizowana wyłącznie przez
`tenant_id` (ContextVar + RLS/`pg_wrap`), a debaty FA2 zapisuje wspólny
pipeline (`api.services.debate_orchestrator`). Patrz Faza 0:
`tests/test_business_fa2_tenant_isolation.py`.

Wcześniejszy `get_fa2_settings()` (klucze `database_path`/`FA2_DATABASE_PATH`,
`FA2_LLM_CONCURRENCY`, `AW_FA2_RATE`) został usunięty — był martwy i sugerował
separację bazy, która nie istnieje. Realnie używane są tylko env-y czytane
w miejscu użycia, np. `AW_FA2_CACHE_TTL` w `shared/utils/cache.py`.
Selekcja agentów wg trybu: `business_fa2.config.modes.MODE_AGENTS`.
"""

from __future__ import annotations
