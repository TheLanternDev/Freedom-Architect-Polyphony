# Plan Zmian — Architekt Wolności (Rada Nadzorcza „Mój Świat”)

**Wersja:** 1.1
**Data:** 2026-05-10
**Bazuje na:** `Rada_Nadzorcza_Moj_Swiat_Specyfikacja_v1.md` (spec v1.0)
**Stan kodu odniesienia:** branch obecny, `main.py` v3.1, `agents/` kompletne (10 plików), UI v3.1

> **Zmiana w v1.1:** dodano dwa AKSJOMATY ponad blokami — „Architektura Marzenia” oraz „Doprowadzanie Projektów Do Końca”. To są pierwotne sensy projektu Architekt Wolności i muszą być wbite w logikę kodu, a nie tylko opisane w prozie.

---

## TL;DR — co tu się dzieje

Kod jest w bardzo dobrym miejscu (FastAPI + SSE + Tauri/React + async LLM + cache + tracking kosztów). Trzon orkiestracji działa. **Ale rdzeń aksjologiczny systemu (tożsamości agentów + dwa AKSJOMATY pierwotne) nie jest zsynchronizowany ze specyfikacją.** Większość agentów ma instrukcje z poprzedniej iteracji „doradca biznesowy”, podczas gdy spec opisuje system integracji jungowsko-somatycznej. Pierwotny cel — **budowa architektury do spełniania marzeń** + **bezwzględne doprowadzanie projektów do końca** — w obecnym kodzie nie istnieje jako mechanizm, tylko jako intencja.

Plan poniżej dzieli zmiany na 2 AKSJOMATY (przekrojowe, dotykają każdego bloku) + 5 priorytetowych bloków. AKSJOMATY i Bloki 1–2 to **must-have** — bez nich system nie spełnia swojej misji. Bloki 3–5 to MVP-completion i Roadmap Fazy 1.

---

## AKSJOMAT 1 — Architektura Marzenia (pierwotny sens) ⭐⭐ FUNDAMENT

**Cel:** Architekt Wolności pierwotnie powstał jako **system tworzenia architektury do spełniania marzeń** — od czystego pragnienia (`marzenie`) do konkretnej, działającej rzeczywistości. To nie może być „jeden z trybów” — to musi być centralny silnik systemu, wokół którego organizują się wszystkie inne tryby (decyzje, projekty, schematy).

**Konsekwencja dla kodu:** Każde zapytanie do Rady — niezależnie od kategorii — przechodzi przez warstwę „Architektury Marzenia”, która:
1. Wydobywa **rdzenne marzenie** stojące za briefem (nawet jeśli brief mówi o decyzji technicznej — pod spodem jest marzenie).
2. Mapuje **architekturę spełnienia** (5 warstw: Wizja → Kotwica wartości → Filary → Kamienie milowe → Najbliższy ruch).
3. Łączy każdy `action_step` z konkretnym `dream_id`, żeby system wiedział, KTÓRE marzenie krok obsługuje.

### A1.1 Nowy moduł `core/dream_architect.py`

```python
# core/dream_architect.py
class DreamArchitecture(BaseModel):
    dream_id: str                       # UUID v4
    raw_brief: str                      # oryginalny tekst Patryka
    core_dream: str                     # 1 zdanie: „o co tu naprawdę chodzi”
    value_anchor: str                   # 1 zdanie: dlaczego to ma znaczenie
    pillars: list[str]                  # 3–5 filarów (od czego zależy spełnienie)
    milestones: list[Milestone]         # twarda lista kamieni milowych z datami
    next_move: NextMove                 # najbliższy konkretny krok (24–72h)
    completion_criteria: list[str]      # OBOWIĄZKOWE: co musi być spełnione, żeby marzenie było „spełnione”
    functionality_checklist: list[str]  # OBOWIĄZKOWE: co musi DZIAŁAĆ, żeby uznać projekt za ukończony (AKSJOMAT 2)
```

### A1.2 Hak orkiestracji — przed Radą

