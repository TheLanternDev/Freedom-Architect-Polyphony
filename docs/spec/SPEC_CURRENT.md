# Architekt Wolności v3.3 — Specyfikacja Techniczna

> Wygenerowano z kodu źródłowego: [`main.py`](../../main.py), [`core/`](../../core/), [`api/`](../../api/), [`db/`](../../db/).

---

## 1. Kontrakt API

### Debata (SSE)

| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/debate/stream` | Strumieniuje pełną debatę Rady (9 agentów + Syez). Rate-limited. |
| POST | `/debate/continue/stream` | Kontynuacja wątku — wczytuje poprzednią debatę jako kontekst. |

Payload (`Brief`): `description` (20–8000 zn.), `category` ∈ {decyzja, projekt, marzenie, schemat}, `mode` ∈ {pelna, marzen, schematy, codzienny}, `language` ∈ {pl, en}, opcjonalnie `intention`, `extra_context`.

**Zdarzenia SSE:** `dream_architecture`, `project_state`, `debate_start`, `agent_start`, `agent_chunk`, `agent_done`, `live_tensions`, `synthesis_start`, `synthesis_chunk`, `synthesis_heartbeat`, `synthesis_done`, `synthesis_structured`, `completion_audit_violation`, `commitment_created`, `budget_warning`, `safety_halt`, `stream_error`, `debate_done`.

### Historia i szczegóły

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/history?limit=40&q=` | Lista debat (paginacja + full-text search). |
| GET | `/debate/{id}` | Pełen zapis: metadane + głosy + synteza + zobowiązania. |
| GET | `/debate/{id}/export.md` | Eksport Markdown. |
| GET | `/debate/{id}/export.pdf` | Eksport PDF. |

### Zobowiązania (Commitments)

| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/commitment` | Nowe zobowiązanie (ręczne lub powiązane z debatą/projektem). |
| GET | `/commitments/due?within_hours=24` | Otwarte zobowiązania z follow-up w horyzoncie. |
| PATCH | `/commitment/{id}/complete` | Odhaczenie z opcjonalnym evidence. |
| POST | `/commitment/{id}/release` | Zwolnienie — wymaga `reason` ≥ 30 znaków (AKSJOMAT 2). |
| DELETE | `/commitment/{id}` | **Celowo zablokowany** (422) — brak cichego usuwania. |

### Marzenia i Projekty

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/dreams?limit=50` | Lista marzeń z projektem i statystykami. |
| GET | `/dreams/{dream_id}` | Szczegóły marzenia + powiązane debaty. |
| GET | `/projects` | Aktywne projekty + completion_ratio + dni bez postępu. |
| GET | `/projects/{id}` | Szczegóły projektu (functionality items). |
| GET | `/projects/{id}/commitments` | Oś czasu zobowiązań projektu. |
| PATCH | `/projects/{id}/functionality/{item_id}` | Odhaczenie pozycji checklisty (+ evidence_url). |
| POST | `/projects/{id}/complete` | Zamknięcie — 422 gdy checklista < 100%. |
| POST | `/projects/{id}/archive` | Archiwizacja świadoma — wymaga `reason` ≥ 50 znaków. |

