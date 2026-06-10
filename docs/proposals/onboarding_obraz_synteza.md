# Propozycja — Onboarding „20 pytań" → trwały Obraz Użytkownika

Status: **do recenzji** (nie zaimplementowane). Cel: przy aktywacji trybu osobistego
Architekt buduje bogaty wstępny obraz użytkownika i — co kluczowe — **udostępnia go
Radzie przez AKSJOMAT 1**.

## 1. Stan faktyczny (już działa, nie ruszamy bez powodu)

- `personal_v1/rituals/onboarding.py` — 20 pytań + 9 sekcji-batchy (`SEKCJE`).
- `api/routers/personal.py` — `GET /onboarding/questions`, `POST /onboarding/save`
  (RLS per tenant, migracja 0004; fallback JSONL z `tenant_id`+`user_subject`),
  `GET /onboarding/answers` („Mój obraz", izolacja po userze).
- Front: `MojObrazPanel.tsx`, `PersonalRitualPanels.tsx`.

**Luka A:** brak wymiaru **kreatywności** i **duchowości** (oba wprost w zakresie).
**Luka B (główna):** odpowiedzi nigdzie nie są **syntetyzowane w trwały model** ani
**wstrzykiwane do kontekstu agentów**. `core/` i `agents/` nie czytają onboardingu →
Rada startuje „ślepa" na obraz, który użytkownik właśnie oddał.

## 2. Pytania — delta (chirurgicznie, kolejność istniejących bez zmian)

Proponuję **dodać 2 sekcje na końcu** (przed „Cisza" lub po niej), 20 → 22.
Etykieta „20 pytań" to brand, nie twarde ograniczenie; testy liczą `len(PYTANIA)`
dynamicznie, więc rozszerzenie ich nie psuje. Alternatywa (jeśli trzymamy 20):
swap dwóch najsłabszych — do Twojej decyzji.

Kreatywność (głos Kidi + Smaty):
- „Co tworzysz, kiedy nikt tego nie zobaczy?"
- „Kiedy ostatnio zrobiłeś coś tylko dla samej formy — bez celu i bez widowni?"

Duchowość (głos Deega + Obver, bez religijnego przechyłu):
- „Co Cię przerasta w dobrym sensie — przed czym czujesz pokorę?"
- „Kiedy ostatnio czułeś, że jesteś częścią czegoś większego niż Ty?"

Ton zgodny z resztą: krótko, bezpośrednio, bez coachingu. (Jeśli wolisz 22→swap,
wskaż które z obecnych ustępują.)

## 3. Synteza → trwały Obraz (rdzeń propozycji)

Po zebraniu odpowiedzi: **jeden cichy dystylator** (NIE 10. głos Rady — analogicznie
do `dream_architect.adistill_dream`, nie do agenta z charakterem) składa odpowiedzi w
ustrukturyzowany `ObrazUzytkownika`:

```
ObrazUzytkownika:
  wartosci: list[str]          # na co się nie zgodzi / czego pragnie
  napiecia: list[str]          # cień, tłumione impulsy, niedomknięcia
  relacje: list[str]           # kto zna naprawdę, komu nie powiedział
  wzorce: list[str]            # pętle z dzieciństwa (Tai/Deega)
  kreatywnosc: str
  duchowosc: str
  cialo: str                   # gdzie trzyma napięcie
  zdanie_dla_siebie: str       # surowy cytat użytkownika (kotwica, nie parafraza)
  zrodlo: "onboarding"         # prowenenacja; wersjonowanie
```

Zasady:
- **Bez dopowiadania** — model cytuje/streszcza wyłącznie to, co użytkownik napisał
  (ta sama dyscyplina co Syez: „czego nie ma w odpowiedziach, nie wpisujesz").
- **Trwałość, tenant-scoped**: tabela `user_obraz` (1 wiersz/użytkownik, wersjonowany),
  `tenant_id` + `user_subject`, RLS jak `onboarding_answers`. Re-synteza = nowa wersja,
  nie nadpisanie w miejscu (audytowalność).
- **Konsumpcja przez AKSJOMAT 1**: `DreamArchitecture.as_agent_context()` (lub warstwa
  obok) dokleja zwięzły wyciąg Obrazu do kontekstu agenta — tak jak teraz dokleja
  marzenie. Obraz **karmi** marzenie i napięcia, nie zastępuje ich.

## 4. Szkic flow (18h-friendly, łagodny)

1. Aktywacja trybu osobistego → ekran powitalny (cisza, tempo „ile chcesz").
2. Batche wg `SEKCJE` — partia po partii, zapis po każdej (`POST /onboarding/save`,
   już działa). Można przerwać i wrócić (stan z `GET /onboarding/answers`).
3. Po ostatniej partii → `POST /personal/onboarding/synthesize` (nowy) → `ObrazUzytkownika`.
4. Pokaz Obrazu użytkownikowi do **akceptacji/edycji** (to jego lustro, nie wyrok Rady).
5. Od tej pory każda debata w trybie personal wstrzykuje Obraz przez AKSJOMAT 1.

## 5. Izolacja / bezpieczeństwo (mandat niepodważalny)

- Odpowiedzi i Obraz to dane **maksymalnie wrażliwe** → ta sama granica co reszta:
  `tenant_id` (ContextVar+RLS) **oraz** `user_subject` (dwóch userów w jednym tenancie
  nie widzi nawzajem Obrazu — jak w `list_onboarding_answers`).
- Synteza biegnie przez istniejący LLM-path → dziedziczy ContextVar tenanta; `pg_wrap`
  fail-closed na pustym tenancie chroni zapis.
- **Nie** logować treści odpowiedzi (PII) — tylko metadane (liczba, status).
- Fallback JSONL: dopuszczalny w dev/soft-launch; w produkcji multi-tenant **tylko DB+RLS**
  (JSONL nie ma RLS — to akceptowalne wyłącznie single-user/dev).

## 6. Najmniejszy następny krok (po Twojej akceptacji pytań)

1. Dodać 4 pytania (2 sekcje) w `onboarding.py` — 5 min, zero ryzyka (testy dynamiczne).
2. `ObrazUzytkownika` (pydantic) + dystylator wzorowany na `adistill_dream`.
3. Migracja `user_obraz` (tenant_id+user_subject, RLS) + `repo.upsert/get_user_obraz`.
4. `POST /personal/onboarding/synthesize` + wstrzyknięcie wyciągu w AKSJOMAT 1.
5. Test izolacji Obrazu A↔B (wzorzec `test_business_fa2_tenant_isolation`).

Najsłabsze ogniwo: pkt 4 (wstrzyknięcie) — jeśli zrobione niechlujnie, rozdmucha
kontekst agenta i rozmyje sygnał. Wyciąg do AKSJOMAT 1 musi być krótki i wysokosygnałowy.