W `_stream_debate` PRZED uruchomieniem 9 agentów dodać fazę **A0: Architektura Marzenia**. Jeden specjalny prompt (Sonnet, niski koszt) destyluje brief w `DreamArchitecture`. Wynik:
- jest emitowany do UI jako event `dream_architecture` (UI pokazuje go jako szkielet ponad gridem agentów),
- jest wstrzykiwany do system promptu KAŻDEGO z 9 agentów jako kontekst dodatkowy: „Patryk tym briefem ściga to marzenie: {core_dream}. Wartość pod spodem: {value_anchor}. Twoje 3 zdania mają wspierać architekturę tego marzenia, nie rozpraszać.”
- jest przekazywany Syezowi, który MUSI w swoim outputie odnieść każdy `action_step` do `dream_id` i do konkretnego `milestone`.

### A1.3 Persystencja — tabela `dreams`

W SQLite (Blok 4):
```sql
CREATE TABLE dreams (
  id TEXT PRIMARY KEY,            -- dream_id
  created_at TIMESTAMP,
  core_dream TEXT NOT NULL,
  value_anchor TEXT,
  pillars_json TEXT,              -- JSON array
  completion_criteria_json TEXT,
  functionality_checklist_json TEXT,
  status TEXT CHECK(status IN ('living','fulfilled','released')) DEFAULT 'living',
  fulfilled_at TIMESTAMP NULL
);
CREATE TABLE dream_debate_link (
  dream_id TEXT REFERENCES dreams(id),
  debate_id INTEGER REFERENCES debates(id),
  PRIMARY KEY (dream_id, debate_id)
);
```

**Dlaczego osobna tabela `dreams`, nie kolumna w `debates`:** jedno marzenie żyje przez wiele debat. „Spełnienie” to długi łuk, nie pojedyncza synteza. System ma pamięć marzeń.

### A1.4 UI — `DreamCanvas`

Nowy komponent ponad gridem agentów: pokazuje aktualną `DreamArchitecture` jako 5-warstwowy diagram (Wizja → Wartość → Filary → Kamienie → Najbliższy ruch). Klik na milestone → otwiera filtr historii debat dla tego marzenia. Klik na „Spełnione” → zmiana statusu marzenia w bazie + emisja zdarzenia świętowania (animacja, dźwięk opcjonalny).

### A1.5 Tryb Marzeń = wzmocniona Architektura Marzenia

Tryb `marzen` (Blok 2) nie jest osobnym flowem — to **wzmocnienie warstwy A1**: prompt destylacji marzenia dostaje dodatkową instrukcję „nie redukuj wizji do realizmu, najpierw pełna ekspansja, potem dopiero kompresja w `pillars`”, a Kidi (Dziecko) dostaje rolę adwokata pierwotnej wersji marzenia, gdyby reszta Rady chciała ją zracjonalizować.

**Akceptacja Aksjomatu 1:** Każda debata produkuje (lub jest powiązana z istniejącym) `DreamArchitecture`. Każdy `action_step` w syntezie Syeza jest spięty z `dream_id` + `milestone`. W UI widać szkielet marzenia od pierwszej sekundy debaty.

---

## AKSJOMAT 2 — Doprowadzanie Projektów Do Końca ⭐⭐ FUNDAMENT

**Cel:** Drugim pierwotnym sensem Architekta Wolności było **zmuszanie się do kończenia tego, co się zaczęło — w pełni funkcjonalnym stanie**. „Zaczęte i porzucone” to choroba, którą system ma leczyć. Spec (sekcja 1) mówi to wprost: „przełamywanie chronicznego zaczynania projektów bez ich kończenia”.

**Konsekwencja dla kodu:** Bezwzględna zasada — żaden projekt nie znika z radaru, dopóki `functionality_checklist` z `DreamArchitecture` nie jest w 100% odhaczony. System aktywnie ściga porzucone projekty, blokuje rozpoczynanie nowych ponad limit, i wymusza decyzję „kończysz albo świadomie odpuszczasz”.

### A2.1 Maszyna stanów `Project`