### Meta / Admin

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/health` | Status systemu (wersja, agenci, redis, db, llm_backend). |
| GET | `/health/ready` | Readiness probe (ping DB). |
| GET | `/costs/status` | Status kosztów LLM (z `cost_log.jsonl`). |
| GET | `/edition` | Dostępne tryby: personal / business. |
| POST | `/admin/trigger-followups` | Wymusza maintenance: follow-upy + stale sync (Bearer token). |
| POST | `/admin/rebuild-evolution` | Przebudowa rolling notatek ewolucyjnych agentów. |
| POST | `/generate` | **Legacy** v3.1 — zastąpiony przez `/debate/stream`. |

### Personal / Voice / Auth (routery opcjonalne)

- `GET /personal/onboarding/questions` — 20 pytań onboarding.
- `GET /personal/ritual/daily` — pytania poranne + wieczorne.
- Router `/auth` — rejestracja/login (JWT, multi-tenant).
- Router `/voice` — voice input (transkrypcja).
- Router `/integrations` — webhook/integracje zewnętrzne.

---

## 2. Model danych

### DreamArchitecture ([`core/dream_architect.py`](../../core/dream_architect.py))

```
DreamArchitecture:
  raw_brief: str
  core_dream: str          — "o co tu naprawdę chodzi" (1 zdanie)
  value_anchor: str        — "dlaczego to ma znaczenie" (1 zdanie)
  pillars: list[str]       — 3–7 filarów spełnienia
  milestones: list[Milestone]  — {title, due?, why_it_matters}
  next_move: NextMove      — {action, when, smallest_form}
  completion_criteria: list[str]  — jakościowe kryteria spełnienia
  functionality_checklist: list[str]  — KONKRETNE wymogi DZIAŁANIA (AKSJOMAT 2)
```

> **Uwaga:** UUID (`dream_id`) jest nadawany przy INSERT do tabeli `dreams`, nie jest częścią obiektu domenowego `DreamArchitecture`.

### Project ([`core/completion_enforcer.py`](../../core/completion_enforcer.py))

```
Project:
  id: int
  dream_id: str (FK → dreams)
  status: ProjectStatus ∈ {dreaming, in_progress, at_risk, stuck, completed, archived_consciously}
  started_at, last_progress_at, completed_at, archived_at: ISO datetime?
  archived_reason: str?
  functionality: list[FunctionalityItem]
```

**Stan ABANDONED nie istnieje** — wyjście wymaga świadomej archiwizacji.

### FunctionalityItem

```
FunctionalityItem:
  id: int
  project_id: int
  description: str
  is_done: bool
  done_at: ISO datetime?
  evidence_url: str?
```

### CompletionAudit (tabela `completion_audits`)

Zapis audytu domknięcia na każdą syntezę Syeza — `remaining_json` zawiera otwarte pozycje checklisty.

### Commitment (tabela `commitments`)

```
Commitment:
  id, debate_id?, project_id?, text, due_at?, follow_up_at?
  trigger_type ∈ {manual, auto_72h, stale_project}
  needs_attention: 0|1
  status ∈ {open, completed, rescheduled, released}
  release_reason: str? (min 30 znaków)
