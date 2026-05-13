# Architekt Wolności — Specyfikacja Aktualna (v3.3)

> Wygenerowana na podstawie rzeczywistego kodu. Źródło prawdy: `main.py`, `agents/`, `config/`, `db/schema.sql`.  
> Data: 2026-05-12

---

## 1. Co to jest

Backend FastAPI uruchamiający **10-osobową Radę Nadzorczą** — 9 agentów analizuje brief równolegle, Syez syntetyzuje wyniki w jedną odpowiedź. System działa w trybie SSE (streaming), persystuje dane w SQLite i opcjonalnie cachuje w Redis.

---

## 2. Rada — skład i modele

| Agent | Emoji | Rola | Model | Temp | Max tokens |
|-------|-------|------|-------|------|------------|
| Syez | 🌌 | Synteza (orchestrator) | **Opus 4.7** | 0.5 | 3000 |
| Szow | ⚫ | Cień (Jungowski) | **Opus 4.7** | 1.0 | 1500 |
| Kogit | 🧠 | Architekt Logiki i Struktury | Sonnet 4.6 | 0.7 | 4000 |
| Tai | 🟠 | Czasowy — pamięć i wizja | Sonnet 4.6 | 0.6 | 4000 |
| Deega | 🔴 | Głęboka Diagnoza | Sonnet 4.6 | 0.0 | 2000 |
| Relacjan | 🔵 | Relacyjny | Sonnet 4.6 | 0.8 | 2000 |
| Emojy | 🟡 | Emocjonalny | Sonnet 4.6 | 0.8 | 2000 |
| Obver | 🔷 | Obserwator (zewnętrzny) | Sonnet 4.6 | 0.8 | 2000 |
| Kidi | 🧸 | Dziecięca Ciekawość | Haiku 4.6 | 1.0 | 1500 |
| Smaty | 🟤 | Somatyczny | Haiku 4.6 | 1.0 | 1500 |

**Modele aktualnie:** `claude-opus-4-7` / `claude-sonnet-4-6` / `claude-haiku-4-6`  
Override przez env: `MODEL_OPUS`, `MODEL_SONNET`, `MODEL_HAIKU`  
Tryb jednomodelowy: `HYBRID_MODELS_ENABLED=false` → wszyscy na Sonnet

---

## 3. Flow debaty

```
Brief → [Faza A0] DreamArchitect → 9 agentów równolegle → Syez → SSE stream
```

### Faza A0 — Architektura Marzenia (AKSJOMAT 1)
Przed uruchomieniem agentów system wywołuje `DreamArchitect`, który z briefu destyluje:
- `core_dream` — co naprawdę chcesz
- `value_anchor` — kotwica wartości
- `pillars` — 3–5 filarów
- `milestones` — kamienie milowe z datami
- `next_move` — najmniejszy konkretny ruch (≤60 min)
- `functionality_checklist` — lista odhaczalnych funkcjonalności (źródło prawdy dla AKSJOMATU 2)

Wynik emitowany jako SSE event `dream_architecture`, przekazywany do każdego agenta jako kontekst systemowy.

### 9 agentów — równolegle
Każdy dostaje: `[DreamArchitecture context] + [instrukcja agenta] + [AKSJOMAT 2 postscript] + [dyrektywa językowa]`

Format odpowiedzi: `{emoji} {name}: [obserwacja] → [konkretna sugestia]` (maks. 3 zdania)

### Syez — synteza
Dostaje bundle wszystkich 9 głosów, pisze **czystą prozę** po polsku (lub angielsku) zawierającą:
- Monitor napięć między agentami (sprzeczności leksykalne)
- Diagram Mermaid relacji
- Sekcję pytań otwartych (min. 4)
- Audyt domknięcia (co blokuje, smallest move ≤60 min)

Bloki JSON są sanitizowane przez `_sanitize_syez_output()`.

---

## 4. Tryby działania

| Tryb | Agenci | Max tokens Syez | Max tokens reszta | Opis |
|------|--------|-----------------|-------------------|------|
| `pelna` | 9 + Syez | 3000 | 2000–4000 | Standardowa pełna Rada |
| `marzen` | 9 + Syez | 3000 | 2000–4000 | Start od marzenia |
| `schematy` | 9 + Syez | 3000 | 2000–4000 | Agresywne przełamywanie blokad |
| `codzienny` | 4–5 + Syez | 1400 | 380 | Check-in ~5 min, tańsze |

**Kategorie briefu:** `decyzja` / `projekt` / `marzenie` / `schemat`

---

## 5. AKSJOMAT 2 — Doprowadzanie Do Końca

- Hard-lock `MAX_ACTIVE_PROJECTS` przy `category=projekt` — blokuje nowy projekt, jeśli stare są niedomknięte (HTTP 409)
- Syez ma wpleść audyt domknięcia w prozę; system waliduje jego obecność i przy braku wykonuje 1 re-prompt naprawczy
- Projekty mają stany: `dreaming → in_progress → at_risk → stuck → completed / archived_consciously`
- Brak stanu ABANDONED — archiwizacja wymaga uzasadnienia (`archived_reason`)
- Zobowiązania (`commitments`) z follow-up 72h, typy: `manual / auto_72h / stale_project`

---

## 6. API — endpointy