Każdy `DreamArchitecture` ze statusem `living` ma powiązany `Project` (1:1 dla marzeń wymagających realizacji; marzenia czysto kontemplacyjne mogą mieć `project_required=false`).

```python
class ProjectStatus(str, Enum):
    DREAMING = "dreaming"           # architektura jest, ale brak pierwszego ruchu
    IN_PROGRESS = "in_progress"     # przynajmniej 1 commitment closed
    AT_RISK = "at_risk"             # 14 dni bez postępu (NIC closed) → tryb agresywny
    STUCK = "stuck"                 # 30 dni bez postępu → forced confrontation
    COMPLETED = "completed"         # functionality_checklist 100% ✓
    ARCHIVED_CONSCIOUSLY = "archived_consciously"  # świadomie odpuszczone (z uzasadnieniem)
```

**Bardzo ważne:** Stan `ABANDONED` (porzucony) **nie istnieje jako legalna ścieżka**. Każde wyjście z projektu wymaga jawnej deklaracji `ARCHIVED_CONSCIOUSLY` + tekstowego uzasadnienia (które wpada do historii i jest dostępne dla Tai/Czasowego w przyszłych debatach).

### A2.2 Reguły logiczne wbite w backend

W `core/completion_enforcer.py`:

1. **Reguła „Najpierw kończ”:** Liczba projektów w stanie `IN_PROGRESS` + `DREAMING` nie może przekroczyć `MAX_ACTIVE_PROJECTS` (env, default = 3). Próba uruchomienia nowej debaty z `category=projekt` przy limicie → backend zwraca event `completion_block` z listą aktywnych projektów i pytaniem „który kończysz / archiwizujesz przed startem nowego?”.

2. **Reguła „Brak ruchu = konfrontacja”:** Background worker (Blok 5) raz dziennie skanuje `projects`:
   - 14 dni od ostatniego `commitment.completed_at` → status `AT_RISK`, automatyczne wymuszenie mini-debaty w trybie `schematy` z briefem „Projekt {X} stoi 14 dni — co się dzieje w ciele, co chowa się w cieniu, co mówi pamięć?”.
   - 30 dni → status `STUCK`, hard block UI: do czasu decyzji (kończysz / archiwizujesz świadomie) nie można rozpocząć żadnej innej debaty z `category=projekt`.

3. **Reguła „Funkcjonalność = warunek konieczny”:** `COMPLETED` może być nadane WYŁĄCZNIE gdy `functionality_checklist` ma 100% ✓ — backend nie pozwoli oznaczyć projektu jako ukończonego, jeśli choć jeden punkt jest niezahaczony. Walidator `assert_full_functionality(project_id)` jest wywoływany w endpoincie `PATCH /projects/{id}` i przy każdej syntezie Syeza, gdzie agent próbowałby skrócić checklistę.

4. **Reguła „Syez patrzy w lustro funkcjonalności”:** W strukturyzowanym outpucie Syeza (Blok 3) dochodzi obowiązkowe pole `completion_audit`:
   ```json
   "completion_audit": {
     "functionality_checklist_remaining": ["..."],
     "blocked_by": ["..."],
     "smallest_next_functional_increment": "..."
   }
   ```
   Bez tego pola synteza jest odrzucana (re-prompt z explicit „brakuje completion_audit”).

### A2.3 Tabele SQLite — projekty + checklist + audyty

```sql
CREATE TABLE projects (
  id INTEGER PRIMARY KEY,
  dream_id TEXT REFERENCES dreams(id),
  status TEXT NOT NULL DEFAULT 'dreaming',
  started_at TIMESTAMP,
  last_progress_at TIMESTAMP,         -- updated przy każdym commitment.completed_at
  completed_at TIMESTAMP NULL,
  archived_reason TEXT NULL,          -- wymagane dla ARCHIVED_CONSCIOUSLY
  archived_at TIMESTAMP NULL
);

CREATE TABLE functionality_items (
  id INTEGER PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  description TEXT NOT NULL,
  is_done BOOLEAN DEFAULT 0,
  done_at TIMESTAMP NULL,
  evidence_url TEXT NULL              -- opcjonalny dowód: link/zrzut/test
);

CREATE TABLE completion_audits (
  id INTEGER PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  debate_id INTEGER REFERENCES debates(id),
  remaining_json TEXT,                -- snapshot completion_audit z Syeza
  audited_at TIMESTAMP
);
```

