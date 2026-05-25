/**
 * Lekki i18n dla Architekta Wolności: Wielogłos / Freedom Architect: Polyphony.
 *
 * Bez zewnętrznych zależności — kontekst + hook + płaski słownik PL/EN.
 * `t("klucz")` → wybrany język. Wybór trzymamy w localStorage.
 * Klucz HTML `lang` aktualizujemy efektem ubocznym.
 */
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Lang = "pl" | "en";

type Phrase = { pl: string; en: string };

export const DICT: Record<string, Phrase> = {
  // App-level
  "app.brand": { pl: "Architekt Wolności: Wielogłos", en: "Freedom Architect: Polyphony" },
  "app.title.supervisory": { pl: "Rada", en: "Supervisory" },
  "app.title.council": { pl: "Nadzorcza", en: "Council" },
  "app.status.idle": { pl: "Gotowy", en: "Ready" },
  "app.status.agents_speaking": { pl: "Debata w toku", en: "Debate in progress" },
  "app.status.synthesizing": { pl: "Syez syntetyzuje", en: "Syez synthesizing" },
  "app.status.done": { pl: "Debata zakończona", en: "Debate finished" },
  "app.status.error": { pl: "Błąd", en: "Error" },
  "app.btn.reset": { pl: "Resetuj", en: "Reset" },
  "app.mobile_mode_label": { pl: "Tryb (skrót mobilny)", en: "Mode (mobile shortcut)" },
  "app.error.unknown": {
    pl: "Nieznany błąd. Sprawdź czy backend działa na porcie 8000.",
    en: "Unknown error. Check whether the backend is running on port 8000.",
  },

  "setup.title": { pl: "Połączenie lokalne", en: "Local connection" },
  "setup.intro": {
    pl: "Ustaw adres backendu FastAPI i sprawdź endpoint /health. Klucz Anthropic ustawiasz w pliku ui/.env (nie w tej aplikacji) — backend go wczytuje przy starcie. Gdy backend ma ustawione ARCHITEKT_API_KEY, wpisz ten sam token w polu poniżej (albo VITE_ARCHITEKT_API_KEY przy buildzie).",
    en: "Set the FastAPI backend URL and check /health. Put your Anthropic key in ui/.env (not in this UI) — the backend reads it on startup. If the server has ARCHITEKT_API_KEY set, paste the same bearer token below (or use VITE_ARCHITEKT_API_KEY at build time).",
  },
  "setup.url_label": { pl: "Adres API (nadpisanie)", en: "API base URL (override)" },
  "setup.apply": { pl: "Zastosuj", en: "Apply" },
  "setup.test": { pl: "Test /health", en: "Test /health" },
  "setup.test_ok": { pl: "Backend odpowiada.", en: "Backend responded." },
  "setup.test_fail": { pl: "Brak odpowiedzi lub błąd", en: "No response or error" },
  "setup.clear_override": {
    pl: "Usuń nadpisanie URL",
    en: "Clear URL override",
  },
  "setup.architekt_api_label": {
    pl: "Klucz HTTP do API (opcjonalnie)",
    en: "HTTP API key (optional)",
  },
  "setup.architekt_api_placeholder": {
    pl: "Ten sam sekret co ARCHITEKT_API_KEY na serwerze",
    en: "Same secret as server ARCHITEKT_API_KEY",
  },
  "setup.architekt_api_note": {
    pl: "Przechowywany lokalnie w przeglądarce — używaj tylko na zaufanym komputerze. W produkcji preferuj nagłówek wstrzykiwany przez reverse proxy.",
    en: "Stored in the browser — use only on a trusted device. In production prefer injecting the header via reverse proxy.",
  },
  "setup.key_hint": {
    pl: "Nie wklejaj klucza API w to pole — nie jest przesyłany do przeglądarki w trybie bezpiecznym. Trzymaj ANTHROPIC_API_KEY w ui/.env; nie commituj tego pliku (jest w .gitignore).",
    en: "Do not paste your API key here — it is not handled securely in the browser. Keep ANTHROPIC_API_KEY in ui/.env; never commit that file (.gitignore covers it).",
  },
  "setup.security_warn": {
    pl: "Nie wystawiaj backendu na publiczny internet bez reverse proxy i uwierzytelniania — API nie jest zaprojektowane pod otwarty dostęp z sieci.",
    en: "Do not expose the backend to the public internet without a reverse proxy and authentication — the API is not meant for open network access.",
  },
  "setup.telemetry_off": {
    pl: "Telemetria produktu: wyłączona (brak wysyłki danych użycia do operatora).",
    en: "Product telemetry: off (no usage data sent to the vendor).",
  },
  "setup.telemetry_on": {
    pl: "Telemetria: włączona (wymaga osobnej zgody — domyślnie off).",
    en: "Telemetry: enabled (requires separate consent — default off).",
  },
  "setup.close": { pl: "Zamknij", en: "Close" },
  "setup.dismiss_startup": {
    pl: "Nie pokazuj przy starcie",
    en: "Do not show on startup",
  },
  "setup.btn_connection": { pl: "Połączenie", en: "Connection" },

  // Sieć / fetch (useDebate, szczególnie Safari „Load failed”)
  "debate.network.unreachable": {
    pl:
      "Nie udało się połączyć z serwerem (brak odpowiedzi). Uruchom backend: uvicorn main:app --host 127.0.0.1 --port 8000 (z katalogu głównego repozytorium). Aplikacja desktopowa domyślnie woła http://127.0.0.1:8000; przy wdrożeniu w sieci ustaw VITE_API_URL na adres swojego API.",
    en:
      "Could not reach the server (no response). Start the backend: uvicorn main:app --host 127.0.0.1 --port 8000 (from the repo root). The desktop app defaults to http://127.0.0.1:8000; for hosted web builds set VITE_API_URL to your API origin.",
  },
  "debate.network.abort": {
    pl: "Żądanie zostało przerwane.",
    en: "The request was aborted.",
  },
  "debate.network.unknown": {
    pl: "Nieznany błąd sieci lub klienta przy wywołaniu API.",
    en: "Unknown network or client error while calling the API.",
  },
  "debate.stream.broke": {
    pl: "Strumień debaty się urwał — sprawdź logi serwera.",
    en: "The debate stream broke — check the server logs.",
  },
  "app.section.council": {
    pl: "Rada Nadzorcza — perspektywy",
    en: "Supervisory Council — perspectives",
  },
  "app.section.synthesis": { pl: "Synteza (Syez)", en: "Synthesis (Syez)" },
  "app.lang.toggle_tooltip": {
    pl: "Przełącz na angielski",
    en: "Switch to Polish",
  },

  // BriefForm
  "brief.label": { pl: "Brief dla Rady", en: "Brief for the Council" },
  "brief.placeholder": {
    pl: "Opisz sytuację, marzenie albo schemat — przynajmniej pięć słów, żeby Rada miała kontekst...",
    en: "Describe the situation, dream, or pattern — at least five words so the Council hears the context...",
  },
  "brief.category": { pl: "Kategoria", en: "Category" },
  "brief.category.decision": { pl: "Decyzja", en: "Decision" },
  "brief.category.project": { pl: "Projekt", en: "Project" },
  "brief.category.dream": { pl: "Marzenie", en: "Dream" },
  "brief.category.pattern": { pl: "Schemat", en: "Pattern" },
  "brief.aggressive.title": {
    pl: "Tryb agresywny (Przełamywanie schematów)",
    en: "Aggressive mode (Break the pattern)",
  },
  "brief.aggressive.hint": {
    pl: "Wymusza tryb",
    en: "Forces the",
  },
  "brief.aggressive.hint_after": {
    pl: "niezależnie od wyboru w pasku",
    en: "mode regardless of the sidebar selection",
  },
  "brief.aggressive.code": { pl: "schematy", en: "patterns" },
  "brief.btn.start": { pl: "Rozpocznij debatę Rady", en: "Start Council debate" },
  "brief.btn.running": { pl: "Debata trwa...", en: "Debate in progress..." },

  // ModeSidebar
  "mode.dreams.label": { pl: "Marzenia", en: "Dreams" },
  "mode.dreams.hint": {
    pl: "Rozszerz wizję, zanim ją skompresujesz",
    en: "Expand the vision before compressing it",
  },
  "mode.daily.label": { pl: "Codzienny", en: "Daily" },
  "mode.daily.hint": {
    pl: "~5 min check-in z pytaniem dnia, 4 lekkie głosy — bez destylacji LLM marzenia (taniej).",
    en: "~5 min check-in with today's question, four light voices — skips dream LLM distillation (lower cost).",
  },
  "mode.patterns.label": {
    pl: "Przełamywanie schematów",
    en: "Break the pattern",
  },
  "mode.patterns.hint": {
    pl: "Szow i Deega mocniej konfrontują ścieżki ucieczki",
    en: "Szow and Deega confront escape routes harder",
  },
  "mode.full.label": { pl: "Pełna Rada", en: "Full Council" },
  "mode.full.hint": { pl: "Wszystkie 9 perspektyw", en: "All 9 perspectives" },
  "mode.title": { pl: "Tryb Rady", en: "Council Mode" },

  // DebateHistory
  "history.title": { pl: "Historia", en: "History" },
  "history.search_placeholder": {
    pl: "Szukaj w briefie, syntezie, głosach…",
    en: "Search brief, synthesis, voices…",
  },
  "history.empty": { pl: "Brak zapisanych debat.", en: "No saved debates yet." },
  "history.no_history": { pl: "Brak historii", en: "No history" },

  // AgentCard
  "agent.waiting": { pl: "Oczekuje...", en: "Waiting..." },
  "agent.go_deeper": { pl: "Pogłębij", en: "Go deeper" },
  "agent.collapse": { pl: "Zwiń", en: "Collapse" },
  "agent.analyzing": { pl: "Analizuje", en: "Analyzing" },
  "agent.speaking": { pl: "Mówi", en: "Speaking" },
  "agent.fallback_role": { pl: "agent", en: "agent" },
  "agent.role.Relacjan": {
    pl: "relacje i zaufanie",
    en: "relationships & trust",
  },
  "agent.role.Kogit": { pl: "logika systemów", en: "systems logic" },
  "agent.role.Emojy": {
    pl: "ciało emocjonalne i somatyka",
    en: "emotional body & somatics",
  },
  "agent.role.Deega": { pl: "głęboka diagnoza", en: "deep diagnosis" },
  "agent.role.Smaty": {
    pl: "ciało, rytm, ugruntowanie",
    en: "body, rhythm, grounding",
  },
  "agent.role.Szow": {
    pl: "cień — bezkompromisowa prawda",
    en: "shadow — uncompromising truth",
  },
  "agent.role.Tai": { pl: "perspektywa czasu", en: "time perspective" },
  "agent.role.Obver": { pl: "obiektywna ocena", en: "objective assessment" },
  "agent.role.Kidi": { pl: "kreatywność i zabawa", en: "creativity & play" },

  // FA2 (business) role overrides — shown when councilMode === "fa2"
  "agent.role.fa2.Emojy": { pl: "trendy i sygnały popytu", en: "trends & demand signals" },
  "agent.role.fa2.Smaty": { pl: "operacje i finanse", en: "operations & finance" },
  "agent.role.fa2.Deega": { pl: "diagnoza i konkurencja", en: "competition & diagnosis" },
  "agent.role.fa2.Kidi": { pl: "innowacja i nisze", en: "innovation & niches" },

  // Lexical tension (backend + TensionMeter)
  "tensions.title": {
    pl: "Monitor napięć (heurystyka leksykalna)",
    en: "Tension monitor (lexical heuristic)",
  },
  "tensions.hint": {
    pl: "Wyższa wartość oznacza mniejsze pokrycie słownictwa — sygnał dla syntezy Syeza, nie „obiektywna prawda.",
    en: "A higher value means less word overlap between the pair — a signal for Syez's synthesis, not an \"objective truth\".",
  },

  "tensionmeter.title": { pl: "Sieć napięć", en: "Tension network" },
  "tensionmeter.hint": {
    pl: "Najedź na krawędź — zobaczysz opis pary (heurystyka jak w backendzie).",
    en: "Hover an edge to read the pair note (same heuristic as the backend).",
  },
  "tensionmeter.why.high": {
    pl: "wysokie napięcie leksykalne — konfrontacja sensów",
    en: "high lexical tension — colliding meanings",
  },
  "tensionmeter.why.mid": {
    pl: "napięcie twórcze — różne wektory, wspólny temat",
    en: "creative tension — different vectors, shared topic",
  },
  "tensionmeter.why.low": {
    pl: "niższe napięcie — podobne słownictwo (nie = zgoda)",
    en: "lower tension — similar vocabulary (not agreement)",
  },
  "tensionmeter.legend.high": { pl: "wysoki konflikt", en: "high clash" },
  "tensionmeter.legend.mid": { pl: "twórcze", en: "creative" },
  "tensionmeter.legend.low": { pl: "zbliżone słowa", en: "lexical overlap" },

  "commitments.timeline.title": { pl: "Oś zobowiązań", en: "Commitments" },
  "commitments.timeline.empty": { pl: "Brak zapisów dla tego projektu.", en: "No rows for this project." },
  "commitments.timeline.note_ph": { pl: "Dowód (tekst)", en: "Evidence (text)" },
  "commitments.timeline.url_ph": { pl: "Link (opcjonalnie)", en: "Link (optional)" },
  "commitments.timeline.check": { pl: "Odhacz", en: "Check off" },

  // SyezPanel
  "syez.mirror": { pl: "lustro Rady", en: "mirror of the Council" },
  "syez.status.waiting_council": {
    pl: "Czekam na głosy Rady...",
    en: "Waiting for the Council's voices...",
  },
  "syez.status.gathering": {
    pl: "Zbieram perspektywy przed syntezą...",
    en: "Gathering perspectives before synthesis...",
  },
  "syez.status.integrating": {
    pl: "Łączę 9 głosów w jedną narrację...",
    en: "Integrating 9 voices into one narrative...",
  },
  "syez.status.done": {
    pl: "Synteza gotowa — struktura, diagram Mermaid i pytania w treści.",
    en: "Synthesis ready — structure (legacy JSON), Mermaid diagram, and questions inline.",
  },
  "syez.btn.export_md": { pl: "Eksport Markdown", en: "Export Markdown" },
  "syez.btn.download_pdf": { pl: "Pobierz PDF", en: "Download PDF" },
  "syez.btn.print_pdf": { pl: "PDF (drukuj)", en: "PDF (print)" },
  "syez.section.insights": {
    pl: "Wnioski — 9 kart",
    en: "Insights — 9 cards",
  },
  "syez.section.tensions": { pl: "Napięcia", en: "Tensions" },
  "syez.section.recommendations": { pl: "Rekomendacje", en: "Recommendations" },
  "syez.section.open_questions": { pl: "Pytania otwarte", en: "Open questions" },
  "syez.section.action_steps": {
    pl: "Kroki działania — zobowiązanie",
    en: "Action steps — commitment",
  },
  "syez.action.due": { pl: "Termin", en: "Due" },
  "syez.action.priority": { pl: "priorytet", en: "priority" },
  "syez.btn.committing": { pl: "Zapisuję...", en: "Saving..." },
  "syez.btn.commit": { pl: "Zobowiązuję się", en: "I commit" },
  "syez.detected_questions": {
    pl: "Wykryte pytania otwarte",
    en: "Detected open questions",
  },
  "syez.empty_placeholder": {
    pl: "Pełna synteza pojawi się tutaj w trakcie strumieniowania.",
    en: "The full synthesis text will appear here as it streams in.",
  },
  "syez.continue.label": {
    pl: "Kontynuuj wątek po tej debacie",
    en: "Continue the thread after this debate",
  },
  "syez.continue.placeholder": {
    pl: "Co dalej? Minimum pięć słów — nowe pytanie albo doprecyzowanie dla Rady.",
    en: "What next? At least five words — a new question or clarification for the Council.",
  },
  "syez.continue.btn_starting": { pl: "Startuję...", en: "Starting..." },
  "syez.continue.btn": { pl: "Nowa runda Rady", en: "New Council round" },
  "syez.continue.min_words": {
    pl: "Kontynuacja: minimum pięć słów (jak w nowym briefie).",
    en: "Continuation: minimum five words (same rule as a new brief).",
  },
  "syez.continue.error": { pl: "Błąd kontynuacji", en: "Continuation error" },
  "syez.commit.no_debate": {
    pl: "Brak powiązania z debatą — zapis działa po zakończonej sesji.",
    en: "No debate link — saving works only after a finished session.",
  },
  "syez.commit.prefix": { pl: "Zobowiązuję się do", en: "I commit to" },
  "syez.commit.error_fallback": { pl: "Błąd zapisu", en: "Save error" },
  "syez.force_commit.title": {
    pl: "Zobowiązanie (siła cienia)",
    en: "Commitment (shadow weight)",
  },
  "syez.force_commit.lead": {
    pl: "Bez cichego znikania — zapis trafia do projektu i uruchamia follow-up w trybie schematów.",
    en: "No silent vanishing — saved to your project; pattern mode schedules follow-up.",
  },
  "syez.force_commit.placeholder": {
    pl: "Konkret, który możesz dowieść za 72h…",
    en: "Something you can prove within 72h…",
  },
  "syez.force_commit.btn": {
    pl: "Zobowiązuję się teraz",
    en: "I commit now",
  },
  "syez.force_commit.min": {
    pl: "Minimum trzy znaki.",
    en: "At least three characters.",
  },
  "dreams.col.dream": { pl: "Marzenie", en: "Dream" },
  "dreams.col.progress": { pl: "Postęp", en: "Progress" },
  "dreams.col.next": { pl: "Następny ruch", en: "Next move" },
  "dreams.open_commitments": { pl: "otwarte zobowiązania", en: "open commitments" },
  "dreams.next_followup": { pl: "najbliższy follow-up", en: "nearest follow-up" },
  "dreams.stuck.banner": {
    pl: "AKSJOMAT 2: projekt utknął — nie ma stanu „porzucony”, tylko domknięcie albo świadoma archiwizacja (≥50 znaków).",
    en: "AXIOM 2: project is stuck — there is no “abandoned”, only completion or conscious archive (≥50 chars).",
  },

  // Manifest (#15)
  "manifest.title": {
    pl: "Czym to nie jest — krótkie pozycjonowanie",
    en: "What this is NOT — quick positioning",
  },
  "manifest.body": {
    pl:
      "To nie jest kolejny czat „zadaj pytanie AI” bez struktury — to debata 9 nazwanych perspektyw.\n\n" +
      "To nie jest zamiennik terapii klinicznej ani superwizji psychologicznej.\n\n" +
      "To nie jest jeden głos-asystent — to zestaw nazwanych perspektyw i lustro syntezy (Syez).\n\n" +
      "To nie obiecuje „prawdy obiektywnej” — monitor napięć to heurystyka leksykalna, nie psychometria.\n\n" +
      "🔒 Prywatność: twój brief nie trafia do treningu Anthropic (korzystamy z API production, " +
      "nie z interfejsu claude.ai). Dane sesji żyją lokalnie w SQLite na twoim urządzeniu. " +
      "Żadnej chmury danych bez twojej zgody.",
    en:
      "This is not another \"ask the AI\" chat without structure — it's a debate of 9 named perspectives.\n\n" +
      "This is not a substitute for clinical therapy or psychological supervision.\n\n" +
      "This is not a single assistant voice — it's a set of named perspectives plus Syez as mirror/synthesis.\n\n" +
      "It does not promise \"objective truth\" — the tension monitor is a lexical heuristic, not psychometrics.\n\n" +
      "🔒 Privacy: your brief does not go into Anthropic training (we use the production API, " +
      "not the claude.ai interface). Session data lives locally in SQLite on your device. " +
      "No data cloud without your consent.",
  },

  // Onboarding + szablony (#1)
  "brief.onboarding.title": {
    pl: "Start w 60 sekund",
    en: "Start in 60 seconds",
  },
  "brief.onboarding.body": {
    pl: "Wybierz gotowy brief albo dyktuj głosem — uruchom pierwszą debatę zanim „wrócisz do ChatGPT”.",
    en: "Pick a starter brief or dictate by voice — run your first debate before you \"snap back to ChatGPT\".",
  },
  "brief.onboarding.dismiss": { pl: "Rozumiem, ukryj", en: "Got it, hide" },
  "brief.quick.title": { pl: "Gotowe briefy (1 klik)", en: "Starter briefs (1 click)" },
  "brief.tpl.quit": {
    pl:
      "Właśnie odszedłem z pracy albo poważnie rozważam odejście. Czuję ulgę i strach jednocześnie i potrzebuję perspektywy Rady zanim zrobię kolejny ruch.",
    en:
      "I just left my job or I'm seriously considering quitting. I feel relief and fear at once and I want the Council's perspectives before my next move.",
  },
  "brief.tpl.quit.label": { pl: "Zwolnienie / przejście", en: "Job exit / transition" },
  "brief.tpl.dream": {
    pl:
      "Mam konkretne marzenie lub wizję życia i chcę rozłożyć je na filary, kamienie milowe oraz jeden najmniejszy pierwszy krok którego nie porzucę po tygodniu.",
    en:
      "I have a concrete dream or life vision and I want it broken into pillars, milestones, and one smallest first step I won't abandon after a week.",
  },
  "brief.tpl.dream.label": { pl: "Marzenie do rozłożenia", en: "Dream to unfold" },
  "brief.tpl.pattern": {
    pl:
      "Widzę że powtarzam ten sam schemat blokady lub ucieczki i chcę nazwać marzenie które ten schemat zasłania oraz najmniejszy przełom następnych 24 godzin.",
    en:
      "I keep repeating the same blockage or escape pattern and I want to name the dream it hides plus the smallest breakthrough for the next 24 hours.",
  },
  "brief.tpl.pattern.label": { pl: "Schemat / blokada", en: "Pattern / blockage" },

  // Portrety agentów (#4) — kim jest i dlaczego boli
  "agent.bio.Relacjan": {
    pl: "Pilnuje żebyś nie poszedł dalej bez sprawdzenia co ten ruch zrobi ludziom wokół ciebie — i tobie samemu. Boli, bo każe patrzeć na relacje które wolałbyś zignorować.",
    en: "Makes sure you don't move forward without checking what it will do to the people around you — and yourself. Hurts because it forces you to look at relationships you'd rather ignore.",
  },
  "agent.bio.Kogit": {
    pl: "Rozkłada każdy pomysł na trzy niezależne moduły i sprawdza który z nich to podzbiór innego. Boli, bo obnażа iluzje i niespójne założenia.",
    en: "Breaks every idea into three independent modules and checks which ones are subsets of each other. Hurts because it exposes illusions and inconsistent assumptions.",
  },
  "agent.bio.Emojy": {
    pl: "Mówi co rzeczywiście czujesz — nie co chcesz czuć. Boli, bo pomija racjonalizacje i dociera do sedna emocji które napędza decyzję.",
    en: "Says what you actually feel — not what you want to feel. Hurts because it bypasses rationalizations and reaches the emotion actually driving the decision.",
  },
  "agent.bio.Deega": {
    pl: "Nazywa to co nieuświadomione — wzorce starsze niż ten projekt, blokady których nie wybierałeś, lojalności które cię trzymają. Boli, bo pyta: co tu naprawdę siedzi i od kiedy?",
    en: "Names what is unconscious — patterns older than this project, blockages you didn't choose, loyalties holding you in place. Hurts because it asks: what's really sitting here, and since when?",
  },
  "agent.bio.Smaty": {
    pl: "Słucha ciała — gdzie siedzi napięcie, gdzie jest luz, gdzie coś blokuje oddech. Boli, bo ciało odpowiada wcześniej niż głowa i nie daje się zagadać.",
    en: "Listens to the body — where tension lives, where there's ease, where something blocks the breath. Hurts because the body answers faster than the mind and can't be talked out of it.",
  },
  "agent.bio.Szow": {
    pl: "Jest głosem cienia — mówi prawdę której nie chcesz słyszeć o tym dlaczego tak naprawdę nie ruszasz dalej. Boli zawsze.",
    en: "Speaks as the shadow — says the truth you don't want to hear about why you're really not moving forward. Always hurts.",
  },
  "agent.bio.Tai": {
    pl: "Pyta: jak będziesz patrzeć na tę decyzję za rok, pięć lat, dekadę. Boli, bo ujawnia co jest chwilowym impulsem a co trwałym kierunkiem.",
    en: "Asks: how will you look at this decision in a year, five years, a decade. Hurts because it reveals what's a momentary impulse versus a lasting direction.",
  },
  "agent.bio.Obver": {
    pl: "Obserwuje z lotu ptaka i mówi co widzi bez emocji — dopóki wszyscy inni są w środku sytuacji. Boli, bo jego chłód jest precyzyjny.",
    en: "Observes from a bird's-eye view and states what it sees without emotion — while everyone else is inside the situation. Hurts because its coldness is precise.",
  },
  "agent.bio.Kidi": {
    pl: "Pyta czemu w ogóle ma to być aplikacja a nie arkusz Google z jednym przyciskiem. Boli, bo czasem ma rację i to rujnuje cały plan.",
    en: "Asks why this needs to be an app at all and not a Google Sheet with one button. Hurts because sometimes it's right and that ruins the whole plan.",
  },

  // Koszt debaty (#14)
  "syez.debate_cost": { pl: "ta debata: ~", en: "this debate: ~" },
  "syez.debate_cost_eur": { pl: " EUR", en: " EUR" },

  // Voice (#12)
  "brief.voice.idle": { pl: "Dyktuj brief", en: "Dictate brief" },
  "brief.voice.active": { pl: "Słucham…", en: "Listening…" },
  "brief.voice.unsupported": {
    pl: "Ta przeglądarka nie wspiera rozpoznawania mowy (Web Speech API).",
    en: "This browser doesn't support speech recognition (Web Speech API).",
  },
};