| Method | Path | Opis |
|--------|------|------|
| POST | `/debate/stream` | Główna debata, SSE stream |
| POST | `/debate/continue/stream` | Kontynuacja wątku |
| GET | `/history` | Lista debat (`limit` 1–200, opcjonalnie `q` — wyszukiwanie treści) |
| GET | `/debate/{id}` | Szczegóły debaty |
| GET | `/debate/{id}/export.md` | Eksport do Markdown |
| GET | `/debate/{id}/export.pdf` | Eksport do PDF (DejaVu) |
| GET | `/health` | Liveness |
| GET | `/health/ready` | Readiness (SQLite ping) |
| POST | `/commitment` | Utwórz zobowiązanie |
| GET | `/commitments/due` | Zobowiązania do follow-up |
| PATCH | `/commitment/{id}/complete` | Oznacz jako done |
| POST | `/commitment/{id}/release` | Zwolnij z uzasadnieniem |
| DELETE | `/commitment/{id}` | Zabronione (HTTP 405) |
| POST | `/admin/trigger-followups` | Ręczny wyzwalacz fazy 2 — gdy `ARCHITEKT_ADMIN_TOKEN` ustawiony: wymaga `Authorization: Bearer` |
| POST | `/dreams` | Utwórz marzenie |
| GET | `/dreams/{id}` | Szczegóły marzenia |
| POST | `/projects/{id}/functionality/{item_id}` | Odhacz element checklisty |
| POST | `/projects/{id}/complete` | Zamknij projekt |
| POST | `/projects/{id}/archive` | Archiwizuj świadomie |

SSE eventy w streamie: `dream_architecture` → `agent_voice` × 9 → `synthesis_chunk` → `debate_done`

---

## 7. Warstwa LLM — BaseAgent

- **Retry:** tenacity, 5 prób, exponential backoff + jitter (1–30s). Retry tylko na `RateLimitError` i `APIConnectionError` (nie na `BadRequestError` — fail fast)
- **Cache:** Redis, TTL 3600s, klucz = SHA256(context[:400] + model + temp + dream_id + language + mode)
- **Cost log:** append-only `cost_log.jsonl` (agent, model, tokeny, koszt USD, brief_hash)
- **Fallback:** brak klucza API lub wyczerpane retry → sync `contribute()` (hardcoded placeholder)
- **Agent evolution (P5):** rolling notatka z poprzednich debat per agent → wstrzykiwana jako prefix user-message

---

## 8. Baza danych (SQLite)

Tabele: `dreams`, `debates`, `agent_voices`, `dream_debate_link`, `projects`, `functionality_items`, `completion_audits`, `commitments`, `agent_evolution`

Migracje: inline w `init_db()` przez `ALTER TABLE` (idempotentne). DB path: `data/architekt.db` (override: `ARCHITEKT_DB_PATH`)

---

## 9. Stack

| Warstwa | Technologia |
|---------|-------------|
| Backend | Python + FastAPI, async (asyncio) |
| LLM | Anthropic SDK (AsyncAnthropic) |
| Cache | Redis (`redis.asyncio`) |
| DB | SQLite (`aiosqlite`) |
| Retry | tenacity |
| Streaming | SSE (StreamingResponse) |
| Rate limit | slowapi (debata POST / IP; wyłącznik `AW_DISABLE_RATE_LIMIT`) |
| Frontend | Tauri + React 19 + Vite + Tailwind (osobne repo) |

Zmienne środowiskowe (plik `ui/.env`, ładowany przez backend i Vite; opcjonalnie `AW_ENV_FILE`): `ANTHROPIC_API_KEY`, `XAI_API_KEY`, `LLM_BACKEND`, `REDIS_URL`, `ARCHITEKT_DB_PATH`, `AW_CORS_ORIGINS`, `HYBRID_MODELS_ENABLED`, `MODEL_OPUS/SONNET/HAIKU`, `COST_LOG_PATH`, `DAILY_COST_LIMIT_USD`, **`ARCHITEKT_API_KEY`**, **`ARCHITEKT_ADMIN_TOKEN`**, **`AW_RATE_DEBATE_PER_MINUTE`**, **`AW_DISABLE_RATE_LIMIT`**

---

## 10. Znane ograniczenia (v3.3)

1. ~~`/admin/trigger-followups` — brak auth~~ — opcjonalny Bearer: `ARCHITEKT_ADMIN_TOKEN` (patrz `docs/SECURITY_PRODUCTION.md`)
2. `_log_cost` — synchroniczny `open()` blokuje event loop pod obciążeniem
3. 10 bezpośrednich `aiosqlite.connect()` w generatorach SSE (poza `Depends(get_db)`)
4. ~~Brak górnej granicy na `?limit=` i `?within_hours=`~~ — clamp: `history.limit` ≤ 200, `dreams.limit` ≤ 100, `commitments/due.within_hours` ≤ 8760
5. `main.py` — 1750+ linii (planowany split na routery)
6. ~~Brak auth na żadnym endpoincie~~ — opcjonalny globalny Bearer: `ARCHITEKT_API_KEY` (middleware); sekret w bundle Vite nadal wymaga świadomej decyzji operatorskiej
7. Klucz API w przeglądarce (`VITE_ARCHITEKT_API_KEY` / localStorage) — używać tylko z zaufanymi klientami lub BFF