### A2.4 Endpointy

- `GET /projects` — wszystkie projekty z agregatem (% checklisty, dni bez postępu).
- `GET /projects/{id}` — pełny stan projektu + ostatnie audyty.
- `PATCH /projects/{id}/functionality/{item_id}` — odhaczenie pozycji (opcjonalnie z `evidence_url`).
- `POST /projects/{id}/archive` — wymaga `{reason: str, min_length=50}`.
- `POST /projects/{id}/complete` — wywołuje `assert_full_functionality`, zwraca 422 jeśli niezahaczone pozycje.

### A2.5 Wpływ na agentów (system prompt patch)

W `agents/identities.py` (Blok 1) każdy agent dostaje wspólny postscriptum:

```
ZASADA NADRZĘDNA ARCHITEKTA WOLNOŚCI:
1. Sensem tej Rady jest doprowadzanie projektów do końca w pełni funkcjonalnym stanie.
2. Nigdy nie sugeruj „odłożenia na później” bez konkretnego warunku powrotu (data + trigger).
3. Każda twoja sugestia musi przybliżać do odhaczenia pozycji z functionality_checklist
   albo świadomie redefiniować, co znaczy „skończone” dla tego marzenia.
4. Jeśli widzisz w briefie wzorzec porzucania — nazwij go wprost.
```

Szow (Cień) i Deega (Głęboka Diagnoza) dostają dodatkowo: „twoim szczególnym zadaniem jest demaskować mechanizmy ucieczki przed dokończeniem.”

### A2.6 UI — `CompletionDashboard` + lock

- Nowy widok w UI: lista aktywnych projektów z paskiem postępu `functionality_checklist`, dniami od ostatniego ruchu, statusem (kolor: zielony → żółty → czerwony).
- Hard-lock: gdy `MAX_ACTIVE_PROJECTS` osiągnięte i Patryk próbuje startować nową debatę projektową, BriefForm pokazuje modal z listą aktywnych i wymaga decyzji „kończysz X / archiwizujesz świadomie X / wracasz”.
- Przy ukończeniu projektu (`COMPLETED`) — wyraźna ceremonia w UI (full screen, animacja, podsumowanie z historii, opcja eksportu „dowodu spełnienia” do PDF).

**Akceptacja Aksjomatu 2:** (a) Nie da się mieć więcej niż `MAX_ACTIVE_PROJECTS` aktywnych projektów. (b) Projekt bez ruchu 14 dni odpala wymuszoną mini-debatę. (c) `COMPLETED` jest nadawany TYLKO przy 100% `functionality_checklist`. (d) Każda synteza Syeza zawiera `completion_audit`.

---

## BLOK 1 — Synchronizacja tożsamości agentów ze spec ⭐ KRYTYCZNY

**Cel:** Doprowadzić wszystkich 10 agentów do zgodności z rolami opisanymi w sekcji 3 spec. Bez tego system nie jest Radą Nadzorczą „Mój Świat”, tylko jej imitacją.

### 1.1 Backend — `agents/*.py`

Dla każdego pliku: przepisać `self.role`, `self.instruction`, oraz fallback `contribute()` zgodnie ze spec. Emoji utrzymać kompatybilne ze spec (kolor + symbol).

