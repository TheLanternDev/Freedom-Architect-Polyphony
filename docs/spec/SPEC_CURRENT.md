# Architekt Wolności — Pełna Specyfikacja Techniczna

> **Źródło prawdy:** ten dokument jest wyprowadzony **wyłącznie z faktycznego stanu kodu** (`main.py`, `agents/`, `core/`, `api/`, `db/`, `config/`), zweryfikowanego 2026-05-25. Nie pochodzi z wcześniejszych dokumentów `docs/` — gdzie kod i dokumenty się różnią, **rozstrzyga kod**.

---

## 0. Rozbieżności kodu↔docs (rozwiązane 2026-05-25)

Wszystkie poniższe zostały usunięte — `docs/ARCHITECTURE.md` i `SPEC_CURRENT.md` zsynchronizowane z kodem.

| # | Obszar | Było (stare docs) | Stan faktyczny (kod) | Status |
|---|--------|-------------------|----------------------|--------|
| 1 | Modele LLM | Hybryda Haiku/Sonnet/Opus | Jednolity `claude-sonnet-4-6` (`config/agent_models.py`) | ✅ poprawiono ARCHITECTURE.md |
| 2 | Integracje | Brak opisu | Router `/integrations` (Notion/Todoist/GCal) | ✅ opisano w sekcji 3 |
| 3 | Wersja | „v3.4" w docstringu | app = 3.3 (etykieta iteracji modeli, nie wersja) | ✅ przeredagowano |
| 4 | Role FA2 | 10 ról „Strategos/Operator/…" | Te same 9 agentów, biznesowe prompty (`business_fa2/config/roles.py`) | ✅ poprawiono ARCHITECTURE.md |

---

## 1. Rada — skład i orkiestracja

**Plik:** `agents/__init__.py`

`COUNCIL` zawiera **9 agentów** w stałej kolejności:

```
Relacjan, Kogit, Emojy, Deega, Smaty, Szow, Tai, Obver, Kidi
```

