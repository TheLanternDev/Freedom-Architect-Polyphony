# Szkic — Historia debat (punkt 2)

Status: **do recenzji**. Wniosek główny: funkcjonalnie **już działa end-to-end** —
realna praca to jedna luka izolacji + drobny lifting, nie budowa od zera.

## 1. Co już działa (zweryfikowane w kodzie)

- **Auto-zapis** (orchestrator, w trakcie streamu): marzenie+projekt
  (`persist_dream_and_project`), głosy (`save_voice`), synteza (`save_synthesis`),
  **wizualizacja** (`tension_axis` zaszyty w `full_synthesis_json`), zobowiązanie
  (`insert_commitment`). Pełny ślad: proza + oś + summary + commitment.
- **Lista historii**: `GET /history` (limit, szukanie `q`, grupowanie w wątki przez
  `root_debate_id`) → `DebateHistory.tsx` (wątki, `onSelect`).
- **Otwarcie**: `loadHistoricalDebate` → `GET /debate/{id}/thread` → mapuje tury,
  w tym `tension_axis` z `synthesis_structured` (`axisOf`, useDebate.ts:357) →
  `PriorTurnView` renderuje każdą turę z `SyezPanel` **i jej TensionAxis**.
- **Kontynuacja**: follow-up → `continuation_parent_id` → `/debate/continue/stream`,
  łańcuch przez `parent_debate_id`, `list_debate_chain`.
- **Eksport**: `/debate/{id}/export.md` i `.pdf`.

Czyli: zapis, lista, otwarcie z wizualizacją, kontynuacja — komplet.

## 2. Luka realna: izolacja per-user (nie tylko per-tenant)

`debates` jest **tylko tenant-scoped** — brak kolumny `user_subject`.
`get_debate_row` / `list_debates_recent` / `list_debate_chain` filtrują wyłącznie
po `tenant_id`. Tymczasem onboarding i `user_obraz` są **user-scoped**.

- **Dziś OK**: self-register nadaje `tenant_id = sha256(username)` → tenant == user,
  więc historia jest de facto izolowana per user. Test `test_debate_detail_tenant_isolation`
  to potwierdza (B dostaje 404).
- **Ryzyko (latentne)**: w trybach **współdzielonego tenanta** — legacy `ARCHITEKT_API_KEY`
  lub BFF/service-header z wieloma userami na jeden `tenant_id` (dokładnie scenariusze
  z przeglądu 2026-06-02) — `user_id` jest ustawiany, ale debaty (tenant-only) byłyby
  **wspólne dla wszystkich userów tenanta** → cross-user leak najbardziej osobistych
  debat. Niespójne z onboardingiem/Obrazem, które tego nie przeciekają.

To jest jedyna rzecz, która w punkcie 2 wymaga realnej pracy.

## 3. Proponowany checkpoint (architektura zapisu — najpierw)

Zrównać debaty z wzorcem user-scoped:

1. Migracja: `ALTER TABLE debates ADD COLUMN user_subject TEXT` (+ Postgres 0008,
   RLS bez zmian — RLS jest tenantowy; user-filtr w repo, jak przy onboardingu).
   Backfill: stare wiersze `user_subject = NULL` (widoczne dla całego tenanta —
   wstecznie zgodne; nowe wiersze stemplowane `current_user_id()`).
2. Zapis: `insert_debate` stempluje `user_subject = current_user_id()` (jak
   `upsert_onboarding_answer`).
3. Odczyt: `list_debates_recent` / `get_debate_row` / `list_debate_chain` /
   `resolve_root_debate_ids` filtrują **dodatkowo** po `user_subject` (z fallbackiem
   `IS NULL` dla wierszy sprzed migracji, by nie zgubić historii).
4. Kontynuacja: `continuation_parent_id` musi należeć do tego samego usera
   (walidacja przy starcie `/debate/continue/stream`).
5. Testy: izolacja A↔B **w tym samym tenancie** (rozszerzenie istniejącego wzorca):
   debata A niewidoczna w `/history` i `/debate/{id}` dla B przy współdzielonym tenancie.

Decyzja do podjęcia: czy `NULL`-owe (legacy) debaty mają pozostać widoczne dla całego
tenanta (wstecznie zgodne, łagodne), czy twardo schować (bezpieczniej, ale „znikają"
stare wpisy w multi-user). Rekomendacja: widoczne dla właściciela-tenanta, nowe
twardo per-user.

## 4. Lifting (drobny, opcjonalny)

- Etykieta sekcji: „Moje Rady Nadzorcze" / „Historia debat" (i18n).
- Pusty stan listy: zaproszenie zamiast surowego „brak".

## 5. Najmniejszy następny krok (po Twoim „ok")

Faza A (izolacja, blokująca dla multi-tenant): migracja + stempel `user_subject` +
filtr w 4 zapytaniach + walidacja parenta + testy A↔B. Osobny checkpoint.
Faza B (lifting): etykieta + pusty stan.

Najsłabsze ogniwo: backfill `NULL` — źle dobrana semantyka (twarde ukrycie) skasowałaby
widoczność historii istniejących userów. Dlatego fallback `IS NULL = własność tenanta`.