| Plik | Obecne `role` | Nowe `role` (zgodne ze spec) | Kluczowa zmiana w instrukcji |
|---|---|---|---|
| `relacjan.py` | Strażnik Relacji i Empatii | **Relacyjny — most między Patrykiem a światem** | Mapa relacji i dynamik (klient ↔ projekt ↔ marzenia ↔ Patryk), nie ogólna empatia UX |
| `kogit.py` | Architekt Logiki i Struktury | **Kognitywny — architekt myśli Patryka** | Przekonania, modele mentalne, zapętlenia poznawcze — nie ogólna logika problemu |
| `emojy.py` | Tłumacz Emocji i Intuicji | **Emocjonalny — rezonans przed nazwą** | Rezonowanie z emocją (radość/strach/żałoba/wstyd/duma) — nie „intuicja produktowa” |
| `deega.py` | Detektyw Detali i Diagnosta | **Głęboka Diagnoza — wzorce, blokady, lojalności** | Nieświadome wzorce, lojalności wobec przeszłości — NIE edge case'y techniczne |
| `smaty.py` | Strateg Małych Kroków | **Somatyczny — ciało Patryka już wie** | Napięcia, energia, blokady fizyczne; gdzie w ciele to siedzi — NIE taktyka MVP |
| `szow.py` | Showman i Komunikator | **Cień (Jung) — bez cenzury, bez grzeczności** | To co wyparte, ukryte za sukcesem i ambicją — NIE marketing hook |
| `tai.py` | Architekt Innowacji | **Czasowy — pamięć i wizja jednocześnie** | Skąd przyszło, dokąd prowadzi; echo historii vs. nowy kierunek — NIE wybór stacka |
| `obver.py` | Obserwator z dystansu | **Obserwator — jedyny stojący na zewnątrz** | Zimno, precyzyjnie, bez interpretacji emocjonalnej (już blisko spec) |
| `kidi.py` | Dziecięca Ciekawość | **Dziecko — Patryk zanim nauczył się być dorosły** | Instynkt, fascynacja/strach, bez filtrów dorosłych |
| `syez.py` | Syntezator Wizji i Sensu | **Synteza — głos całej Rady w jednym, NIC od siebie** | Krytyczna zmiana: Syez NIE dodaje własnej perspektywy; instrukcja musi tego pilnować |

**Zasada DRY:** rozważyć wyniesienie definicji do `agents/identities.py` (jeden dict z `name → {emoji, role, quote, instruction}`) i niech klasy go tylko ładują. Łatwiej będzie synchronizować z spec.

### 1.2 `Syez` — wymuszenie „tylko lustro”

Przepisać instrukcję Syeza tak, by promptem wymuszała:
1. Brak własnej perspektywy.
2. Strukturyzowany output: insights per agent → napięcia/konflikty → zintegrowane rekomendacje → pytania otwarte → kroki działania (z terminem).
3. W trybie „Przełamywanie Schematów”: dodatkowo zobowiązania + follow-up.

Fallback `contribute()` Syeza obecnie deklaruje konkluzję („sukces zależy od pierwszego klienta…”) — usunąć i zastąpić neutralnym tekstem informującym, że bez LLM nie ma syntezy.

### 1.3 Frontend — `ui/src/components/AgentCard.tsx`

Zaktualizować `AGENT_META` (role + kolory) tak, by odzwierciedlał spec:
- Szow — czerń/czerwień (Cień, sekcja 5.2 spec: „akcenty teal / fiolet / czerwony (dla cienia)”).
- Smaty — odcień ziemisty/brązowy (somatyczny).
- Pozostałe role po polsku z opisów spec.

**Akceptacja Bloku 1:** każdy agent w UI i backendzie ma rolę 1:1 z sekcją 3 spec.

---

## BLOK 2 — Brief: kategorie + tryby działania ⭐ WAŻNE

**Cel:** Spec wymaga 4 kategorii briefu (Decyzja / Projekt / Marzenie / Schemat do przełamania) oraz 3 trybów (Marzeń / Przełamywania Schematów / Codzienny — light). Obecny `Brief` ma `scale` + `budget` (artefakty starego MVP).

### 2.1 Model `Brief` — `main.py`

Rozszerzyć:
```python
class Brief(BaseModel):
    description: str = Field(..., min_length=20, max_length=2000)
    category: Literal["decyzja", "projekt", "marzenie", "schemat"] = "decyzja"
    mode: Literal["pelna", "marzen", "schematy", "codzienny"] = "pelna"
    intention: Optional[str] = None         # spec sekcja 4.1
    extra_context: Optional[str] = None     # opcjonalny dodatkowy kontekst
    # scale + budget — zostawić deprecated, zachowując kompatybilność wsteczną
```

