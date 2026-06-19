# Prompt dla Cursora — naprawa reela Rady do spec (v2.1 → v2.2)

> Wklej całość jako zadanie w Cursorze, w repo **reel-forge / aw-reels** (pipeline `finishing.py` + alignment + klipy Grok).
> Pracuj **krok po kroku**. Po Fazie 0 (Discovery) **zatrzymaj się i pokaż ustalenia + plan cięć**, zanim cokolwiek zmienisz. Nie zgaduj struktury repo.

---

## 0. Kontekst (zweryfikowany klatka-po-klatce na `reel-council-grok-10spots-v2.mp4`)

Reel 9:16, ~40 s, marka **Architekt Wolności** (ciemne tło, złoty serif #E8D5A3). VO: paraliż → kontrast („nie chatbot / nie coaching") → Rada → synteza → CTA „Odkryj swoją polifonię". Pipeline: klipy Grok I2V (część z **wypalonym** tekstem) + warstwa napisów z alignmentu (ASS/drawtext) + `finishing.py` (FFmpeg, slots + `-shortest`).

**Co JUŻ naprawione na renderze (v2.1, nie ruszaj tego ponownie):** dołożona karta końcowa „Odkryj swoją polifonię" (złoty serif na czerni, fade), długość 42,4 s, audio znormalizowane 96 kHz → 48 kHz. v2.1 to salvage outputu — **prawdziwe** naprawy poniżej idą w źródle i dają v2.2.

**Defekty do usunięcia w źródle (potwierdzone):**

| ID | Defekt | Dowód z klatek | Warstwa |
|----|--------|----------------|---------|
| P1 | Końcówka VO ucięta (`-shortest` tnie 42,35 s VO do 40 s wideo) | audio = video = 40,0 s; „Odkryj swoją polifonię" przepada | `finishing.py` |
| P2 | Potrójna warstwa tekstu (Grok-baked + napisy VO) | 0:08 „Wątpli/Strąch" + „Pętla" + dolny blok jednocześnie | `finishing.py` + klipy |
| P3 | Spotlight niechlujny, brak „jedno słowo na beat" | 0:08 „Wątpli"+„Strąch" zlane, literówka „Strąch" | klip spotlight (Grok) |
| P4 | Scena drzwi praktycznie nieobecna | ~0:30–0:36 glow+CTA zamiast drzwi | klip 05_doors (Grok) |
| P5 | Koło Rady = znaki **zodiaku**, nie 9 symboli | 0:28 mandala z glifami zodiaku | klip council (Grok) |
| P6 | Outro = pełna mandala CTA, brak intymnego domknięcia | 0:39 „Architekt Wolności / Zgłoś się teraz" | `finishing.py` outro |
| P7 | Desync obraz ↔ VO | 0:21 „To jest Rada" nad złą klatką; 0:28 CTA przy VO o ścieraniu | `finishing.py` timing |

**Cel v2.2:** jedna czytelna warstwa tekstu, klipy bez wypalonego tekstu, 9 symboli, drzwi obecne, outro intymne, obraz zsynchronizowany z VO, pełne 42,3–42,5 s.

### Twarde ograniczenia (nie wolno złamać)
1. **Audio-first.** Alignment VO jest źródłem prawdy dla czasu. Wideo dopasowujemy do beatów VO, nigdy odwrotnie.
2. **Jedna warstwa tekstu.** Tekst żyje w warstwie napisów (ASS/drawtext z alignmentu), **nie** w klipach Grok. Wyjątki: dwie czyste karty baked „…Rada." (0:20, 0:37) — patrz §3.
3. **Marka:** ciemne tło, złoty serif #E8D5A3. Zero hype'u, zero tonu coachingowego. Bez roszczeń terapeutycznych.
4. **Brak nadmiarowych kredytów:** regeneruj **tylko** 3 klipy z listy §2. Reszta bez ruszania.
5. **Determinizm:** każda zmiana w `finishing.py` ma być idempotentna i odtwarzalna z manifestu.

### Nie ruszać
Neural head (0:00–0:05, ew. drobny crop), transition particles (~0:14–0:18), karta baked „Architekt Wolności / Nie chatbot. Nie coaching. **Rada.**" w 0:20 (czysta, on-brand), normalizacja audio 48 kHz.

---

## FAZA 0 — Discovery (NIE zmieniaj — zbadaj i zaraportuj)

- [ ] Zlokalizuj `finishing.py` i wypisz: jak buduje timeline (sloty czasowe vs concat), gdzie jest `-shortest`, gdzie wstrzykuje `frame_caption_texts`/ASS/drawtext.
- [ ] Znajdź **manifest** produkcji (np. `production_manifest.yaml`) — lista slotów, czasy, ścieżki klipów, teksty napisów.
- [ ] Znajdź **alignment VO** (plik z timestampami słów/zdań). Wypisz dokładny czas końca („Odkryj swoją polifonię") — oczekiwane ~42,35 s.
- [ ] Zinwentaryzuj klipy źródłowe: który plik = spotlight, council, doors (np. `05_doors`). Sprawdź, czy istnieją „legacy frame" do reg0 drzwi.
- [ ] Znajdź konfigurację promptów Grok (gdzie definiowane są prompty I2V) i czy jest pole negative prompt.
- [ ] Sprawdź bramkę **coverage 1:1** (jeśli istnieje w pipeline/aw-studio) — jak liczy pokrycie audio↔wideo.

**STOP.** Zaraportuj: tabela slot → czas → klip → tekst napisu, lokalizacja `-shortest`, czas końca VO, lista 3 klipów do regen. Przedstaw **plan cięć audio-first** (każdy slot dosztukowany do beatu VO). Po „OK" → dalej.

---

## FAZA 1 — Naprawy w pipeline (P1, P2, P7) — kod, zero kredytów

- [ ] **P1 — usuń truncację.** W `finishing.py` usuń `-shortest`. Ustaw długość wyjścia na **długość VO z alignmentu** (np. `-t {vo_end}` lub dopaduj wideo `tpad`/freeze ostatniej klatki do `vo_end`). Done = `ffprobe duration` ≈ 42,3–42,5 s, audio niecięte.
- [ ] **P2 — jedna warstwa tekstu.** Wyłącz wstrzykiwanie `frame_caption_texts` **poza** dwiema kartami baked (0:20, 0:37). Cała reszta tekstu = wyłącznie warstwa napisów z alignmentu. Done = w żadnej klatce nie ma jednocześnie tekstu baked + dolnego napisu (poza kartami).
- [ ] **P7 — sync audio-first.** Przypisz każdy slot wideo do okna czasowego z alignmentu, tak by obraz odpowiadał wypowiadanemu zdaniu:
  - „To nie jest chatbot…" → sylwetka+koło (~13 s)
  - „To jest Rada." → mandala 9 symboli (nie wcześniej niż VO)
  - „…ścierają się…" → council/synthesis (NIE karta CTA)
  - CTA „Odkryj swoją polifonię" → outro (§3)
  - Done = przy odsłuchu każde zdanie VO pada na właściwą scenę (±0,3 s).
- [ ] Zachowaj `-color_range`/pełny zakres tak, by złoty serif nie ginął w cieniu (pipeline już to robi — nie psuj).

**Brama Fazy 1 (bez regeneracji):** render „v2.2-rc1" ma 42,3–42,5 s, jedną warstwę tekstu, poprawny sync. To samo w sobie zamyka P1/P2/P7.

---

## FAZA 2 — Regeneracja 3 klipów Grok (P3, P4, P5) — tylko te trzy

Reguła nadrzędna dla **każdego** promptu I2V: **zero tekstu w klipie.** Słowa dokłada wyłącznie warstwa napisów.

- [ ] **Spotlight (P3)** — sylwetka w stożku światła, ciemne tło. Choreografia: jedna emocja na beat (Wątpliwość → Strach → Pętla → Paraliż) **realizowana ruchem/światłem**, nie tekstem. Zastępuje obecny klip z literówką „Strąch".
- [ ] **Council (P5)** — złote koło z **dokładnie 9** symbolami Rady (NIE znaki zodiaku, NIE 10–12 ikon). Jeśli istnieje kanoniczny zestaw 9 glifów agentów (Kogit, Szow, Kidi, Tai, Obver, Relacjan, Emojy, Smaty, Deega) — użyj go jako referencji obrazowej. Bez napisu „Architekt Wolności" w klatce.
- [ ] **Doors (P4)** — mocne drzwi z przebijającym strumieniem światła (~0:31–0:37). Regen z legacy frame, jeśli jest. Bez tekstu.
- [ ] Po regen: podmień ścieżki w manifeście, **nie** zmieniaj pozostałych slotów.

Szablony promptów (EN, do Grok) — w Załączniku A.

**Brama Fazy 2:** 3 nowe klipy bez wypalonego tekstu; council ma policzalne 9 symboli; drzwi czytelne jako drzwi.

---

## FAZA 3 — Outro intymne (P6)

- [ ] Zamień pełną mandalę CTA („Architekt Wolności / Zgłoś się teraz") na **intymne domknięcie**: ciemne tło, subtelny złoty blask lub jeden symbol, centralnie złoty serif **„Odkryj swoją polifonię"** (#E8D5A3), fade-in 0,5 s / fade-out 0,5 s.
- [ ] Możesz wykorzystać gotową kartę z **v2.1** jako kanoniczny asset outro (już zrenderowana, zgodna z marką) — dla spójności.
- [ ] Karta baked „…Rada." w 0:20 zostaje jako mid-point; outro to osobny, czystszy beat.
- [ ] Done = ostatnie ~2,3 s to spokojne domknięcie z puentą VO, bez przeładowanej mandali.

---

## FAZA 4 — QA / kryteria akceptacji (wszystkie muszą przejść)

- [ ] **Długość:** `ffprobe duration` 42,3–42,5 s; audio nieucięte (ostatnie słowo VO słyszalne w całości).
- [ ] **Jedna warstwa tekstu:** ekstrakcja klatek na 0:05, 0:08, 0:20, 0:28, 0:37, 0:41 — w żadnej (poza kartami 0:20/0:37) nie ma podwójnego tekstu. Zero literówek w jakimkolwiek widocznym słowie.
- [ ] **Council = 9:** na klatce council policz symbole = 9.
- [ ] **Drzwi:** klatka ~0:33 czyta się jako drzwi ze światłem.
- [ ] **Sync:** odsłuch — każde zdanie VO na właściwej scenie (±0,3 s).
- [ ] **Outro:** ostatni beat = „Odkryj swoją polifonię", spokojny.
- [ ] **Coverage 1:1** (jeśli bramka istnieje) = PASS.
- [ ] **Marka/treść:** zero hype'u, zero roszczeń terapeutycznych, AI-kontekst zachowany.

Komenda pomocnicza do QA (ekstrakcja klatek):
```bash
for t in 5 8 20 28 33 37 41; do ffmpeg -y -ss $t -i v2.2.mp4 -frames:v 1 qa_${t}s.png; done
```

Na koniec: render **`reel-council-grok-v2.2.mp4`**, lista zmian (pliki + diff `finishing.py`), 3 nowe klipy, oraz tabela QA z wynikami.

---

## Czego NIE robić
- Nie zakrywać wypalonego tekstu drawboxem na ruchomym tle (stratne — dlatego regenerujemy klipy).
- Nie regenerować klipów spoza listy 3.
- Nie dodawać tekstu do promptów Grok (żadnego, nawet „brand name").
- Nie wprowadzać języka motywacyjnego/coachingowego ani roszczeń terapeutycznych w napisach/CTA.
- Nie zmieniać neural head, transition particles, karty „…Rada." (0:20), normalizacji audio.

---

## Załącznik A — Szablony promptów Grok (EN, I2V; NO TEXT)

Wspólny **negative prompt** dla wszystkich trzech:
```
no text, no letters, no words, no captions, no subtitles, no typography, no watermark, no logo, no UI, no numbers
```

**Spotlight (P3)**
```
Lone human silhouette sitting hunched under a single hard spotlight, vast dark void around, faint golden volumetric light rays, particles of dust, cinematic 9:16, slow oppressive zoom, sense of doubt and looping paralysis conveyed purely through light and posture. NEGATIVE: no text, no letters, no words, no captions, no typography, no logo.
```

**Council 9 symbols (P5)**
```
A perfect circle of exactly nine distinct glowing golden esoteric glyph-emblems evenly spaced on a deep black background, a bright golden core at center emitting thin tension-lines to each emblem, sacred-geometry, cinematic 9:16, slow rotation. Exactly nine symbols, not zodiac, not astrology. NEGATIVE: no text, no letters, no zodiac signs, no extra icons, no captions, no logo.
```

**Doors (P4)**
```
Massive ancient double doors slowly opening in a dark space, a powerful beam of golden light streaming through the widening gap, dust and particles in the light, cinematic 9:16, hopeful threshold moment, slow push-in. NEGATIVE: no text, no letters, no words, no captions, no logo.
```