```

---

## 3. AKSJOMATY

### AKSJOMAT 1 — Architektura Marzenia

**Plik:** [`core/dream_architect.py`](../../core/dream_architect.py)

**Działanie:** Przed uruchomieniem 9 agentów Rady, brief Patryka przechodzi przez *fazę A0* — destylację marzenia (wywołanie LLM lub deterministyczny fallback). Wynikiem jest `DreamArchitecture`, która:
1. Jest emitowana jako event SSE `dream_architecture`.
2. Jest wstrzykiwana do system-promptu każdego agenta (`as_agent_context()`).
3. Jest przekazywana Syezowi jako kontekst nadrzędny (`for_syez()`).
4. Jest zapisywana w tabeli `dreams` (SQLite/Postgres).

**Przykład fallbacku (tryb codzienny):** brak wywołania LLM — użyty `_fallback_dream()` z hardkodowanymi filarami i milestones. Oszczędność ~1 wywołania Sonnet.

### AKSJOMAT 2 — Doprowadzanie Projektów Do Końca

**Plik:** [`core/completion_enforcer.py`](../../core/completion_enforcer.py)

**Działanie:**
1. **Hard-lock projektów:** `MAX_ACTIVE_PROJECTS=1` — nie da się rozpocząć nowego projektu gdy aktywny istnieje (HTTP 409).
2. **Wymuszenie checklisty:** `POST /projects/{id}/complete` zwraca 422 gdy `functionality_checklist` < 100%.
3. **Audyt w syntezie:** Syez MUSI w prozie czytelnie zawrzeć audyt domknięcia. Brak → re-prompt naprawczy → `completion_audit_violation` event.
4. **Stale detection:** Projekty bez postępu: 14 dni → `at_risk`, 30 dni → `stuck`. Maintenance tworzy zobowiązania `stale_project` (głos Deegi/Szowa).
5. **Brak DELETE:** Zobowiązań nie można usunąć — jedynie zwolnić z uzasadnieniem ≥ 30 znaków.
6. **Brak ABANDONED:** Archiwizacja wymaga `reason` ≥ 50 znaków (`archived_consciously`).

**Przykład (HTTP 409 przy próbie nowego projektu):**
```json
{"kind": "active_project_limit", "max": 1, "active_projects": [...], "message_pl": "Najpierw dokończ..."}
```

#### Mechanizm re-promptu (completion audit)

Gdy `validate_syez_prose_completion_audit()` nie znajdzie audytu domknięcia w syntezie Syeza:

1. Orkiestrator łapie `CompletionViolation` i wykonuje **max 2 próby** (oryginał + 1 retry).
2. Przy retry do payloadu Syeza doklejany jest `AGENT_COMPLETION_POSTSCRIPT` — jawne przypomnienie o wymogu audytu w prozie.
3. Jeśli druga próba również nie przechodzi walidacji → emitowany jest event SSE `completion_audit_violation` z treścią naruszenia. Synteza jest mimo to zapisywana (z flagą ostrzegawczą).

Plik: [`api/services/debate_orchestrator.py`](../../api/services/debate_orchestrator.py), linie ~440–520.

---

## 4. Tryby debaty

| Tryb | Agenci | Faza A0 | Orkiestracja | Specyfika |
|------|--------|---------|--------------|-----------|
| `pelna` | 9 + Syez | LLM destylacja | Pełna debata Rady | Domyślny tryb. |
| `marzen` | 9 + Syez | LLM wzmocniony | j.w. + prefix "[Tryb Marzeń] pełna ekspansja wizji" | Nie redukuj do realizmu przed nazwaniem. |
| `schematy` | 9 + Syez | LLM destylacja | j.w. + agresywny Szow/Deega | Wymuszony output "Dziś zrobię…" + auto-commitment 72h. |
| `codzienny` | 4 (Kogit, Emojy, Smaty, Obver) + Syez | Fallback (bez LLM) | Check-in ~5 min | Maks 2 zdania/agent; pytanie dnia z puli 7. Tańsze max_tokens. |

**Różnice w orkiestracji:**
- `codzienny`: `_LIGHT_MODE_AGENTS`, brak wywołania LLM A0, zwarta synteza (~650–900 słów).
- `schematy`: automatyczne `insert_commitment` z `trigger_type=auto_72h` i `follow_up_at` = +72h. Prefix `[Tryb Przełamywania Schematów]`.
- `marzen`: prefix zachęcający do pełnej ekspansji bez redukowania.

---

## 5. Persistence

### SQLite Schema ([`db/schema.sql`](../../db/schema.sql))

| Tabela | Klucz | Rola |
|--------|-------|------|
| `dreams` | TEXT PK (UUID) | Architektura Marzenia (JSON blobs w kolumnach `*_json`). |
| `debates` | INTEGER AUTOINCREMENT | Cykl Rady (brief, synteza, koszt). FK → dreams. |
| `dream_debate_link` | (dream_id, debate_id) | Wiele debat per marzenie. |
| `agent_voices` | INTEGER AUTOINCREMENT | Głosy agentów per debata. |
| `projects` | INTEGER AUTOINCREMENT | Realizacja marzenia. 1:1 z dream (UNIQUE dream_id). |
| `functionality_items` | INTEGER AUTOINCREMENT | Checklista per projekt. |
| `completion_audits` | INTEGER AUTOINCREMENT | Audyty domknięcia per debata×projekt. |
| `commitments` | INTEGER AUTOINCREMENT | Zobowiązania (open/completed/released). |
| `agent_evolution` | (agent_name, tenant_id) | Rolling notatka ewolucyjna per agent. |
| `users` | TEXT PK (username) | Multi-user auth (Faza 4). |

Wszystkie tabele mają `tenant_id TEXT NOT NULL DEFAULT 'default'` (multi-tenant).

### Repo functions ([`db/`](../../db/))

Asynchroniczne funkcje w `db.repo` (wzorzec repository): `insert_dream`, `ensure_project_for_dream`, `insert_debate`, `save_voice`, `save_synthesis`, `save_completion_audit`, `insert_commitment`, `complete_commitment`, `release_commitment`, `mark_functionality_done`, `update_project_status`, `list_active_projects`, `get_project`, `list_debates_recent`, `list_commitments_due`, `touch_project_last_progress`, `merge_agent_evolution_snippet`, `list_agent_evolution`.

Backend-agnostic: SQLite (domyślnie) lub PostgreSQL (`DATABASE_URL` → `db.backend`).

---

## 6. Bezpieczeństwo i Safety

### Safety halt ([`core/safety.py`](../../core/safety.py))

Przed uruchomieniem Rady cały brief (description + intention + extra_context) przechodzi przez `safety_check()`:
1. Tekst normalizowany (NFKD → ASCII lowercase).
2. Dopasowanie regex po granicach słów (`\b`) — lista fraz kryzysowych (PL + EN): samobójstwo, samookaleczenie, utrata woli życia.
3. Trafienie → SSE event `safety_halt` z komunikatem wsparcia (nr tel. 116 123) + debata **nie startuje**.

Filozofia: *Zdrowie Patryka > postęp projektu.*

### Auth (JWT multi-tenant) ([`api/routers/auth.py`](../../api/routers/auth.py))

| Endpoint | Opis |
|----------|------|
| `POST /auth/register` | Rejestracja — Argon2id hash, `tenant_id` = SHA256(username)[:16]. 5/min. |
| `POST /auth/login` | Login — weryfikacja Argon2id (lub legacy PBKDF2 → auto-upgrade). 10/min. |
| `POST /auth/refresh` | Rotacja refresh tokena (wymaga Redis). 20/min. |
| `POST /auth/revoke` | Unieważnienie JWT (JTI → Redis blocklist). |
| `GET /auth/me` | Placeholder (user z JWT middleware). |

**Token:** HS256 JWT, TTL 24h, claims: `sub`, `tenant_id`, `iat`, `exp`, `jti`, opcjonalnie `iss`/`aud`.  
**Refresh:** UUID v4 przechowywany w Redis (TTL 30 dni), single-use (rotation).  
**Tenant isolation:** każda tabela ma `tenant_id` — middleware `http_guard` wyciąga go z JWT i wstrzykuje do kontekstu.

---

## 7. Monitor napięć ([`core/live_tensions.py`](../../core/live_tensions.py))

Heurystyka leksykalna między parami agentów:
1. Tokenizacja głosów (słowa ≥ 4 znaki, lowercase).
2. Jaccard similarity per para: `intensity = 1.0 − 2.2 × jaccard` (clamped 0.22–1.0).
3. Sortowanie malejąco, top 16 par → SSE event `live_tensions`.

Interpretacja: wyższa `intensity` ≈ mniejsze nachodzenie leksykalne → większe tematyczne rozbieżności (nie semantyczny sentyment!).

---

## Known Gaps

- [ ] Brak formalnej specyfikacji payloadu SSE (JSON Schema per event).
- [ ] Router `/voice` — plik nowy, niescommitowany; brak widocznego kodu transkrypcji.
- [ ] Router `/integrations` — brak dokumentacji endpointów webhooka.
- [ ] `business_fa2` (mount `/business`) — osobna aplikacja FA2; brak specyfikacji w tym dokumencie.
- [ ] `core/agent_learner.py` — cykl ewolucji agentów (rolling notes rebuild) nie opisany.
- [ ] Brak diagramu sekwencji pełnego flow SSE (od POST do debate_done).
- [ ] Postgres schema (`db/schema_postgres.sql`) — różnice vs. SQLite nie opisane.
- [ ] Brak opisu cost_tracking (cost_log.jsonl, DAILY_BUDGET_USD, MONTHLY_BUDGET_USD).
