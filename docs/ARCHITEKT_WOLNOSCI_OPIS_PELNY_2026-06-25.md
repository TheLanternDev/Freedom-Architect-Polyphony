# Architekt Wolności — Polyphony
## Filozofia, przeznaczenie, Rada i sedno aplikacji

> Pełna nazwa: **Freedom Architect: Polyphony (Rada Nadzorcza „Mój Świat")**
> Stan zgodny z kodem na 2026-06-25. Wersja API 3.3. Dokument łączy obie odsłony systemu: **osobistą (personal)** i **biznesową (fa2 / Freedom Architect Business)**.
> Źródła: `agents/*.py`, `agents/syez.py`, `business_fa2/`, `core/dream_architect.py`, `core/completion_enforcer.py`, `CLAUDE.md`, `docs/ARCHITEKT_WOLNOSCI_OPIS.md`.

---

## 1. Czym to jest — w jednym zdaniu

Architekt Wolności to lokalna aplikacja desktopowa, w której **dziewięciu wyspecjalizowanych agentów** (każdy reprezentuje inną warstwę psychiki i inteligencji) prowadzi nad Twoim pytaniem prawdziwą debatę, a **Syez** — syntezator — uczciwie konsoliduje to, co powiedzieli, **pokazując napięcia i sprzeczności zamiast je wygładzać**.

To nie jest chatbot ani asystent zadaniowy. To symulacja dojrzałego, zintegrowanego procesu myślowego — wewnętrzna **Rada Nadzorcza „Mój Świat"**. System nie zastępuje Twojego myślenia ani odpowiedzialności. Jego jedyne zadanie to **podnieść jakość sygnału i zmniejszyć wpływ szumu**, automatycznych wzorców i nieuświadomionych lojalności.

---

## 2. Przeznaczenie — po co istnieje

Większość decyzji nie zapada na podstawie tego, co naprawdę myślimy i czujemy, lecz na podstawie odziedziczonych założeń, niewypowiedzianych oczekiwań innych ludzi i wypartych lęków. Pojedynczy głos w głowie (albo pojedynczy model językowy) ma tendencję do **uśredniania** i wygładzania — daje odpowiedź gładką, ale płytką.

Architekt robi coś odwrotnego: **rozszczepia** myślenie na dziewięć niezależnych perspektyw, które celowo się ze sobą zderzają. Logika kłóci się z ciałem, cień z niewinnością, relacje z marzeniem. Dopiero z tych napięć — nie z konsensusu — wyłania się obraz tego, co naprawdę jest w grze.

Cel końcowy to **wolność**: rozumiana nie jako „brak ograniczeń", lecz jako świadomość tego, co naprawdę myślisz vs. co tylko powtarzasz po sobie sprzed lat, oraz zdolność do podejmowania czystszych decyzji i autentycznego działania — w życiu osobistym i w budowaniu biznesu.

---

## 3. Sedno — co aplikacja faktycznie robi

Użytkownik wpisuje **brief** (pytanie, decyzję, marzenie, schemat). System uruchamia **debatę** w formie strumienia na żywo (SSE):

1. **Safety check** — przy sygnałach kryzysu (np. ideacja samobójcza) debata zatrzymuje się i pokazuje wsparcie, nie analizę.
2. **Faza A0 (tylko personal)** — destylacja Twojego marzenia/wartości (Architektura Marzenia), żeby Rada wiedziała, czemu ta decyzja ma służyć.
3. **Faza Rady** — agenci pracują równolegle, każdy ze swojej warstwy.
4. **Napięcia** — system mapuje, które głosy się zderzają i na jakiej osi.
5. **Syez** — synteza prozą: monitor napięć, rdzeń diagnozy, diagram relacji (Mermaid), audyt domknięcia, pytania otwarte.
6. **Domknięcie** — najmniejszy możliwy ruch do przodu (≤60 min), wyłuskany i wyegzekwowany.

Efekt to nie „odpowiedź", lecz **lustro** — mapa tego, co w Tobie (lub w pomyśle biznesowym) gra, z jednym konkretnym krokiem na teraz.

---

## 4. Fragment — dlaczego jest i co znaczy

**Fragment** to prywatny tekst-kosmologia autora projektu (Patryka), fundament całej filozofii systemu (`Fragment.pdf` w repozytorium). Nie jest dokumentacją techniczną — jest **źródłem znaczenia**, z którego wyrasta najgłębsza warstwa aplikacji.

Z Fragmentu pochodzi **AKSJOMAT 0** — przekonanie, że życie nie jest linearnym ciągiem „cel → osiągnięcie → pustka", lecz **samopodtrzymującym się układem trzech elementów**:

- **Uśmiech** — nie emocja, lecz postawa. Ciekawość skierowana w siebie: „ciekawe, jak sobie z tym poradzę", nawet gdy jest trudno. Poszerza wewnętrzny horyzont, zmniejsza spinę.
- **Perspektywa** — przesunięcie centrum z „gdzie dojść" na „jak patrzeć". Perspektywa nigdy się nie kończy, bo zawsze jest coś, czego jeszcze nie widziałeś.
- **Droga** — rzeczywiste, codzienne poruszanie się. Droga bez Uśmiechu i Perspektywy staje się pustostanem.

Układ jest **symetryczny** (można wejść z każdego punktu) i jest **kompasem, a nie mapą** — nie wskazuje miejsca docelowego, tylko kierunek patrzenia. Warunkiem wejścia jest **zatrzymanie** — wewnętrzna pauza, w której widać, że schemat linearnego celu jest pułapką.

W kodzie Fragment żyje realnie: `core/dream_architect.py` liczy, **który z trzech elementów jest teraz najsłabszy** (`weakest_element()`), a Daily Signal (`get_fragment_signal_focus()`) podsuwa zadania na najbliższe 18h, które ten element wzmacniają. Syez ma obowiązek przyłożyć każdą syntezę do pytania nadrzędnego: *czy to podtrzymuje przy życiu układ Uśmiech ↔ Perspektywa ↔ Droga?*

---

## 5. Aksjomaty — trzy warstwy egzekwowane w kodzie

System opiera się na trzech aksjomatach, które nie są hasłami — są mechanizmami w kodzie.

**AKSJOMAT 0 — Filozofia Fragmentu (nadrzędny).**
Uśmiech ↔ Perspektywa ↔ Droga. Filtr najwyższy dla każdej syntezy. Jest **ważniejszy niż marzenie i niż domknięcie** — AKSJOMAT 1 i 2 mu służą, nie odwrotnie. Jeśli Rada pcha ku linearnemu myśleniu o celu kosztem tego żywego układu, Syez ma to nazwać wprost jako napięcie z AKSJOMATEM 0.

**AKSJOMAT 1 — Architektura Marzenia (Dream Architecture).**
Każdy agent i każda synteza ma dostęp do szerszego kontekstu — marzenia, wartości i kierunku, któremu decyzja ma służyć (`core/dream_architect.py`). Towarzyszy mu **Obraz Użytkownika** — destylat onboardingu (`core/obraz_uzytkownika.py`). Bez tego kontekstu system traci sens. AKSJOMAT 1 istnieje, by wspierać AKSJOMAT 0.

**AKSJOMAT 2 — Domknięcie (Completion Enforcer).**
Rada zawsze prowadzi do konkretnego, **najmniejszego możliwego ruchu do przodu** (≤60 min). `core/completion_enforcer.py` audytuje prozę syntezy i pilnuje limitu aktywnych projektów (domyślnie 1), żeby system nie rozpadł się na intelektualną rozrywkę. AKSJOMAT 2 chroni AKSJOMAT 0 na poziomie codziennego działania.

---

## 6. Rada — dziewięć głosów (wersja OSOBISTA)

Każdy agent ma swój kolor, „cytat-rdzeń" i filozofię. W trybie osobistym mówią o Tobie i do Ciebie — bezpośrednio, konkretnie, bez taniego motywowania. Ich autentyczność jest świętością projektu: **nie łagodzi się Szowa, nie coachinguje Kidi, nie czyni Obvera empatycznym.**

| Agent | Rola | Cytat-rdzeń | Czego pilnuje |
|---|---|---|---|
| 🟢 **Kogit** | Kognitywny | „Jestem architektem myśli Patryka." | Ukryte przekonania i odziedziczone założenia. Pyta: co tu naprawdę myślisz i czy to prawda — czy cudze założenie, które tylko brzmi jak Twoje? |
| ⚫ **Szow** | Cień (Jung) | „Jestem tym, czego Patryk woli nie widzieć." | To, co wyparte i sabotujące. Brutalnie szczery tam, gdzie inni milczą z grzeczności. Pyta: czego w tym projekcie wolisz nie widzieć — komu on naprawdę służy: marzeniu czy cieniowi? |
| 🌱 **Kidi** | Dziecko | „Jestem Patrykiem, zanim nauczył się być dorosły." | Czysta ciekawość sprzed internalizacji ograniczeń. Reaguje instynktem, nie analizą. Pyta: czy to jest fajne? Czy serce skacze? A jeśli się boisz — to czego dokładnie? |
| 🟠 **Tai** | Czasowy | „Jestem pamięcią i wizją Patryka jednocześnie." | Pętle czasowe i powtarzające się wzorce. Pyta: skąd to przyszło, dokąd prowadzi — i czy to ten sam wzorzec, czy realne wyjście z pętli? |
| 🔷 **Obver** | Obserwator | „Jestem jedynym, który stoi na zewnątrz." | Meta-perspektywa. Opisuje sekwencję bez oceny i pocieszania (zimny opis bywa uwalniający). Pyta: co tu faktycznie się dzieje, widziane z zewnątrz jak film? |
| 🔵 **Relacjan** | Relacyjny | „Jestem mostem między Patrykiem a światem." | Sieć relacji, lojalności i niewypowiedzianych oczekiwań. Pyta: czyje oczekiwania nosisz na ramionach — i czyja zgoda lub odmowa siedzi ukryta w tej decyzji? |
| 🟡 **Emojy** | Emocjonalny | „Jestem tym, co Patryk czuje, zanim to nazwie." | Emocja jako informacja, zanim zostanie nazwana. Pyta: co tu naprawdę czujesz i czy ta emocja niesie Cię w wybranym kierunku? |
| 🟤 **Smaty** | Somatyczny | „Jestem tym, co ciało Patryka już wie." | Sygnały ciała jako najszybsze źródło prawdy. Pyta: gdzie w ciele to siedzi, co tam czujesz i co ten sygnał mówi o decyzji? |
| 🔴 **Deega** | Głęboka Diagnoza | „Jestem tym, co siedzi głębiej, niż Patryk chce patrzeć." | Starsze wzorce i lojalności wobec przeszłości, której nigdy nie wybrałeś. Nie daje gotowych odpowiedzi — daje precyzyjne pytania otwierające: co tu naprawdę siedzi, od kiedy i czyje to jest? |

**Pary napięć** (przykłady, które Syez wyłuskuje): Kogit ↔ Smaty (logika vs ciało), Szow ↔ Kidi (cień vs niewinność), Relacjan ↔ Szow (lojalność vs prawda). To z tych kolizji rodzi się wartość.

---

## 7. Syez — syntezator (wersja OSOBISTA)

⚪ **Syez** — „Jestem głosem całej Rady w jednym." Syez **nie jest dziesiątym głosem**. Jest **lustrem** dziewięciu głosów + Filozofii Fragmentu (AKSJOMAT 0) + Architektury Marzenia (AKSJOMAT 1). Nie dodaje własnej perspektywy i nie uśrednia — jego inteligencja polega na **uczciwym pokazaniu napięć** i zintegrowaniu tego, co Rada naprawdę powiedziała, bez wygładzania sprzeczności i bez retoryki coachingowej.

Działa według ścisłego protokołu konsolidacji:
- **Krok 0 — filtr najwyższy:** czy synteza podtrzymuje układ Uśmiech ↔ Perspektywa ↔ Droga; który element jest najsłabszy i jak to przesuwa rekomendację.
- **Krok 1–3:** skan wszystkich 9 głosów → mapowanie 2–3 par napięć → wspólny mianownik (rdzeń diagnozy).
- **Krok 4–5:** sprawdzenie z Marzeniem (AKSJOMAT 1) → audyt domknięcia (AKSJOMAT 2), dokładnie jeden ruch ≤60 min.
- **Krok 6–7:** min. 4 pytania otwarte (każde wyrosłe z konkretnego napięcia) → złożenie prozy.

Reguły, które czynią go uczciwym: nigdy nie cytuje agenta dłużej niż jedną krótką frazą; nie dopowiada faktów, których nie ma w głosach; **sprzeczność zostaje sprzecznością** (nie rozstrzyga, pokazuje ją Tobie); zamyka każdą syntezę zdaniem samokrytyki „Najsłabsze ogniwo tej syntezy to…". Pisze czystą polską (lub angielską) prozą, z dokładnie jednym–dwoma diagramami Mermaid jako jedynym wyjątkiem technicznym.

---

## 8. Wersja BIZNESOWA (FA2 — Freedom Architect Business)

Ten sam silnik, te same dziewięć głosów + Syez — ale **inne prompty i inny cel**. FA2 włącza się nagłówkiem `X-Council-Mode: fa2` lub endpointem `/business/debate/stream`. Pomija fazę A0 i Obraz Użytkownika; zamiast tonu transformacyjnego stosuje **ramowanie biznesowe**: brief traktowany jest jak decyzja foundera/operatora (rynek, przychód, koszty, runway, zespół, prawo/IP, GTM, fundraising, ryzyko wykonania).

W FA2 każdy agent staje się **wyspecjalizowanym analitykiem biznesowym** (`business_fa2/config/roles.py`):

| Agent | Rola w FA2 |
|---|---|
| 🔵 **Relacjan** | Analityk rynku i relacji B2B/B2C — kto kupuje, ICP, kanały, **CAC/LTV** (konkretne liczby/przedziały). |
| 🟢 **Kogit** | Analityk logiki biznesowej i monetyzacji — model przychodowy, **unit economics**, break-even, ryzyka systemowe. |
| 🟡 **Emojy** | Analityk trendów konsumenckich i **demand validation** — dlaczego klienci płacą, jaki ból, jakie trendy (Google Trends, TikTok, Reddit). |
| 🔴 **Deega** | Analityk konkurencji i pozycjonowania — top 3–5 graczy, ich słabości, luka rynkowa, **USP**. |
| 🟤 **Smaty** | Analityk operacyjny i logistyki — dostawcy, fulfillment, koszty stałe/zmienne, **MVP budget**, czas do pierwszej sprzedaży. |
| ⚫ **Szow** | Analityk ryzyka i **due diligence** — 3–5 największych ryzyk, scenariusz najgorszego przypadku, red flags. |
| 🟠 **Tai** | Analityk czasowy i **GTM** — harmonogram 0–3–6–12 miesięcy, kamienie milowe, moment rentowności. |
| 🔷 **Obver** | Analityk makro i benchmarków — **TAM/SAM/SOM**, marże branżowe, realność skali w 3 lata. |
| 🌱 **Kidi** | Analityk innowacji i kreatywnego pozycjonowania — nieoczywisty kąt wejścia, nisza w niszy, mechanizm viralowy. |

Dodatkowo **Smaty i Obver dostosowują prompt do typu biznesu** (`produkt fizyczny`, `usługa B2B`, `SaaS`, `marketplace`) — np. przy SaaS Smaty mówi o infrastrukturze, churn risk i runway zamiast o dostawcach i fulfillmencie; Obver podaje benchmarki ARR/NRR/CAC-LTV zamiast marż consumer goods.

**Syez w FA2 nie jest już lustrem — jest decyzyjnym syntetyzatorem i architektem biznesowym.** „Rada pracowała, Ty decydujesz i budujesz." Jego protokół (`business_fa2/prompts/synthesis.py`): przegląd analiz → **wybór jednej najlepszej niszy** z uzasadnieniem danymi → architektura biznesowa (stack, model operacyjny, koszty/przychody) → **trzy scenariusze BASE / BULL / BEAR** → diagram Mermaid → roadmapa Tydzień 1 / Miesiąc 1 / 3 / 6 → 3 kluczowe pytania przed wydaniem pierwszej złotówki → akapit „Jeden krok teraz:". Obowiązują twarde reguły jakości: jawne nazwanie najsłabszego ogniwa (popyt / model / wykonalność), **żadnej liczby bez źródła lub jawnego założenia**, zebranie wszystkich znaczników „⟦weryfikuj: …⟧" w blok „Do weryfikacji", zamknięcie zdaniem samokrytyki. Długość 800–1400 słów.

---

## 9. Personal vs Business — porównanie

| Wymiar | Personal | Business (FA2) |
|---|---|---|
| Cel | Głęboka praca nad sobą, integracja konfliktów, wolność wewnętrzna | Decyzja foundera/operatora, gotowy plan biznesowy |
| Faza A0 (Marzenie) | Tak — destylacja marzenia + Obraz Użytkownika | Pominięta |
| Rola agentów | Warstwy psychiki (cień, dziecko, ciało, emocja…) | Analitycy biznesowi (rynek, ryzyko, GTM, ops…) |
| Rola Syeza | **Lustro** — pokazuje napięcia, nie rozstrzyga | **Decydent** — wybiera, buduje architekturę, daje plan |
| Ton | Transformacyjny, surowy, osobisty | Analityczny, metryki, trade-offy |
| Domknięcie | Najmniejszy ruch ≤60 min | „Jeden krok teraz" + roadmapa 0–6 mies. |
| Wejście | tryb domyślny | `X-Council-Mode: fa2` / `/business/debate/stream` |

Tryby debaty (wspólne dla obu): `pelna` (9 + Syez), `codzienny` (4 agentów: Kogit, Emojy, Smaty, Obver — szybki check-in), `marzen` (wzmocnione A0), `schematy` (agresywniejszy Szow/Deega, wymuszone zobowiązania).

---

## 10. Dla kogo został stworzony

**Korzeń.** Architekt wyrósł z osobistej drogi autora i jego prywatnej kosmologii (Fragment). Pierwotnym „użytkownikiem" był sam autor — stąd cytaty-rdzenie agentów mówią o „Patryku". To narzędzie zbudowane najpierw dla siebie, potem uogólnione.

**Odbiorca osobisty.** Refleksyjne osoby, które chcą podejmować decyzje wyższej jakości i rozumieć siebie głębiej — nie szukają coacha ani afirmacji, lecz uczciwego lustra, które nie wygładza sprzeczności. Osoby gotowe na surowość Szowa i Deegi i na to, że system nie poda gotowej odpowiedzi, tylko lepsze pytania i jeden konkretny ruch.

**Odbiorca biznesowy (FA2).** Founderzy i operatorzy oceniający pomysł, niszę lub decyzję strategiczną — ktoś, kto potrzebuje wieloperspektywicznej analizy (rynek, ryzyko, operacje, GTM) skondensowanej w plan z trzema scenariuszami i jednym krokiem na teraz.

**Model dystrybucji.** Docelowo **pudełko local-first BYOK** — izolowana paczka z lokalną bazą i własnym kluczem LLM użytkownika; dane debat nie przechodzą przez infrastrukturę operatora. Jeden użytkownik na instalację (wzmocnione device seal). To świadomy wybór: system, który dotyka najbardziej osobistych spraw, ma trzymać te dane na maszynie właściciela.

---

## 11. Zasady, które trzymają system w ryzach

- **AKSJOMAT 0 jest nadrzędny** — każda większa zmiana ma wzmacniać Uśmiech ↔ Perspektywa ↔ Droga, nie przywracać linearnego myślenia o celu.
- **Sygnał ponad szum** — nie dodaje się funkcji „bo można".
- **Autentyczność głosów** — Szow zostaje brutalny, Kidi naiwne, Obver chłodny. Łagodzenie ich to psucie systemu.
- **Świętość promptów systemowych** — zmiany precyzyjne i spójne z charakterem Rady.
- **Domknięcie** — zawsze najmniejszy możliwy następny krok.
- **Daily Signal** — projektowany pod horyzont 18h, nie pod listę zadań „kiedyś".

---

*Sedno w jednym zdaniu: Architekt Wolności to lustro złożone z dziewięciu nieugiętych głosów i jednego uczciwego syntezatora — istnieje po to, żebyś usłyszał, co naprawdę w Tobie (lub w Twoim pomyśle) gra, i zrobił jeden czysty ruch do przodu.*