**Syez** = singleton-syntezator (`SYNTHESIZER = Syez()`), **świadomie poza Radą** (komentarz w kodzie: „Syez jako singleton-orchestrator, nie członek Rady"). `get_council()` zwraca kopię listy 9 agentów bez Syeza.

Każdy agent dziedziczy z `BaseAgent` (`agents/base_agent.py`), eksponuje `name`, `contribute(context)` (sync) i `acontribute(...)` (async).

---

## 2. Modele LLM per agent

**Plik:** `config/agent_models.py` (iteracja „jednolity model": jeden model dla wszystkich — spójność jakości i kosztów; wersja aplikacji = 3.3)

Alias: `_SONNET = os.getenv("MODEL_SONNET", "claude-sonnet-4-6")`. Wszyscy agenci i Syez używają tego samego modelu; różnicowane są jedynie `temperature` i `max_tokens`:

| Agent | model | temperature | max_tokens |
|-------|-------|-------------|------------|
| default | Sonnet 4.6 | 0.8 | 2000 |
| kogit | Sonnet 4.6 | 0.7 | 4000 |
| tai | Sonnet 4.6 | 0.6 | 4000 |
| deega | Sonnet 4.6 | 0.0 | 2000 |
| relacjan | Sonnet 4.6 | 0.8 | 2000 |
| emojy | Sonnet 4.6 | 0.8 | 2000 |
| obver | Sonnet 4.6 | 0.8 | 2000 |
| syez | Sonnet 4.6 | 0.5 | 3000 |
| szow | Sonnet 4.6 | 1.0 | 1500 |
| kidi | Sonnet 4.6 | 1.0 | 1500 |
| smaty | Sonnet 4.6 | 1.0 | 1500 |

- `_validate()` — fail-fast: temperatura musi być w `[0, 1]` (limit Anthropic API).
- `AGENT_MODEL_CONFIG_FA2` — wariant biznesowy: Syez podniesiony do `temperature=0.6, max_tokens=5000` (dłuższa analiza, unik timeoutu).
- `HYBRID_MODELS_ENABLED` (ENV, default `true`) — feature flag; obie tablice i tak wskazują Sonnet, więc realnie nie zmienia modelu, tylko ścieżkę wyboru configu.
- `get_model_config(agent_name, council_mode="personal")` — case-insensitive lookup; `council_mode="fa2"` → tablica FA2.

---

## 3. Kontrakt API (faktyczne dekoratory tras)

### Debata (SSE)

| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/debate/stream` | Strumieniuje pełną debatę Rady (9 agentów + Syez). |
| POST | `/debate/continue/stream` | Kontynuacja — wczytuje poprzednią debatę jako kontekst rodzica. |

**Payload `Brief`** (`main.py`, `class Brief(BaseModel)`):

| Pole | Typ / ograniczenie |
|------|---------------------|
| `description` | str, **min 20 / max 8000** znaków (+ `field_validator`) |
| `category` | `Literal["decyzja","projekt","marzenie","schemat"]`, default `decyzja` |
| `mode` | `Literal["pelna","marzen","schematy","codzienny"]`, default `pelna` |
| `language` | `Literal["pl","en"]`, default `pl` |
| `intention` | Optional[str], max 400 |
| `extra_context` | Optional[str], max 2000 |

**Payload kontynuacji:** `previous_debate_id` (int ≥ 1), `follow_up` (str, min 20 / max 2000). Kontynuacja dziedziczy `category`/`mode`/`intention` z rodzica.

Gdy `category == "projekt"` → uruchamiany jest hard-lock `MAX_ACTIVE_PROJECTS` (AKSJOMAT 2).

### Historia i szczegóły

| Metoda | Endpoint |
|--------|----------|
| GET | `/history` |
| GET | `/debate/{debate_id}` |
| GET | `/debate/{debate_id}/export.md` |
| GET | `/debate/{debate_id}/export.pdf` |

### Zobowiązania (Commitments)

| Metoda | Endpoint | Uwaga |
|--------|----------|-------|
| POST | `/commitment` | nowe zobowiązanie |
| GET | `/commitments/due` | otwarte z follow-upem w horyzoncie |
| PATCH | `/commitment/{commitment_id}/complete` | odhaczenie |
| POST | `/commitment/{commitment_id}/release` | wymaga `reason` ≥ 30 znaków |
| DELETE | `/commitment/{commitment_id}` | **zablokowany** — zwraca `shadow_no_silent_release` |

### Marzenia i Projekty

| Metoda | Endpoint |
|--------|----------|
| GET | `/dreams` |
| GET | `/dreams/{dream_id}` |
| GET | `/projects` |
| GET | `/projects/{project_id}` |
| GET | `/projects/{project_id}/commitments` |
| PATCH | `/projects/{project_id}/functionality/{item_id}` |
| POST | `/projects/{project_id}/complete` (422 gdy checklista < 100%) |
| POST | `/projects/{project_id}/archive` (wymaga `reason` ≥ 50 znaków) |

### Integracje (router `/integrations` — `api/routers/integrations.py`)

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/status` | Stan konfiguracji: `notion`, `todoist`, `gcal` (czy klucze/ID ustawione) |
| POST | `/notion/export` | Eksport zobowiązań → strony Notion (`https://api.notion.com/v1/pages`) |
| POST | `/todoist/export` | Eksport → zadania Todoist (`/rest/v2/tasks`, treść obcięta do 500 zn.) |
| POST | `/gcal/export` | Eksport → eventy Google Calendar (OAuth `creds_json`, summary do 200 zn.) |

**Payload `ExportRequest`** (wszystkie trzy POST):

```
ExportRequest:
  commitment_ids: list[int]   = []   (eksportowane są tylko te ID)
  dream_id:       str | null  = null
```

**Odpowiedź sukcesu** (HTTP 200) — `{"exported": [...]}`, jeden wpis per `commitment_id`, kształt per-kanał:

| Kanał | Wpis sukcesu | Wpis błędu (per item) |
|-------|--------------|------------------------|
| Notion | `{"commitment_id", "notion_page_id", "ok": true}` | `{"commitment_id", "ok": false, "error": <str>}` |
| Todoist | `{"commitment_id", "todoist_task_id", "ok": true}` | `{"commitment_id", "ok": false, "error": <str>}` |
| GCal | `{"commitment_id", "gcal_event_id", "ok": true}` | `{"commitment_id", "ok": false, "error": <str>}` lub `"error": "brak daty"` gdy zobowiązanie nie ma `due_at` |

**Mapowanie pól na zewnętrzne API:**
- Notion: `Name` ← `text[:200]`, `Status` ← `status` (select), `Due` ← `due_at[:10]` (jeśli jest). Tworzy stronę pod `database_id` z ENV.
- Todoist: `content` ← `text[:500]`, `due_string` ← data, opcjonalny `project_id` z `TODOIST_PROJECT_ID`.
- GCal: `summary` ← `text[:200]`, `date` ← `due_at[:10]`; kalendarz z `GCAL_CALENDAR_ID` (default `primary`).

**Błędy całego żądania** (HTTPException, przerywają eksport):

| Kod | Kanał | Warunek |
|-----|-------|---------|
| 400 | Notion | brak `NOTION_API_KEY` lub `NOTION_DATABASE_ID` w ENV |
| 400 | Todoist | brak `TODOIST_API_KEY` w ENV |
| 400 | GCal | brak `GCAL_CREDENTIALS_JSON` w ENV (service account) |
| 500 | GCal | brak pakietu `cryptography` (wymagany do podpisu JWT OAuth) |

**Edge-case (po cichu pomijane, nie błąd):** `commitment_id` którego nie ma w `list_commitments_due(within_hours=8760)` → `continue`, brak wpisu w `exported`. To znaczy: eksport obejmuje tylko zobowiązania z follow-upem w horyzoncie ~365 dni; starsze/poza horyzontem nie zostaną wyeksportowane mimo podania ID.

Klucze i ID czytane wyłącznie z ENV (`_notion_key`, `_todoist_key`, `_gcal_id`).

### Voice (router `/voice` — `api/routers/voice.py`)

| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/transcribe` | Transkrypcja audio. Backend: OpenAI Whisper (`_transcribe_openai`) lub lokalny (`_transcribe_local`), wybór przez `_whisper_backend()`. |

### Personal (router `/personal` — `api/routers/personal.py`)

| Metoda | Endpoint |
|--------|----------|
| GET | `/onboarding/questions` |
| GET | `/ritual/daily` |

### Auth (router `/auth` — `api/routers/auth.py`)

`POST /register`, `POST /login`, `POST /refresh`, `POST /revoke`, `GET /me`.

### Meta / Admin

| Metoda | Endpoint |
|--------|----------|
| GET | `/health`, `/health/ready` |
| GET | `/costs/status` |
| GET | `/edition` |
| POST | `/admin/trigger-followups` |
| POST | `/admin/rebuild-evolution` |
| POST | `/generate` (**legacy** v3.1) |
| GET | `/` oraz `/{full_path:path}` (catch-all SPA) |

---

## 4. Zdarzenia SSE (faktycznie emitowane)

Helper `api/services/_sse.py`:
```python
def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

Eventy emitowane w `api/services/debate_orchestrator.py` i guardach:

```
agent_start, agent_chunk, agent_done,
live_tensions,
project_state,
dream_architecture_error,
synthesis_start, synthesis_chunk, synthesis_heartbeat, synthesis_done, synthesis_structured,
completion_audit_violation,
safety_halt,
budget_soft_warning_sse, budget_hard_block
```

> **Uwaga:** zestaw eventów różni się od listy w starej specyfikacji — np. budżet to `budget_soft_warning_sse` / `budget_hard_block` (nie `budget_warning`); dochodzi `dream_architecture_error`.

---

## 5. AKSJOMATY (stałe i mechanizmy z kodu)

### AKSJOMAT 1 — Architektura Marzenia
**Plik:** `core/dream_architect.py`. Faza A0 destyluje `Brief` w obiekt `DreamArchitecture` przed uruchomieniem Rady; wstrzykiwana do promptów agentów i Syeza, zapisywana w tabeli `dreams`. Tryb `codzienny` używa deterministycznego fallbacku bez wywołania LLM.

### AKSJOMAT 2 — Doprowadzanie Projektów Do Końca
**Plik:** `core/completion_enforcer.py`. Stałe (z ENV-override):

| Stała | Wartość | Rola |
|-------|---------|------|
| `MAX_ACTIVE_PROJECTS` | `1` | twardy zamek antyfragmentacyjny (HTTP 409) |
| `MIN_ARCHIVE_REASON_LEN` | `50` | świadoma archiwizacja |
| `MIN_COMMITMENT_RELEASE_REASON_LEN` | `30` (`commitment_service.py`) | zwolnienie zobowiązania |
| `STALE_DAYS_STUCK` | `30` | projekt bez postępu → `stuck` (14 dni → `at_risk`) |

Mechanizmy:
1. **Hard-lock projektów** — `validate` rzuca przy `len(active) >= limit`.
2. **Checklista 100%** — `complete` → 422 gdy pozostały otwarte pozycje (`AKSJOMAT 2: Pozostało N pozycji`).
3. **Audyt prozą Syeza** — `validate_syez_prose_completion_audit()`; brak → re-prompt (`AGENT_COMPLETION_POSTSCRIPT`) → po drugiej nieudanej próbie event `completion_audit_violation`, synteza zapisywana z flagą.
   - **Próg (2026-05-25):** wymaga rdzenia `remaining` **i** `next_move` + łącznie ≥3 z 4 klastrów. Sam znak `?` nie liczy się jako pytanie otwarte (musi być przy markerze pytania).
   - **Granica heurystyki:** to detekcja leksykalna, nie NLP — **nie rozumie zaprzeczeń** (np. „bez najmniejszego ruchu" trafia w klaster `next_move`). Bariera minimalna przeciw pustym syntezom, nie pełna weryfikacja treści. Wzmocnienie → tu, gdy Syez zacznie przechodzić mimo pustki.
4. **Brak DELETE zobowiązań** — `shadow_no_silent_release` z `min_reason_chars`.
5. **Brak stanu ABANDONED** — `ProjectStatus.ARCHIVED_CONSCIOUSLY` jedynym wyjściem.

`ProjectStatus` ∈ `{dreaming, in_progress, at_risk, stuck, completed, archived_consciously}`.

---

## 6. Tryby debaty

**Plik:** `api/services/mode_helpers.py`

| Tryb | Specyfika |
|------|-----------|
| `pelna` | domyślny — pełna Rada |
| `marzen` | prefix pełnej ekspansji wizji bez redukcji do realizmu |
| `schematy` | prefix `[Tryb Przełamywania Schematów]`; nazwij marzenie zasłonięte przez schemat; auto-commitment `auto_72h` |
| `codzienny` | check-in ~5 min, fallback A0 bez LLM, zwarta synteza |

---

## 7. Model danych (`db/schema.sql`, dosłownie)

Wszystkie tabele: `tenant_id TEXT NOT NULL DEFAULT 'default'` (multi-tenant).

### dreams (TEXT PK, UUID v4)
`raw_brief, core_dream, value_anchor, pillars_json, milestones_json, next_move_json, completion_criteria_json, functionality_checklist_json`, `status ∈ {living, fulfilled, released}` (default `living`), `fulfilled_at`.

### debates (INTEGER AUTOINCREMENT)
`category` CHECK ∈ {decyzja,projekt,marzenie,schemat}; `mode` CHECK ∈ {pelna,marzen,schematy,codzienny}; `brief_description, intention, extra_context`; `dream_id` (FK SET NULL); `parent_debate_id` (FK SET NULL — wątki); `full_synthesis_json`, `synthesis_text` (backup), `cost_usd`. Indeksy: `dream_id`, `created_at`.

### dream_debate_link
PK `(dream_id, debate_id)`, oba FK CASCADE — wiele debat per marzenie.

### agent_voices (INTEGER AUTOINCREMENT)
`debate_id` (FK CASCADE), `agent_name`, `voice_text`, `tokens_in`, `tokens_out`, `cost_usd`. Indeks: `debate_id`.

### projects (INTEGER AUTOINCREMENT)
`dream_id` (FK CASCADE), `status` CHECK ∈ {dreaming,in_progress,at_risk,stuck,completed,archived_consciously} (default `dreaming`), `started_at, last_progress_at, completed_at, archived_reason, archived_at`, **`UNIQUE(dream_id)`** — 1 projekt per marzenie. Indeks: `status`.

### functionality_items (INTEGER AUTOINCREMENT)
`project_id` (FK CASCADE), `description`, `is_done` CHECK (0,1), `done_at`, `evidence_url`. Indeks: `project_id`.

### completion_audits (INTEGER AUTOINCREMENT)
`project_id` (FK CASCADE), `debate_id` (FK SET NULL), `remaining_json`, `audited_at`. Indeks: `project_id`.

### commitments (INTEGER AUTOINCREMENT)
`debate_id` (FK SET NULL), `project_id` (FK SET NULL), `text`, `due_at`, `follow_up_at`, `trigger_type` CHECK ∈ {manual,auto_72h,stale_project} (default `manual`), `needs_attention` CHECK (0,1), `release_reason`, `status` CHECK ∈ {open,completed,rescheduled,released} (default `open`), `completed_at`, `created_at`. Indeksy: `project_id`, `status`, `follow_up_at`.

### agent_evolution
PK `(agent_name, tenant_id)`, `note_md`, `updated_at` — rolling notatka ewolucyjna per agent.

### users (TEXT PK = username)
`pw_hash, salt, tenant_id, display_name, created_at`.

Backend: SQLite (`db/schema.sql`) lub PostgreSQL (`db/schema_postgres.sql` przez `db/backend.py` / `pg_wrap.py`), `tenant.py` izoluje tenanta.

### Różnice SQLite vs. PostgreSQL

Oba schematy mają **te same 10 tabel, te same kolumny i te same CHECK-i enumów** — model logiczny jest identyczny (celowo, by `db.backend` był cienki). Różnice są wyłącznie w typach natywnych:

| Konstrukcja | SQLite (`schema.sql`) | PostgreSQL (`schema_postgres.sql`) |
|-------------|-----------------------|-------------------------------------|
| PK autoinkrementowany | `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| Znaczniki czasu | `TEXT` + `DEFAULT (datetime('now'))` | `TIMESTAMPTZ` + `DEFAULT NOW()` |
| Flagi 0/1 (`is_done`, `needs_attention`) | `INTEGER … CHECK (… IN (0,1))` | `SMALLINT … CHECK (… IN (0,1))` |
| Kolumny `*_json` | `TEXT` (JSON jako string) | `TEXT` — **nie JSONB** |

**Świadome decyzje:** (1) PG **nie** używa `JSONB` — JSON trzymany jako `TEXT`, identycznie jak w SQLite (brak indeksowania/operatorów JSON po stronie bazy; parsowanie w warstwie aplikacji). (2) PG **nie** używa `BOOLEAN` — flagi pozostają `SMALLINT 0/1`, by kod repo był wspólny dla obu backendów. (3) Enumy egzekwowane przez `CHECK IN (...)` w obu (nie typ `ENUM` PG). TEXT PK (`dreams.id`, `users.username`) jest taki sam w obu.

---

## 8. Bezpieczeństwo

### Safety halt (`core/safety.py`)
`safety_check()` przed Radą: normalizacja NFKD→ASCII lowercase, regex po granicach słów (`\b`) na liście fraz kryzysowych PL+EN → event `safety_halt` z nr 116 123; debata **nie startuje**. Filozofia: *Zdrowie Patryka > postęp projektu.*

### Auth (`api/routers/auth.py`, `api/auth_identity.py`, `api/http_guard.py`)
JWT multi-tenant; rejestracja/login z hashem hasła; `http_guard` wyciąga `tenant_id` z JWT i wstrzykuje do kontekstu zapytań DB. Refresh/revoke wymagają Redis (blocklist JTI).

---

## 9. Budżet i koszty

**Pliki:** `api/services/budget_guard.py`, `core/cost_tracking.py`

- **Hard block:** `ensure_hard_budget_or_raise()` → `evaluate_hard_budget(load_budget_snapshot())`. ENV: `DAILY_BUDGET_HARD_USD`, `MONTHLY_BUDGET_HARD_USD`. Przekroczenie → event `budget_hard_block`, Rada nie startuje.
- **Soft warning:** próg `DAILY_BUDGET_USD` → event `budget_soft_warning_sse`; Rada nadal działa („świadomy wybór").
- Log kosztów: `cost_log.jsonl`; `GET /costs/status` raportuje stan.

### Maintenance scheduler (Faza 2 / AKSJOMAT 2)

W `lifespan` (`main.py`) działa opcjonalna pętla w tle egzekwująca AKSJOMAT 2.

- **`AW_MAINTENANCE_INTERVAL_SEC`** (int, default **0**) — `0`/brak = **wyłączone**; `>0` = co N sekund uruchamia `run_phase2_maintenance` (`apply_followup_nudges` + `sync_stale_projects`: przeterminowane follow-upy oraz przejścia `at_risk`/`stuck` z zobowiązaniami `stale_project`).
- Implementacja: `asyncio.create_task` + `asyncio.sleep` (bez frameworka schedulera). Idempotentne (anty-dup `has_open_stale_nudge`), nieblokujące, anulowane przy zamknięciu. Log `[Maintenance] Running scheduled tasks...` per cykl; na starcie log o stanie (włączone/wyłączone).
- **Produkcja:** ustaw `> 0` (np. `86400` = 24h) — inaczej stale-detection i follow-upy nie odpalą się automatycznie. To samo wykonuje ręcznie `POST /admin/trigger-followups`.

---

## 10. Monitor napięć (`core/live_tensions.py`)

Heurystyka leksykalna: tokenizacja głosów (≥4 znaki), Jaccard per para agentów, `intensity = 1.0 − 2.2 × jaccard` (clamp 0.22–1.0), sortowanie malejąco, top par → event `live_tensions`. To miara rozbieżności tematycznej, **nie** sentymentu.

---

## 11. Edycja biznesowa — Freedom Architect 2.0 (`business_fa2/`)

**Mount:** `main.py` linia 255 — `app.mount("/business", _business_app, name="freedom_architect_2_business")`. Edycja dostępna jako `"business"` w `/edition` (`business_mount = "/business"`). Wybór trybu również przez nagłówek **`X-Council-Mode: fa2`** (`_council_mode_from_request`).

**Architektura (korekta vs. `docs/ARCHITECTURE.md`):** FA2 **nie wprowadza nowych ról** typu „Strategos/Operator/Growth". To **przeramowanie tej samej 9-osobowej Rady** w kontekst biznesowy — `business_fa2/config/roles.py` definiuje `_FA2_BASE_ROLES` dla tych samych agentów: **Relacjan, Kogit, Emojy, Deega, Smaty, Szow, Tai, Obver, Kidi**. Syez pozostaje syntezatorem (z podniesionym budżetem tokenów — patrz `AGENT_MODEL_CONFIG_FA2`, sekcja 2).

**Endpointy sub-app** (`business_fa2/api/main.py`):

| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/business/debate/stream` | Proxy — wymusza `council_mode="fa2"` na głównym pipeline (`m._stream_debate(brief, council_mode="fa2")`). Ma fallback gdy główny moduł niedostępny. |
| GET | `/business/health` | Health sub-appa FA2. |

**Konteksty biznesowe** (`KontekstBiznesu`, Literal): `"produkt fizyczny"`, `"usługa B2B"`, `"SaaS"`, `"marketplace"`. `get_fa2_roles(kontekst)` rozszerza prompty **Smaty** (`_SMATY_KONTEKST`) i **Obver** (`_OBVER_KONTEKST`) o specyfikę branży — np. dla SaaS: NRR > 110% jako sygnał product-market fit, CAC/LTV > 3x. `FA2_BUSINESS_ROLES` = alias backward-compat dla `_FA2_BASE_ROLES`.

**Tryby** (`business_fa2/config/modes.py`): te same co edycja osobista — `VALID_MODES = ("pelna","marzen","schematy","codzienny")`. `MODE_AGENTS`: `pelna/marzen/schematy → None` (wszyscy 9), `codzienny → ["Kogit","Emojy","Smaty","Obver"]` (4 agenci).

**Ustawienia** (`business_fa2/config/settings.py`, `get_fa2_settings()`): `FA2_LLM_CONCURRENCY=4`, `cache_ttl=604800` (7 dni), `rate_limit=30`. ⚠️ `FA2_DATABASE_PATH` (default `data/fa2.db`) jest **zadeklarowane, ale nieużywane** — proxy FA2 woła `main._stream_debate`, który korzysta ze **wspólnej** bazy (`get_db`). Izolacja kontekstów osobisty↔biznesowy realizowana jest na poziomie **ewolucji agentów** (sufiks tenanta `:fa2` w `list/merge_agent_evolution_snippet`), nie osobnej bazy debat. Debaty obu trybów współdzielą tabele (rozróżniane przez `mode`/`category`).

**Prompty:** `business_fa2/prompts/context.py` (ramowanie: team, legal/IP, GTM, fundraising, ryzyko wykonania, konkretne metryki i trade-offy), `business_fa2/prompts/synthesis.py` (synteza pod model operacyjny, struktura kosztów i przychodów).

---

## 12. Cykl ewolucji agentów (`core/agent_learner.py`, Faza 3)

Warstwa ucząca: po debatach agenci budują **rolling notatkę** kluczowych obserwacji z własnych wcześniejszych głosów; notatka wraca do nich jako kontekst w kolejnych debatach. Stałe: `MAX_EVOLUTION_NOTE_LEN=2000`, `MAX_SNIPPETS_PER_AGENT=20`, `SNIPPET_TARGET_LEN=200`.

**Flaga:** `AW_AGENT_EVOLUTION` (ENV, default `1`); wartości `0/false/no/off` wyłączają cały mechanizm (`_agent_evolution_enabled()` w `debate_orchestrator.py`).

**Funkcje (`core/agent_learner.py`):**

| Funkcja | Rola |
|---------|------|
| `extract_evolution_snippet(agent, voice)` | Kompresja głosu do ~200 zn.: pierwsze zdanie `(...)` ostatnie. Zwraca `""` gdy tekst < 30 zn. |
| `merge_evolution_notes(existing, snippet)` | Dokleja `[YYYY-MM-DD] snippet`; FIFO do 20 wpisów; twardy trim do 2000 zn. (zostawia ≥3 linie). |
| `rebuild_evolution_for_agent(db, agent, repo, max_debates=30)` | Odbudowa notatki z `repo.list_recent_voices_for_agent` (ostatnie 30 głosów). |
| `run_full_evolution_cycle(db, repo, agents)` | Pełny rebuild dla wszystkich; zapis przez `repo.merge_agent_evolution_snippet(... f"[rebuild] {note[-200:]}")`. |

> **Usunięto (2026-05-25):** `suggest_temperature_adjustment` — martwy kod bez infrastruktury ocen (`recent_ratings` nie istniało w bazie ani UI). Decyzja świadoma wg AKSJOMATU 2: zamiast cicho zalegać, zostanie dopisany dopiero gdy powstanie tor zbierania ocen agentów.

**Pełny tor (cztery warstwy):**
1. **Zapis po debacie** — `debate_orchestrator.py` (~478): dla każdego głosu kompresja `extract_evolution_snippet(name, voice)` (zdaniowa, ~200 zn.) → `repo.merge_agent_evolution_snippet(db, name, snippet)` (gdy flaga on). Repo (`db/connection.py:476`) nakłada własny `snippet_cap=380`, prefiks `•`, FIFO do `total_cap=2600` i pomija głosy `[błąd`/`[error`. **Dwa formaty zapisu tej samej tabeli:** live → `• <zdaniowy snippet>`; rebuild → `[YYYY-MM-DD] <snippet>`. Kompresja zdaniowa w live została ujednolicona z rebuild (wcześniej repo obcinał surowy głos twardo na 380 zn., często w połowie zdania).
2. **Wczytanie do promptu** — `debate_orchestrator.py` (~274): `repo.list_agent_evolution(db)` → mapa agent→notatka → przekazywana jako `evolution_note`.
3. **Wstrzyknięcie** — `agents/base_agent.py` (~175): notatka jako prefiks user-message z nagłówkiem „[EWOLUCJA Rady — skrót z Twoich wcześniejszych wypowiedzi (tylko TY)…]". Agent widzi **wyłącznie własną** historię, nie innych.
4. **Rebuild on-demand** — `POST /admin/rebuild-evolution` (`main.py:858`): chroniony `ARCHITEKT_ADMIN_TOKEN` (Bearer, `hmac.compare_digest`); wywołuje `run_full_evolution_cycle` dla `COUNCIL`; zwraca `{"ok": true, "agents_updated": [...]}`.

**Persystencja:** tabela `agent_evolution` PK `(agent_name, tenant_id)`, kolumna `note_md`. Migracja schematu: `db/connection.py:_migrate_agent_evolution_table`.

---

## 13. Pozostałe moduły

- `core/autonomy.py`, `core/analytics.py`, `core/identity.py` — odpowiednio: polityka autonomii, analityka, model tożsamości (cache, miss-tolerant).
- `core/debate_export.py`, `core/debate_export_pdf.py` — eksport MD/PDF.
- `personal_v1/` — rytuały osobiste (m.in. `rituals/zgodnosc.py`).

---

## Known Gaps (nadal otwarte)

- [x] ~~JSON Schema per event SSE (formalny payload)~~ — [`sse_events.schema.json`](sse_events.schema.json) (20 eventów, Draft 2020-12).
- [x] ~~Pełna dokumentacja payloadów `/integrations`~~ — opisana w sekcji 3 (`ExportRequest`, odpowiedzi sukcesu/błędu, edge-case horyzontu).
- [x] ~~Specyfikacja `business_fa2`~~ — opisana w sekcji 11.
- [x] ~~Opis `core/agent_learner.py` (cykl ewolucji)~~ — opisany w sekcji 12.
- [x] ~~Diagram sekwencji pełnego flow SSE (POST → debate_done)~~ — [`sse_flow.mermaid`](sse_flow.mermaid).
- [x] ~~Różnice `schema_postgres.sql` vs. SQLite~~ — opisane w sekcji 7.
- [x] ~~Ujednolicenie wersji v3.3/v3.4~~ — wersja aplikacji = **3.3** (spójna: `main.py`, `/health`). „v3.4" w `config/agent_models.py` była etykietą iteracji modeli, nie wersją app — przeredagowano.

## Decyzje wstrzymane (świadoma archiwizacja, AKSJOMAT 2 — nie porzucenie)

- **Druga tura konfrontacji Rady (2026-05-25).** Prototyp gotowy i przetestowany (`api/services/confrontation.py`, `tests/test_confrontation_prototype.py`, harness `_tools/confrontation_live_ab.py`). Live A/B na 1 briefie: efekt realny ale subtelny — R2 daje czytelniejsze obozy/sojusze + 1 deklarowaną rewizję, kosztem ostrości pojedynczego audytu; +9 wywołań LLM. **Decyzja: NIE integrować do `_phase_council`.** Dowód z 1 briefu niewystarczający względem kosztu. **Warunek powrotu:** gdy będzie potrzeba i budżet na A/B n≥3–5 briefów pokazujący powtarzalnie ≥2 rewizje i wyraźniejszą strukturę napięć. Prototyp pozostaje za flagą `AW_COUNCIL_DEBATE_ROUNDS` (domyślnie 1 = bez zmian), gotowy do wznowienia bez przepisywania.
