# Podsumowanie refaktoryzacji v3.3 (24.05.2026)

## Cel

Wydzielenie logiki biznesowej z `main.py` do modularnych serwisów w `api/services/`.
Efekt: `main.py` pełni wyłącznie rolę routera FastAPI (routing, lifespan, middleware, modele Pydantic).

## Metryki

| Plik | Przed | Po |
|------|------:|---:|
| `main.py` | 1172 linii | 957 linii (−18%) |
| `api/services/` (łącznie) | 0 | 1526 linii (9 modułów) |
| Nowe testy | 0 | 645 linii (4 pliki, ~60 test cases) |
| **Wynik testów** | 187 passed / 6 pre-existing failures | **bez zmian** |

## Nowe pliki

### `api/services/` — warstwa serwisowa

| Moduł | Linie | Odpowiedzialność |
|-------|------:|-----------------|
| `_sse.py` | 10 | Single source of truth dla formatu SSE event |
| `_types.py` | 19 | `BriefLike` Protocol (structural typing dla brief) |
| `mode_helpers.py` | 74 | `daily_checkin_question()`, `mode_decorator_for_dream()` |
| `budget_guard.py` | 87 | Twardy budżet LLM (402), warning SSE, snapshot |
| `dream_service.py` | 88 | Faza A0: destylacja marzenia + zapis DB |
| `commitment_service.py` | 159 | CRUD zobowiązań + shadow enforcement (AKSJOMAT 2) |
| `completion_service.py` | 195 | Stale nudges, follow-upy, phase2 maintenance |
| `project_service.py` | 220 | CRUD projektów, complete, archive, limit enforcement |
| `debate_orchestrator.py` | 674 | 3-fazowa orkiestracja SSE debaty |

### Testy

| Plik | Testy | Pokrywa |
|------|------:|---------|
| `tests/test_aksjomat_v33.py` | 16 | A0 fallback, stale detection, re-prompt, auto-followup |
| `tests/test_debate_orchestrator.py` | 18 | extract_json, parse_synthesis, chunk_words, council, syez_payload |
| `tests/test_budget_guard.py` | 7 | spent_today, warning SSE, hard budget 402 |
| `tests/test_sse.py` | 3 | Format, JSON, unicode |

### Inne zmiany

| Plik | Zmiana |
|------|--------|
| `_tools/scripts/smoke_week1.sh` | Dodana sekcja AKSJOMAT v3.3 |
| `scripts/unpack-founders-archive.sh` | Fix: `tar -x` → `tar -xz` |
| `docs/spec/SPEC_CURRENT.md` | Mechanizm re-promptu, poprawka DreamArchitecture |
| `README.md` | Sekcja "Architektura v3.3+" z tabelą modułów |
| `INSTALL.md` | §8 (struktura backendu) + §9 (smoke) |
| `tests/test_hard_lock_and_audit.py` | Fix importów po refaktoryzacji |

## Kluczowe decyzje architektoniczne

1. **3-fazowy orchestrator**: `_stream_debate_inner` rozbity na `_phase_council` → `_phase_synthesis` → `_phase_commit_and_finalize` (łatwiejsze testowanie i rozszerzanie).

2. **BriefLike Protocol**: Structural typing zamiast `Any` — IDE/mypy łapie brakujące pola bez konieczności dziedziczenia.

3. **Single SSE helper**: Duplikacja `_sse()` w 4 plikach wyeliminowana — jeden import z `_sse.py`.

4. **Commitment service**: Pełna logika biznesowa (72h auto-followup, shadow enforcement, touch_project) wydzielona z endpointów.

5. **Enforce w project_service**: `enforce_active_project_limit_for_brief` przeniesiony z completion_service (bliżej domeny projektów).

## Zero-regresja

Wszystkie zmiany zachowują backward compatibility:
- Endpointy API bez zmian (te same ścieżki, payloady, kody HTTP)
- `dream_service.py` re-eksportuje `daily_checkin_question` i `mode_decorator_for_dream` (kompatybilność importów)
- Testy: 187 passed, 6 pre-existing failures (Redis, PDF deps, SQLite FTS, safety regex)