### 2.2 Logika trybu w `_stream_debate`

- **Tryb Codzienny (`codzienny`)** — light mode, wywołuje tylko 4–5 agentów (proponowani: Kogit, Emojy, Smaty, Obver, Syez). Zysk czasu i kosztu.
- **Tryb Pełna (`pelna`)** — wszyscy 9 + Syez.
- **Tryb Marzeń (`marzen`)** — pełna 9-tka + Syez, ale system prompt dla każdego agenta dostaje dopisek „kontekst: marzenie/wizja, nie zawężaj zbyt szybko do realizmu”.
- **Tryb Przełamywanie Schematów (`schematy`)** — pełna 9-tka + Syez, ale Szow (Cień) i Deega (Głęboka Diagnoza) dostają **agresywniejsze** promptowanie (mniej grzeczności, więcej konfrontacji), a Syez wymusza w outputie zobowiązania + termin follow-upu (72h).

### 2.3 BriefForm — `ui/src/components/BriefForm.tsx`

Zastąpić select `scale` + `budget` selektami `category` i `mode`. Dodać opcjonalne pole `intention` (textarea). Update typów w `ui/src/types/debate.ts`.

**Akceptacja Bloku 2:** Patryk wybiera tryb i kategorię w UI, backend respektuje, koszty trybu Codziennego są ~½ trybu Pełnego.

---

## BLOK 3 — Struktura syntezy Syeza + akcje „Zobowiązuję się”

**Cel:** Dziś Syez zwraca jeden tekst. Spec wymaga **strukturyzowanego JSON-like outputu** (sekcja 4.3).

### 3.1 Format syntezy

Wymóc w prompcie Syeza zwracanie JSON-a z polami:
```json
{
  "insights_per_agent": [{"agent": "Relacjan", "insight": "..."}],
  "tensions": [{"between": ["Smaty", "Kogit"], "why": "..."}],
  "recommendations": ["..."],
  "open_questions": ["..."],
  "action_steps": [{"step": "...", "due": "2026-05-12", "priority": "high"}],
  "commitments": [{"text": "...", "follow_up_at": "2026-05-13T20:00Z"}]  // tylko w trybie Schematy
}
```

Backend parsuje JSON; jeśli się nie sparsuje — fallback do plain text (graceful degradation).

### 3.2 SSE — nowy event `synthesis_structured`

W `main.py` dodać event `synthesis_structured` z `payload = parsed_json` po `synthesis_done`. Frontend uczy się go obsłużyć.

### 3.3 SyezPanel — akcje

- Wyświetlanie napięć (TensionMeter — sekcja 5.2 spec), rekomendacji, pytań otwartych jako osobnych bloków.
- Przycisk **„Zobowiązuję się”** przy każdym `action_step` / `commitment` — emituje POST `/commitments` (nowy endpoint).
- Przycisk **„Eksportuj do Markdown”** (sekcja 6 spec).

### 3.4 Endpoint `/commitments` (zalążek bazy)

- `POST /commitments` — zapis do SQLite (`data/architekt.db`, tabela `commitments`).
- `GET /commitments` — lista (do widoku Historia w bloku 4).
- `PATCH /commitments/{id}` — oznaczenie jako zrealizowane.

**Akceptacja Bloku 3:** Patryk może po debacie kliknąć „Zobowiązuję się” przy konkretnym kroku i widzieć go w historii.

---

## BLOK 4 — Persystencja + Historia debat

**Cel:** Spec sekcja 5.1: „Baza danych: SQLite (MVP) → Postgres (produkcja)”. Sekcja 6: „Historia debat + wyszukiwanie”.

### 4.1 Schema SQLite

`data/architekt.db` (przez `aiosqlite`):
- `debates(id PK, created_at, category, mode, brief_description, intention, full_synthesis_json, cost_usd)`
- `agent_voices(id PK, debate_id FK, agent_name, voice_text, tokens_in, tokens_out, cost_usd)`
- `commitments(id PK, debate_id FK, text, due_at, follow_up_at, status, created_at)`

