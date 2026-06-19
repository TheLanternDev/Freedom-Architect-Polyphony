# Prompt dla Cursora — przebudowa `mypolyphony.com` na model DUAL-TRACK (Firmy + Osobista)

> Wklej całość jako zadanie w Cursorze, w repo, w którym żyje strona `mypolyphony.com`.
> Pracuj **krok po kroku**. Po Fazie 0 (Discovery) **zatrzymaj się i pokaż ustalenia + proponowaną IA**, zanim zaczniesz większe edycje. Nie zgaduj stacku ani lokalizacji plików.

---

## 0. Kontekst (przeczytaj zanim cokolwiek zmienisz)

Produkt: **Freedom Architect: Polyphony / Architekt Wolności** — wieloperspektywiczny system multi-agentowy („Rada" 9 głosów + Syez).

**Cel zmiany:** strona obsługuje dziś **wyłącznie odbiorcę B2B** (liderzy RevOps/Operations, closed beta). Ma obsługiwać **dwie ścieżki równolegle**, spójnie z dwoma trybami istniejącymi w kodzie:

- **Ścieżka „Dla firm" (B2B)** = tryb `fa2` (Freedom Architect Business): analityczny, dane/modele/metryki, scenariusze Base/Bull/Bear, decyzje operacyjne.
- **Ścieżka „Dla Ciebie" (B2C / osobista)** = tryb `personal`: głęboka praca nad sobą, integracja wewnętrznych konfliktów, decyzje życiowe. Ton surowy, transformacyjny — **nie** coachingowy, **nie** terapeutyczny.

**Tożsamość tonu (NIE zmieniaj jej w żadnej ścieżce):** anty-motywacyjny, anty-chatbot. Obecne frazy-kotwice na stronie, które mają zostać DNA: „nie kolejny chatbot z odpowiedzią", „bez motywacyjnego języka", „synteza, która nie zgładza tego, co niewygodne". Polifonia, nie konsensus za wszelką cenę.

### Twarde ograniczenia compliance (BLOKUJĄCE — nie wolno ich złamać)
Wersja osobista dotyka **danych szczególnej kategorii (zdrowie/uzależnienia, art. 9 RODO)**. W warstwie marketingowej oznacza to:

1. **ZERO roszczeń terapeutycznych / medycznych.** Żadnego „leczy", „terapia", „wyleczysz uzależnienie", „zastępuje terapeutę", „diagnoza". Ryzyko reklasyfikacji jako wyrób medyczny (MDR).
2. **Widoczny disclaimer** na ścieżce osobistej: „To nie jest pomoc medyczna ani terapeutyczna."
3. **Ścieżka kryzysowa** — krótka informacja/kontakt do pomocy, gdy treść dotyka kryzysu (telefon zaufania / numer alarmowy). Nie wymyślaj numerów — zostaw placeholder `[DO UZUPEŁNIENIA: numer/kontakt kryzysowy]` i oznacz jako TODO.
4. **AI Act / transparentność:** jawnie, że użytkownik rozmawia z systemem AI (Radą).
5. **Local-first / BYOK:** jeśli copy dotyka prywatności — dane debat zostają lokalnie, model na kluczu klienta; nie obiecuj hostingu/„chmury", którego nie ma.

> Jeśli któraś proponowana treść ociera się o roszczenie terapeutyczne — **odrzuć ją i zaproponuj sformułowanie opisowe** (co system robi: mapuje napięcia, pokazuje perspektywy), nie obietnicę efektu zdrowotnego.

---

## FAZA 0 — Discovery (NIE edytuj jeszcze — tylko zbadaj i zaraportuj)

Checklista:

- [ ] Zlokalizuj **źródło strony** `mypolyphony.com`. Uwaga: README głównego repo wspomina katalog `polyphony-site/`, ale w repo aplikacji go **nie ma** — strona jest hostowana na **Cloudflare**. Ustal, czy źródło jest: (a) w tym repo w innym katalogu, (b) w osobnym repo, (c) w Cloudflare Pages/Workers. Wypisz dokładne ścieżki.
- [ ] Zidentyfikuj **stack**: czysty statyczny HTML/CSS/JS? framework (Astro/Next/Vite)? Cloudflare Pages vs Worker? Gdzie konfiguracja routingu (`/fragment`, `/testuj` to czyste URL-e)?
- [ ] Zinwentaryzuj **istniejące strony i sekcje**: `/` (hero + „Rada" + „Jak działa" + „Program testowy" z formularzem), `/fragment`, `/testuj`. Wypisz pliki odpowiadające każdej.
- [ ] Znajdź **formularz zgłoszeniowy**: dokąd realnie wysyła dane (endpoint / Cloudflare Worker / usługa zewnętrzna?), jakie pola, oraz pole-honeypot „HP". Udokumentuj — tego nie wolno zepsuć.
- [ ] Sprawdź obecne `<title>`, meta-description, OG-tags, favicon, język (`lang="pl"`).

**STOP.** Zaraportuj ustalenia 0 w formie tabeli plików → odpowiedzialność, a następnie przedstaw **proponowaną architekturę informacji (Faza 1)** do akceptacji. Dopiero po „OK" przechodź dalej.

---

## FAZA 1 — Architektura informacji (rekomendacja domyślna, do potwierdzenia)

**Rekomendowany model: rozwidlenie na home + dwie dedykowane podstrony.** (Alternatywy w notce niżej — jeśli user wybierze inaczej, dostosuj.)

- [ ] **`/` (home) = rozdzielacz (fork).** Krótki, neutralny hero o Radzie/polifonii (wspólny rdzeń, bez przechyłu B2B/B2C), a pod nim **dwa wyraźne wejścia**:
  - „**Dla firm**" → `/firmy`
  - „**Dla Ciebie**" → `/osobista`
- [ ] **`/firmy`** — pełna narracja B2B (przeniesiona i rozwinięta z obecnej treści RevOps/Operations + closed beta).
- [ ] **`/osobista`** — narracja B2C (tryb `personal`), z blokiem compliance (disclaimer + ścieżka kryzysowa + AI disclosure).
- [ ] **`/fragment`** — zostaje jako **wspólna** warstwa filozoficzna (działa dla obu ścieżek; nie przechylaj jej w stronę firm).
- [ ] **`/testuj`** — formularz; rozszerz o wybór ścieżki (patrz Faza 4) albo rozdziel na dwa CTA.
- [ ] **Nawigacja** w headerze odzwierciedla obie ścieżki bez chaosu (np. „Dla firm · Dla Ciebie · Fragment · Jak działa").

> Notka — alternatywne modele, jeśli user woli: (A) jedna home z dwiema kolumnami/kartami zamiast osobnych podstron; (B) toggle „Firma / Ja" przełączający copy in-place. Domyślnie realizuj rozwidlenie z podstronami — jest najczystsze dla SEO i dla rozjazdu tonów.

---

## FAZA 2 — Copy: ścieżka „Dla firm" (`/firmy`)

- [ ] Przenieś istniejący, działający przekaz B2B i wyostrz pod tryb `fa2`: decyzje operacyjne, napięcia w zespole, scenariusze Base/Bull/Bear, „nie demo — prawdziwe decyzje".
- [ ] Zachowaj closed-beta/kontrolowany dostęp dla firm („rekrutujemy liderów RevOps i Operations").
- [ ] Utrzymaj ton anty-motywacyjny. Żadnego „zwiększ produktywność o X%".
- [ ] CTA: „Zgłoś zespół do programu testowego" → `/testuj?track=firma` (lub odpowiednik z Fazy 4).

## FAZA 3 — Copy: ścieżka „Dla Ciebie" (`/osobista`)

- [ ] Napisz narrację B2C w tonie `personal`: decyzje życiowe, integracja wewnętrznych konfliktów, „decyzja, której nie podejmujesz sam — bo nie widzisz całej swojej mapy". Surowo, bez afirmacji.
- [ ] Opisz, **co system robi** (mapuje perspektywy: logika, ciało, cień, czas; pokazuje, co w decyzji pozostaje niewygodne), a **nie obietnicę efektu zdrowotnego**.
- [ ] **Blok compliance (obowiązkowy, widoczny):**
  - [ ] disclaimer: „To nie jest pomoc medyczna ani terapeutyczna.";
  - [ ] AI disclosure: „Rozmawiasz z systemem AI (Radą), nie z człowiekiem.";
  - [ ] ścieżka kryzysowa: krótki blok „Jeśli jesteś w kryzysie…" + `[DO UZUPEŁNIENIA: kontakt kryzysowy]` (TODO);
  - [ ] prywatność/local-first: „Twoje debaty zostają lokalnie; model działa na Twoim kluczu (BYOK)." — tylko jeśli zgodne z faktycznym modelem dystrybucji.
- [ ] CTA: „Dołącz do wczesnego dostępu" → `/testuj?track=osobista` (lub waitlist).

---

## FAZA 4 — Formularze i dane

- [ ] **Nie psuj** istniejącego endpointu zgłoszeń ani honeypotu „HP".
- [ ] Dodaj rozróżnienie ścieżki w zgłoszeniu: pole ukryte/`select` `track = firma | osobista` (z parametru URL `?track=` lub wyboru w formularzu), żeby leady się nie zlewały.
- [ ] Dla ścieżki firmowej zachowaj pola: imię i nazwisko, stanowisko/firma, **email służbowy**, website.
- [ ] Dla ścieżki osobistej: imię, email — **nie zbieraj** danych wrażliwych w formularzu (żadnych pytań o zdrowie/uzależnienia).
- [ ] Zachowaj komunikat „Dane trafiają do zabezpieczonego endpointu. Bez spamu."
- [ ] Jeśli endpoint to Cloudflare Worker — zweryfikuj, że nowe pole `track` jest po stronie odbioru obsłużone lub przynajmniej nieblokujące.

---

## FAZA 5 — Spójność, SEO, dostępność

- [ ] Zaktualizuj `<title>` i meta-description **per strona** (`/firmy`, `/osobista`) oraz OG-tags.
- [ ] `lang="pl"`; nagłówki w logicznej hierarchii (jeden `<h1>` na stronę).
- [ ] Social SEO: słowa kluczowe w treści i meta (zgodnie z trendem 2026 — search-first), bez keyword-stuffingu.
- [ ] Spójna paleta/typografia z obecną stroną (złoty akcent „momentu syntezy"); nie wprowadzaj nowego brandingu.
- [ ] A11y: kontrast, focus-state na CTA, alt-teksty wizualizacji „polifonii".
- [ ] Linkowanie wewnętrzne: home ↔ `/firmy` ↔ `/osobista` ↔ `/fragment` ↔ `/testuj` spójne, bez martwych linków.

---

## FAZA 6 — QA i wdrożenie

Kryteria akceptacji (wszystkie muszą przejść):

- [ ] Istniejące URL-e (`/`, `/fragment`, `/testuj`) **nadal działają** (brak 404, brak utraty istniejących leadów).
- [ ] Obie nowe ścieżki dostępne z home w ≤1 kliknięciu; oba CTA prowadzą do działającego formularza z poprawnym `track`.
- [ ] **Grep regresji roszczeń:** brak słów „terapia/leczy/wyleczysz/diagnoza/medyczn*" w kontekście obietnicy efektu. Wypisz wszystkie trafienia do akceptacji.
- [ ] Disclaimer + AI disclosure + blok kryzysowy obecne i widoczne na `/osobista`.
- [ ] Honeypot „HP" nienaruszony; formularz wysyła do tego samego (lub świadomie zaktualizowanego) endpointu.
- [ ] Build przechodzi lokalnie; podgląd (`dev`/preview) renderuje obie ścieżki.
- [ ] Notatka deploy dla Cloudflare (Pages/Worker): co zmieniono w routingu/configu; **nie** zmieniaj sekretów ani ustawień projektu Cloudflare bez wskazania użytkownika.

Na koniec: krótkie podsumowanie zmian (lista plików + diff-highlights) i lista **TODO dla użytkownika** (kontakt kryzysowy, weryfikacja endpointu `track`, ewentualna polityka prywatności sprzedaży).

---

## Czego NIE robić
- Nie dodawaj roszczeń terapeutycznych/medycznych ani języka motywacyjnego.
- Nie przeprojektowuj brandingu „przy okazji".
- Nie ruszaj sekretów, DNS, ani ustawień Cloudflare bez wyraźnej zgody.
- Nie usuwaj ani nie nadpisuj istniejącego endpointu leadów — rozszerzaj, nie zastępuj.
- Nie zgaduj stacku — jeśli czegoś nie ustaliłeś w Fazie 0, zapytaj.