export function t(lang: Lang, key: string): string {
  return DICT[key]?.[lang] ?? key;
}

interface LangCtxValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (k: string) => string;
}

const LangCtx = createContext<LangCtxValue>({
  lang: "pl",
  setLang: () => {},
  t: (k) => k,
});

const STORAGE_KEY = "aw-lang";

function readInitialLang(): Lang {
  if (typeof window === "undefined") return "pl";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "pl" || stored === "en") return stored;
  } catch {
    /* localStorage może być zablokowane (Safari w trybie prywatnym) */
  }
  const navLang = (
    typeof navigator !== "undefined" && navigator.language
      ? navigator.language
      : ""
  ).toLowerCase();
  return navLang.startsWith("pl") ? "pl" : "en";
}

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => readInitialLang());

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* ignorujemy — nie wpływa to na działanie aplikacji */
    }
    if (typeof document !== "undefined") {
      document.documentElement.lang = lang;
      document.title =
        lang === "pl" ? "Architekt Wolności: Wielogłos" : "Freedom Architect: Polyphony";
    }
  }, [lang]);

  const value = useMemo<LangCtxValue>(
    () => ({
      lang,
      setLang: setLangState,
      t: (k: string) => t(lang, k),
    }),
    [lang],
  );

  return <LangCtx.Provider value={value}>{children}</LangCtx.Provider>;
}

export function useLang() {
  return useContext(LangCtx);
}