### 4.2 Zapis po każdej debacie

Na końcu `_stream_debate`, po `synthesis_done`, zapisać debatę i wszystkie głosy. Koszt brać z `cost_log.jsonl` (po `brief_hash`).

### 4.3 Endpointy

- `GET /debates` — paginowana lista (id, created_at, category, brief preview, koszt).
- `GET /debates/{id}` — pełna debata z głosami.
- `GET /debates/search?q=...` — proste LIKE po `brief_description` (FTS5 w Fazie 1).

### 4.4 UI — `HistoryTimeline`

Nowy komponent `ui/src/components/HistoryTimeline.tsx`. Pokazuje listę debat, klik → powrót do widoku.

**Akceptacja Bloku 4:** każda debata trafia do SQLite, Patryk widzi je w UI, może wrócić do dowolnej.

---

## BLOK 5 — Optymalizacje, tryb agresywny follow-up, eksport

### 5.1 Tryb agresywny follow-up (sekcja 4 spec, Faza 2 roadmap)

- Background worker (APScheduler lub `asyncio.create_task` z lifespan): co 30 min sprawdza `commitments.follow_up_at <= now()` i `status='open'`.
- Push do frontu przez WebSocket lub fallback: zapis do tabeli `notifications` → endpoint `GET /notifications/unread` → polling z UI co 60s.
- W UI: badge przy ikonce „Powiadomienia”, modal „Co z tym? [Zrobione / Przesunąć / Odpuścić]”.

### 5.2 Eksport do Markdown / PDF

- `GET /debates/{id}/export?format=md` — render template Jinja2 → MD.
- `GET /debates/{id}/export?format=pdf` — MD → HTML → WeasyPrint → PDF.
- UI: przyciski w `SyezPanel` i `HistoryTimeline`.

### 5.3 Optymalizacje kosztów (sekcja 5.3 spec)

- **Alert budżetowy:** w `BaseAgent._log_cost` dodać agregator dzienny (`cost_summary.json`); jeśli dzień > `DAILY_BUDGET_USD` (env), Syez emituje warning event do UI.
- **Fallback na tańsze modele:** w `BaseAgent._call_llm` przy `RateLimitError` po 3 retry — spadek Opus→Sonnet→Haiku (dla agentów Opus). Już częściowo zaimplementowane retry; brakuje fallbacku modelu.
- **Kompresja kontekstu:** dla trybu Codzienny — skracać `context` (top 200 znaków + intencja). Dla pełnej — pełen kontekst.

**Akceptacja Bloku 5:** Patryk widzi powiadomienia follow-up, może wyeksportować syntezę do PDF, dostaje alert gdy dzień przekracza budżet.

---

## Co świadomie pomijamy w v1 (= Roadmap Fazy 2+)

- Pamięć długoterminowa per agent (ewolucja osobowości na podstawie historii) — Faza 3.
- Multi-user / personalizowane Rady dla innych — Faza 4.
- Integracje Notion / Todoist / Calendar / Voice — Faza 5.
- Migracja na Postgres — gdy SQLite zacznie boleć.
- Faktyczny token streaming z Anthropic (obecnie chunkujemy słowo po słowie po stronie serwera) — to upgrade ergonomiczny, można dodać w Fazie 1 razem z `client.messages.stream(...)`.

---

## Kolejność rekomendowana

1. **Aksjomat 1 — szkielet** (`core/dream_architect.py` + tabela `dreams` + event `dream_architecture` w SSE) — 1 dzień, przekrojowy.
2. **Aksjomat 2 — szkielet** (`core/completion_enforcer.py` + tabele `projects` / `functionality_items` / `completion_audits` + walidator) — 1–2 dni, przekrojowy.
3. **Blok 1** — synchronizacja tożsamości + wspólny postscriptum z AKSJOMATU 2 (1–2 dni, niski risk).
4. **Blok 2** — kategorie + tryby, z trybem Marzeń jako wzmocnieniem Aksjomatu 1 (2–3 dni).
5. **Blok 3** — strukturyzowana synteza z obowiązkowym `completion_audit` + zobowiązania (3–4 dni).
6. **Blok 4** — persystencja + historia + `DreamCanvas` + `CompletionDashboard` w UI (3–4 dni).
7. **Blok 5** — follow-up agresywny (egzekwuje Aksjomat 2 dla `AT_RISK`/`STUCK`), eksport, optymalizacje (3–5 dni).

**Razem ~3 tygodnie pracy do pełnego MVP zgodnego ze spec v1.0 + oba AKSJOMATY.**

---

## Testy — co dopisać

Dla każdego bloku/aksjomatu odpowiadające testy w `tests/`:
- `test_dream_architect.py` — destylator briefu zwraca pełen `DreamArchitecture` ze wszystkimi 7 polami, w tym niepustą `functionality_checklist`.
- `test_completion_enforcer.py` — (a) `MAX_ACTIVE_PROJECTS` blokuje 4. projekt; (b) `complete()` rzuca 422 gdy checklist niepełny; (c) `archive()` wymaga `reason` min 50 znaków; (d) brak ruchu 14d → status `AT_RISK`.
- `test_syez_completion_audit.py` — synteza Syeza ZAWSZE zawiera klucz `completion_audit` z trzema wymaganymi polami; re-prompt przy braku.
- `test_agent_identities.py` — assert role/instrukcji każdego agenta + obecność wspólnego postscriptum z Aksjomatu 2.
- `test_modes.py` — dla `mode=codzienny` wywoływane jest 4–5 agentów, nie 9.
- `test_syez_no_perspective.py` — synteza nie zawiera fraz typu „moim zdaniem” / „uważam, że” (lustro).
- `test_synthesis_json.py` — Syez zwraca parsowalny JSON ze wszystkimi polami.
- `test_persistence.py` — debata trafia do SQLite z poprawnymi FK, w tym FK do `dreams`.
- `test_followup.py` — commitment z `follow_up_at` w przeszłości pojawia się w `/notifications/unread`; projekt `AT_RISK` odpala wymuszoną mini-debatę.

---

## Ryzyka i jak je adresujemy

| Ryzyko | Mitigacja |
|---|---|
| Zmiana ról agentów = stare cache Redis zwracają „stare” głosy | Bumpnąć prefix klucza cache (`llm:v2:{name}:...`) lub `FLUSHDB` przy migracji |
| JSON od Syeza czasem niepoprawny | Walidacja przez Pydantic + fallback do plain text + event `synthesis_parse_error` do UI |
| Koszt Opus dla 4 agentów + Syez = drogo | Mode-aware: w trybie Codziennym Opus tylko Syez, reszta Sonnet/Haiku |
| Strukturyzowany output zubaża „głos" Syeza | Zostawić sekcję `closing_mirror` jako narracyjny tekst, JSON tylko dla akcji |
| Faza A0 (Architektura Marzenia) dodaje ~2 s opóźnienia przed Radą | A0 leci Sonnet z `max_tokens=600`; jest cache'owana per `sha256(brief)`; emitujemy `dream_architecture` natychmiast → UI ma co pokazać podczas debaty |
| `MAX_ACTIVE_PROJECTS` może frustrować w intensywnych okresach | Wartość konfigurowalna w env; tryb „override” dostępny tylko po wpisaniu jawnego uzasadnienia (zapisywane do `completion_audits`) — system nigdy nie blokuje cicho |
| Walidator `functionality_checklist` może być nadmiernie sztywny | Patryk może edytować checklist w trakcie projektu (przez `PATCH /projects/{id}/functionality`), ale każda edycja jest logowana w `completion_audits` jako delta — historia widzi, czy redefiniujemy „skończone” uczciwie czy uciekamy |

---

## Kolejny krok

Powiedz "zaczynamy Blok 1" — wejdę w synchronizację tożsamości agentów i przepiszę 10 plików zgodnie z tabelą wyżej (najpierw plan na każdy plik, potem implementacja).
