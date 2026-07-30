/**
 * Lekki i18n dla Architekta Wolności / Freedom Architect.
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
  "app.brand": { pl: "Architekt Wolności", en: "Freedom Architect" },
  "app.title.supervisory": { pl: "Rada", en: "Supervisory" },
  "app.title.council": { pl: "Nadzorcza", en: "Council" },
  "app.status.idle": { pl: "Gotowy", en: "Ready" },
  "app.status.agents_speaking": { pl: "Debata w toku", en: "Debate in progress" },
  "app.status.synthesizing": { pl: "Syez syntetyzuje", en: "Syez synthesizing" },
  "app.status.done": { pl: "Debata zakończona", en: "Debate finished" },
  "app.status.error": { pl: "Błąd", en: "Error" },
  "app.status.safety_halt": { pl: "Wstrzymano — bezpieczeństwo", en: "Stopped — safety" },
  "safety.halt.title": {
    pl: "Wsparcie w kryzysie",
    en: "Crisis support",
  },
  "safety.halt.helpline": {
    pl: "Jeśli jesteś w kryzysie lub masz myśli o odebraniu sobie życia, zadzwoń pod numer",
    en: "If you are in crisis or having thoughts of self-harm, call",
  },
  "safety.halt.footer": {
    pl: "Debata nie została uruchomiona. Zdrowie jest ważniejsze niż postęp projektu.",
    en: "The debate did not start. Your wellbeing matters more than project progress.",
  },
  "app.btn.reset": { pl: "Resetuj", en: "Reset" },
  "app.mobile_mode_label": { pl: "Tryb (skrót mobilny)", en: "Mode (mobile shortcut)" },
  "app.workspace.seal": {
    pl: "9 perspektyw · debata, nie czat",
    en: "9 perspectives · debate, not chat",
  },
  "app.error.unknown": {
    pl: "Nieznany błąd. Sprawdź czy backend działa na porcie 8000.",
    en: "Unknown error. Check whether the backend is running on port 8000.",
  },

  "setup.title": { pl: "Połączenie lokalne", en: "Local connection" },
  "setup.intro": {
    pl: "Ustaw adres backendu FastAPI i sprawdź endpoint /health. Klucz Anthropic wpisz w polu BYOK poniżej — trafia do keychaina i jest wysyłany per żądanie, serwer go nie zapisuje. Gdy backend ma ustawione ARCHITEKT_API_KEY, wpisz ten sam token w osobnym polu niżej (albo VITE_ARCHITEKT_API_KEY przy buildzie).",
    en: "Set the FastAPI backend URL and check /health. Enter your Anthropic key in the BYOK field below — it goes to the keychain and is sent per request; the server never stores it. If the server has ARCHITEKT_API_KEY set, paste the same bearer token in the separate field below (or use VITE_ARCHITEKT_API_KEY at build time).",
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
    pl: "Klucz Anthropic (BYOK) i klucz HTTP API to dwa różne sekrety — patrz opisy przy odpowiednich polach wyżej. Żaden z nich nie trafia do repozytorium ani logów.",
    en: "The Anthropic key (BYOK) and the HTTP API key are two different secrets — see the notes under each field above. Neither is written to the repository or to logs.",
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
  "setup.tab_connection": { pl: "Połączenie", en: "Connection" },
  "setup.tab_privacy": { pl: "Prywatność i konto", en: "Privacy & account" },
  "setup.founders_hint": {
    pl: "Founders BYOK: zarejestruj konto (JWT), aby eksportować dane i korzystać z RODO w aplikacji. Klucz ARCHITEKT_API_KEY to tryb zaawansowany bez per-user izolacji.",
    en: "Founders BYOK: register (JWT) to export data and use in-app privacy tools. ARCHITEKT_API_KEY is advanced mode without per-user isolation.",
  },
  "setup.llm_key_label": {
    pl: "Klucz Anthropic (BYOK)",
    en: "Anthropic API key (BYOK)",
  },
  "setup.llm_key_placeholder": {
    pl: "sk-ant-…",
    en: "sk-ant-…",
  },
  "setup.llm_key_note": {
    pl: "Klucz jest przechowywany lokalnie (keychain w aplikacji desktopowej) i wysyłany per żądanie — serwer go nie zapisuje.",
    en: "The key is stored locally (keychain on desktop) and sent per request — the server never persists it.",
  },
  "setup.llm_key_clear": {
    pl: "Usuń klucz Anthropic",
    en: "Remove Anthropic key",
  },
  "setup.llm_key_saved": {
    pl: "Klucz Anthropic zapisany lokalnie.",
    en: "Anthropic key saved locally.",
  },
  "setup.llm_key_masked": {
    pl: "Zapisany klucz: {mask}",
    en: "Saved key: {mask}",
  },

  "llm_key.missing_gate": {
    pl: "Brak klucza Anthropic — dodaj go w Ustawieniach (Połączenie), aby uruchomić debatę.",
    en: "No Anthropic key — add it in Settings (Connection) to start a debate.",
  },
  "llm_key.missing_stream": {
    pl: "Brak klucza LLM — dodaj swój klucz w Ustawieniach.",
    en: "Missing LLM key — add your key in Settings.",
  },
  "llm_key.invalid": {
    pl: "Klucz Anthropic został odrzucony — sprawdź go i wpisz ponownie w Ustawieniach.",
    en: "Anthropic key was rejected — check it and re-enter in Settings.",
  },
  "llm_key.open_settings": {
    pl: "Otwórz Ustawienia",
    en: "Open Settings",
  },

  "account.intro": {
    pl: "Eksportuj wszystkie dane tenanta (debates, marzenia, zobowiązania…) lub trwale usuń konto z lokalnej bazy.",
    en: "Export all tenant data (debates, dreams, commitments…) or permanently delete your account from the local database.",
  },
  "account.privacy_link": { pl: "Polityka prywatności", en: "Privacy policy" },
  "account.export_btn": { pl: "Pobierz eksport JSON", en: "Download JSON export" },
  "account.exporting": { pl: "Eksportuję…", en: "Exporting…" },
  "account.export_ok": { pl: "Eksport pobrany.", en: "Export downloaded." },
  "account.delete_warn": {
    pl: "Usunięcie jest nieodwracalne na tej instalacji.",
    en: "Deletion is irreversible on this installation.",
  },
  "account.delete_label": {
    pl: "Wpisz dokładnie, aby potwierdzić:",
    en: "Type exactly to confirm:",
  },
  "account.delete_btn": { pl: "Usuń moje konto", en: "Delete my account" },
  "account.deleting": { pl: "Usuwam…", en: "Deleting…" },
  "account.delete_ok": {
    pl: "Konto usunięte. Wylogowano.",
    en: "Account deleted. Signed out.",
  },
  "account.delete_confirm_mismatch": {
    pl: "Niepoprawny tekst potwierdzenia.",
    en: "Confirmation text does not match.",
  },
  "account.demo_blocked": {
    pl: "Eksport i usuwanie konta są niedostępne w wersji demo.",
    en: "Export and account deletion are not available in demo mode.",
  },
  "account.jwt_required": {
    pl: "Zaloguj się lub zarejestruj, aby zarządzać danymi (POST /auth/login).",
    en: "Sign in or register to manage your data (POST /auth/login).",
  },
  "account.auth_intro": {
    pl: "Zaloguj się lub załóż konto (JWT per-user), aby eksportować lub usuwać swoje dane. To bezpieczna ścieżka z izolacją tenanta.",
    en: "Sign in or create an account (per-user JWT) to export or delete your data. This is the safe, tenant-isolated path.",
  },
  "account.auth_tab_login": { pl: "Logowanie", en: "Login" },
  "account.auth_tab_register": { pl: "Rejestracja", en: "Register" },
  "account.auth_username": { pl: "Login", en: "Username" },
  "account.auth_password": { pl: "Hasło", en: "Password" },
  "account.auth_display_name": { pl: "Imię (opcjonalnie)", en: "Name (optional)" },
  "account.auth_btn_login": { pl: "Zaloguj", en: "Log in" },
  "account.auth_btn_register": { pl: "Zarejestruj", en: "Register" },
  "account.auth_busy": { pl: "Łączę…", en: "Connecting…" },
  "account.auth_pw_hint_register": {
    pl: "Hasło: min. 6 znaków.",
    en: "Password: min. 6 characters.",
  },

  // Sieć / fetch (useDebate, szczególnie Safari „Load failed”)
  "debate.network.unreachable": {
    pl:
      "Nie udało się połączyć z serwerem (brak odpowiedzi). Uruchom backend: uvicorn main:app --host 127.0.0.1 --port 8000 (z katalogu głównego repozytorium). Przy npm run dev Vite przekieruje /health itd. na :8000 — oba procesy muszą działać. Aplikacja desktopowa (build) domyślnie woła http://127.0.0.1:8000; w sieci ustaw VITE_API_URL lub Połączenie w UI.",
    en:
      "Could not reach the server (no response). Start the backend: uvicorn main:app --host 127.0.0.1 --port 8000 (from the repo root). With npm run dev, Vite proxies /health etc. to :8000 — both must be running. The desktop build defaults to http://127.0.0.1:8000; for hosted web set VITE_API_URL or use Connection in the UI.",
  },
  "debate.network.unreachable_desktop": {
    pl:
      "Backend jeszcze nie odpowiada. Poczekaj kilka sekund po starcie aplikacji i spróbuj ponownie. Jeśli problem się powtarza, sprawdź logi: macOS ~/Library/Application Support/ArchitektWolnosci/logs/backend-stderr.log, Windows %APPDATA%\\ArchitektWolnosci\\logs\\backend-stderr.log — i zrestartuj aplikację.",
    en:
      "The backend isn't responding yet. Wait a few seconds after app startup and try again. If this persists, check the logs: macOS ~/Library/Application Support/ArchitektWolnosci/logs/backend-stderr.log, Windows %APPDATA%\\ArchitektWolnosci\\logs\\backend-stderr.log — then restart the app.",
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
  // Auth: sesja wygasła (401 na starcie debaty). Rozróżniamy to od martwego
  // backendu — inaczej wygasły token pokazywał się jako „backend nie odpowiada".
  "debate.auth.expired": {
    pl: "Twoja sesja wygasła — zaloguj się ponownie, aby uruchomić Radę.",
    en: "Your session has expired — sign in again to start the Council.",
  },
  // Sesja wygasła W TRAKCIE strumienia debaty (nie na starcie) — inny komunikat,
  // bo część głosów Rady user już widzi na ekranie i nie chcemy udawać, że nie.
  "debate.auth.expired_mid_stream": {
    pl: "Sesja wygasła w trakcie debaty — zaloguj się ponownie. Głosy, które już się pojawiły, zostają na ekranie.",
    en: "Your session expired mid-debate — sign in again. The voices already on screen stay.",
  },

  // ── Stan backendu z launchera Tauri (src-tauri/src/lib.rs) ──────────────
  // Każdy status ma WŁASNY komunikat z instrukcją. Wcześniej wszystkie
  // wyglądały tak samo: „nie udało się połączyć z serwerem".
  "backend.status.starting": {
    pl: "Uruchamiam silnik Rady… Pierwsze uruchomienie po instalacji może potrwać kilkanaście sekund.",
    en: "Starting the Council engine… The first launch after install can take a dozen seconds.",
  },
  "backend.status.pending": {
    pl: "Sprawdzam stan silnika Rady…",
    en: "Checking the Council engine…",
  },
  "backend.status.port_blocked": {
    pl: "Port 8000 jest zajęty przez inny program, więc silnik Rady nie mógł wystartować. Zamknij program używający tego portu (macOS: lsof -i :8000, Windows: netstat -ano | findstr :8000) i uruchom aplikację ponownie.",
    en: "Port 8000 is taken by another program, so the Council engine could not start. Close whatever uses that port (macOS: lsof -i :8000, Windows: netstat -ano | findstr :8000) and restart the app.",
  },
  "backend.status.spawn_failed": {
    pl: "Nie udało się uruchomić silnika Rady — w paczce brakuje zbudowanego backendu. To błąd tej wersji aplikacji, nie Twojej konfiguracji: zgłoś go razem z plikami logów.",
    en: "The Council engine could not be launched — this build is missing its backend binary. That's a defect in this app version, not your setup: report it together with the log files.",
  },
  "backend.status.unreachable": {
    pl: "Silnik Rady wystartował, ale nie odpowiada. Zrestartuj aplikację; jeśli to się powtarza, dołącz do zgłoszenia plik backend-stderr.log.",
    en: "The Council engine started but isn't responding. Restart the app; if it repeats, attach backend-stderr.log to your report.",
  },
  "backend.status.ready": { pl: "Silnik Rady gotowy.", en: "Council engine ready." },
  "backend.status.reused_existing": {
    pl: "Używam już działającego silnika Rady.",
    en: "Using an already running Council engine.",
  },
  "backend.status.autospawn_disabled": {
    pl: "Automatyczny start silnika jest wyłączony (AW_DISABLE_AUTOSPAWN).",
    en: "Automatic engine startup is disabled (AW_DISABLE_AUTOSPAWN).",
  },
  "backend.status.logs_at": { pl: "Logi:", en: "Logs:" },
  "app.section.council": {
    pl: "Rada Nadzorcza — perspektywy",
    en: "Supervisory Council — perspectives",
  },
  "app.section.synthesis": { pl: "Synteza (Syez)", en: "Synthesis (Syez)" },
  "thread.prior_turn": { pl: "Tura", en: "Turn" },
  "thread.your_followup": { pl: "Ty (kontynuacja)", en: "You (follow-up)" },
  "thread.your_brief": { pl: "Twój brief", en: "Your brief" },
  "thread.expand": { pl: "Rozwiń", en: "Expand" },
  "thread.collapse": { pl: "Zwiń", en: "Collapse" },
  "thread.prior_summary": {
    pl: "{n} perspektyw{synthesis}",
    en: "{n} perspectives{synthesis}",
  },
  "thread.prior_has_synthesis": {
    pl: " · synteza gotowa",
    en: " · synthesis ready",
  },
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

  "mode.fa2.title": { pl: "Tryb FA2 (biznes)", en: "FA2 mode (business)" },
  "mode.fa2.dreams.label": { pl: "Fundraising / wizja", en: "Fundraising / vision" },
  "mode.fa2.dreams.hint": {
    pl: "Większy nacisk na ekonomię, ryzyko i narrację dla inwestorów.",
    en: "Stronger focus on economics, risk, and investor-facing narrative.",
  },
  "mode.fa2.daily.label": { pl: "Strategia (lekka)", en: "Strategy (light)" },
  "mode.fa2.daily.hint": {
    pl: "Pięciu analityków — szybsza runda, mniej szerokie pokrycie.",
    en: "Five analysts — faster round, narrower coverage.",
  },
  "mode.fa2.patterns.label": { pl: "Pivot i ryzyko", en: "Pivot & risk" },
  "mode.fa2.patterns.hint": {
    pl: "Tryb na zmianę kursu: klient, produkt, ekonomia, ryzyko.",
    en: "Course-correction mode: customer, product, economics, risk.",
  },
  "mode.fa2.full.label": { pl: "Pełna rada analityków", en: "Full analyst council" },
  "mode.fa2.full.hint": {
    pl: "Dziewięciu analityków biznesowych + Syez (lustro).",
    en: "Nine business analysts + Syez (mirror synthesis).",
  },

  // DebateHistory
  "history.title": { pl: "Moje Rady Nadzorcze", en: "My Supervisory Councils" },
  "history.search_placeholder": {
    pl: "Szukaj w briefie, syntezie, głosach…",
    en: "Search brief, synthesis, voices…",
  },
  "history.empty": {
    pl: "Twoja historia jest jeszcze pusta.",
    en: "Your history is still empty.",
  },
  "history.empty_hint": {
    pl: "Zadaj pierwsze pytanie Radzie w panelu obok — zakończona debata pojawi się tutaj.",
    en: "Ask the Council your first question in the panel — a finished debate will appear here.",
  },
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

  // Lexical tension (backend + TensionMeter)
  "tensions.title": {
    pl: "Monitor napięć (heurystyka leksykalna)",
    en: "Tension monitor (lexical heuristic)",
  },
  "tensions.hint": {
    pl: "Wyższa wartość oznacza mniejsze pokrycie słownictwa — sygnał dla syntezy Syeza, nie „obiektywna prawda.",
    en: "A higher value means less word overlap between the pair — a signal for Syez's synthesis, not an \"objective truth\".",
  },

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
  "syez.closing.title": {
    pl: "Domknięcie Rady",
    en: "Closing the Council",
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
  "syez.continue.unavailable": {
    pl: "Debata nie została zapisana — kontynuacja wątku niedostępna.",
    en: "Debate was not saved — thread continuation unavailable.",
  },
  "syez.new_debate.btn": { pl: "Nowa debata", en: "New debate" },
  "syez.commit.no_debate": {
    pl: "Brak powiązania z debatą — zapis działa po zakończonej sesji.",
    en: "No debate link — saving works only after a finished session.",
  },
  "syez.commit.prefix": { pl: "Zobowiązuję się do", en: "I commit to" },
  "syez.commit.error_fallback": { pl: "Błąd zapisu", en: "Save error" },
  "syez.force_commit.title": {
    pl: "Twoje zobowiązanie",
    en: "Your commitment",
  },
  "syez.force_commit.lead": {
    pl: "Jeden konkretny krok, który bierzesz z tej debaty. Zapisuje się w historii — bez cichego znikania.",
    en: "One concrete step you take from this debate. Saved to your history — no silent vanishing.",
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
  "brief.hero.title": {
    pl: "Jaki temat stawiasz przed Radą?",
    en: "What do you bring before the Council?",
  },
  "brief.hero.subtitle": {
    pl: "Opisz marzenie, decyzję lub wzorzec — w swoich słowach, bez skrótów.",
    en: "Describe a dream, decision, or pattern — in your own words, without shortcuts.",
  },
  "brief.chars.min_words": {
    pl: "Minimum 5 słów, aby rozpocząć debatę",
    en: "Minimum 5 words to start the debate",
  },
  "brief.chars.remaining": {
    pl: "pozostało znaków",
    en: "characters remaining",
  },
  "brief.tpl.quit": {
    pl:
      "Mam około trzech miesięcy poduszki finansowej i albo właśnie odszedłem z etatu, albo mam to zrobić w tym tygodniu. Czuję ulgę i panikę naraz. Boję się, że to ucieczka OD szefa, nie ruch DO czegoś własnego. Chcę, żeby Rada rozdzieliła te dwie rzeczy i dała mi jeden konkretny ruch na najbliższe 48 godzin, zanim podejmę decyzję pod wpływem emocji.",
    en:
      "I have roughly three months of savings and I've either just left my job or I'm about to this week. I feel relief and panic at once. I'm afraid this is escape FROM a boss, not a move TOWARD something of my own. I want the Council to separate the two and give me one concrete move for the next 48 hours, before I decide on emotion.",
  },
  "brief.tpl.quit.label": { pl: "Etat: zostać czy odejść", en: "Job: stay or leave" },
  "brief.tpl.dream": {
    pl:
      "Mam jedno marzenie, które wraca do mnie od lat, ale za każdym razem ginie pod codziennością i pracą zarobkową. Chcę je rozłożyć na trzy filary i kilka kamieni milowych, dostać najmniejszy pierwszy krok na dziś, którego nie porzucę po tygodniu, oraz usłyszeć od Rady wprost, co konkretnie zabija to marzenie za każdym razem, gdy się do niego zbliżam.",
    en:
      "I have one dream that's been coming back for years, but every time it dies under daily life and paid work. I want it broken into three pillars and a few milestones, the smallest first step for today that I won't abandon after a week, and to hear from the Council plainly what specifically kills this dream each time I get close to it.",
  },
  "brief.tpl.dream.label": { pl: "Marzenie, które ciągle ucieka", en: "The dream that keeps slipping" },
  "brief.tpl.pattern": {
    pl:
      "Już trzeci raz w tym roku rzucam coś na osiemdziesiąt procent i zaczynam nowy projekt od zera. Wmawiam sobie brak czasu albo że pomysł się wypalił, ale w środku wiem, że to coś innego. Chcę, żeby Rada nazwała, czego ten wzorzec naprawdę broni i czego boję się w samym momencie ukończenia, oraz dała mi jeden ruch na najbliższą godzinę, którego nie da się zracjonalizować.",
    en:
      "For the third time this year I'm abandoning something at eighty percent and starting a new project from scratch. I tell myself it's lack of time or that the idea burned out, but inside I know it's something else. I want the Council to name what this pattern actually protects and what I fear at the very moment of finishing, and give me one move for the next hour that can't be rationalized away.",
  },
  "brief.tpl.pattern.label": { pl: "Rzucam na 80% i uciekam", en: "I quit at 80% and run" },

  // Presety trybu Biznesowa (fa2) — konkretne dylematy, dane + scenariusze
  "brief.tpl.fa2_saas": {
    pl:
      "Prowadzę software house B2B, około 18 osób, 140k EUR miesięcznie z usług przy marży 22%. Mam działający prototyp produktu SaaS, ale zero płacących klientów. Pytanie: czy w najbliższych 6 miesiącach przesuwać 40% zespołu na produkt kosztem zdolności usługowej, czy budować go „z nadwyżki” bez ruszania core'u? Chcę scenariusze Base / Bull / Bear, realne ryzyka cash flow i jeden najmniejszy ruch na najbliższe 60 minut.",
    en:
      "I run a B2B software house, about 18 people, 140k EUR per month from services at a 22% margin. I have a working SaaS prototype but zero paying customers. The question: over the next 6 months, do I move 40% of the team onto the product at the cost of service capacity, or build it 'from the surplus' without touching the core? I want Base / Bull / Bear scenarios, real cash-flow risks, and one smallest move for the next 60 minutes.",
  },
  "brief.tpl.fa2_saas.label": { pl: "Usługi → produkt (SaaS)", en: "Services → product (SaaS)" },
  "brief.tpl.fa2_pricing": {
    pl:
      "Od trzech lat nie podniosłem cen, a koszty wzrosły o jakieś 20%. Boję się, że podwyżka odstraszy klientów, ale przy obecnych marżach ledwo wychodzę na swoje. Chcę, żeby Rada policzyła wpływ podwyżki o 10–15% w scenariuszach Base / Bull / Bear, nazwała realne ryzyko odejścia klientów i dała mi jeden konkretny ruch na ten tydzień — z jasnym triggerem decyzji.",
    en:
      "I haven't raised prices in three years while costs went up roughly 20%. I'm afraid a hike will scare customers off, but at current margins I'm barely breaking even. I want the Council to model the impact of a 10–15% increase across Base / Bull / Bear, name the real churn risk, and give me one concrete move for this week — with a clear decision trigger.",
  },
  "brief.tpl.fa2_pricing.label": { pl: "Podnieść ceny czy nie", en: "Raise prices or not" },
  "brief.tpl.fa2_gtm": {
    pl:
      "Mam gotowy produkt B2B i przyzwoity ruch organiczny, ale konwersja na płacących klientów jest bliska zeru. Nie wiem, czy to problem produktu, ceny, czy dotarcia. Chcę, żeby Rada postawiła diagnozę opartą na danych, wskazała najsłabsze ogniwo lejka (popyt / model / wykonalność) i dała mi jeden eksperyment do odpalenia w najbliższe 48 godzin.",
    en:
      "I have a finished B2B product and decent organic traffic, but conversion to paying customers is close to zero. I don't know whether it's a product, pricing, or reach problem. I want the Council to give a data-grounded diagnosis, name the weakest link in the funnel (demand / model / feasibility), and give me one experiment to run in the next 48 hours.",
  },
  "brief.tpl.fa2_gtm.label": { pl: "Zero płacących klientów", en: "Zero paying customers" },

  // ── Mój obraz (MojObrazPanel) ──
  "obraz.section": { pl: "Mój obraz", en: "My image" },
  "obraz.lead": {
    pl: "Żywy obraz z onboardingu. Możesz edytować odpowiedzi — Rada bierze je pod uwagę.",
    en: "A living image from onboarding. You can edit the answers — the Council takes them into account.",
  },
  "obraz.council_sees": { pl: "Obraz, który Rada widzi", en: "The image the Council sees" },
  "obraz.btn.distilling": { pl: "Destyluję…", en: "Distilling…" },
  "obraz.btn.refresh": { pl: "Odśwież", en: "Refresh" },
  "obraz.btn.synthesize": { pl: "Zsyntetyzuj", en: "Synthesize" },
  "obraz.empty": {
    pl: "Rada jeszcze nie złożyła Twojego obrazu z odpowiedzi. Kliknij „Zsyntetyzuj”, żeby zdestylować wysokosygnałowy ekstrakt.",
    en: "The Council hasn't assembled your image from the answers yet. Click “Synthesize” to distill a high-signal extract.",
  },
  "obraz.row.values": { pl: "Wartości", en: "Values" },
  "obraz.row.tensions": { pl: "Napięcia / cień", en: "Tensions / shadow" },
  "obraz.row.relations": { pl: "Relacje", en: "Relationships" },
  "obraz.row.patterns": { pl: "Wzorce", en: "Patterns" },
  "obraz.row.body": { pl: "Ciało", en: "Body" },
  "obraz.row.creativity": { pl: "Kreatywność", en: "Creativity" },
  "obraz.row.spirituality": { pl: "Duchowość", en: "Spirituality" },
  "obraz.row.need_now": { pl: "Potrzeba teraz", en: "Need now" },
  "obraz.version": { pl: "wersja", en: "version" },
  "obraz.btn.saving": { pl: "Zapisuję…", en: "Saving…" },
  "obraz.btn.save": { pl: "Zapisz obraz", en: "Save image" },
  "obraz.saved": { pl: "zapisano", en: "saved" },
  "obraz.redo": { pl: "Przejdź onboarding ponownie", en: "Redo onboarding" },
  "obraz.loading": { pl: "Wczytuję…", en: "Loading…" },
  "obraz.err.load": { pl: "Błąd wczytywania", en: "Load error" },
  "obraz.err.save": { pl: "Błąd zapisu", en: "Save error" },
  "obraz.err.synth": { pl: "Błąd syntezy", en: "Synthesis error" },

  // ── Onboarding modal + rytuał (PersonalRitualPanels) ──
  "onb.first_run": { pl: "Pierwsze uruchomienie", en: "First run" },
  "onb.later": { pl: "Później", en: "Later" },
  "onb.placeholder": {
    pl: "Odpowiedz w swoim tempie. Możesz pominąć.",
    en: "Answer at your own pace. You can skip.",
  },
  "onb.back": { pl: "← Wstecz", en: "← Back" },
  "onb.next": { pl: "Dalej →", en: "Next →" },
  "onb.finish": { pl: "Zakończ", en: "Finish" },
  "ritual.morning": { pl: "Rytuał poranny", en: "Morning ritual" },
  "ritual.evening": { pl: "Rytuał wieczorny", en: "Evening ritual" },

  // ── Feedback (FeedbackPanel) ──
  "fb.title": { pl: "Jak ci poszło?", en: "How did it go?" },
  "fb.subtitle": {
    pl: "Trzy krótkie pytania. Pomagasz mi domknąć system zanim wpuszczę więcej osób.",
    en: "Three short questions. You help me close the system before I let more people in.",
  },
  "fb.rating_label": { pl: "Ocena (1 = słabo, 5 = świetnie)", en: "Rating (1 = poor, 5 = great)" },
  "fb.worked_label": { pl: "Co realnie pomogło?", en: "What actually helped?" },
  "fb.worked_ph": {
    pl: "Pomijalne. Np. „synteza wskazała ruch do 60 min”.",
    en: "Optional. E.g. “the synthesis pointed to a 60-min move”.",
  },
  "fb.broke_label": { pl: "Co było mylące lub nie działało?", en: "What was confusing or didn't work?" },
  "fb.broke_ph": { pl: "Pomijalne. Konkret > ogólnik.", en: "Optional. Specifics > generalities." },
  "fb.err_rating": { pl: "Wybierz ocenę 1–5.", en: "Pick a rating from 1–5." },
  "fb.sending": { pl: "Wysyłam…", en: "Sending…" },
  "fb.send": { pl: "Wyślij", en: "Send" },

  // ── Brakujące klucze brief.* (pokazywały się jako surowe klucze / brak EN) ──
  "brief.btn.start_fa2": { pl: "Zwołaj Radę Analityczną", en: "Convene the Analyst Council" },
  "brief.btn.start_schematy": { pl: "Konfrontuj schemat", en: "Confront the pattern" },
  "brief.btn.start_codzienny": { pl: "Zwołaj Radę", en: "Convene the Council" },
  "brief.advanced.show": { pl: "Więcej opcji", en: "More options" },
  "brief.advanced.hide": { pl: "Mniej opcji", en: "Fewer options" },

  // ── Nawigacja / tytuły paneli bocznych ──
  "nav.brief": { pl: "Brief / Debata", en: "Brief / Debate" },
  "nav.dreams": { pl: "Marzenia i projekty", en: "Dreams & projects" },
  "nav.notifications": { pl: "Powiadomienia i zobowiązania", en: "Notifications & commitments" },
  "nav.notifications_short": { pl: "Powiadomienia", en: "Notifications" },
  "nav.history": { pl: "Historia debat", en: "Debate history" },
  "nav.settings": { pl: "Ustawienia", en: "Settings" },

  // ── Tryby debaty (label w historii) ──
  "mode.pelna": { pl: "Pełna", en: "Full" },
  "mode.marzen": { pl: "Marzeń", en: "Dream" },
  "mode.schematy": { pl: "Schematy", en: "Patterns" },
  "mode.codzienny": { pl: "Codzienny", en: "Daily" },

  // ── Widget Fragmentu (AKSJOMAT 0) ──
  "frag.kompas": { pl: "Fragment · kompas", en: "Fragment · compass" },
  "frag.hint": {
    pl: "To nie jest lista do odhaczenia. To kompas — wejdź z dowolnego elementu.",
    en: "This is not a checklist. It's a compass — enter from any element.",
  },
  "frag.smile": { pl: "Uśmiech", en: "Smile" },
  "frag.smile_short": { pl: "Postawa, nie emocja.", en: "A stance, not an emotion." },
  "frag.smile_detail": {
    pl: "Ciekawość skierowana w siebie. „Ciekawe, jak sobie z tym poradzę” — nawet gdy trudno. Poszerza wewnętrzny horyzont, zmniejsza spinę. Nie wymaga że jest dobrze. Wymaga że jesteś.",
    en: "Curiosity turned toward yourself. “I wonder how I'll handle this” — even when it's hard. It widens the inner horizon and lowers the tension. It doesn't require things to be good. It requires you to be here.",
  },
  "frag.persp": { pl: "Perspektywa", en: "Perspective" },
  "frag.persp_short": { pl: "Jak patrzeć, nie gdzie dojść.", en: "How to look, not where to arrive." },
  "frag.persp_detail": {
    pl: "Zmiana centrum z „cel” na „spojrzenie”. Perspektywa nigdy się nie kończy — zawsze jest coś, czego jeszcze nie widziałeś. Karm ciekawość zamiast ją zabijać celem.",
    en: "Shifting the center from “goal” to “gaze”. Perspective never ends — there's always something you haven't seen yet. Feed curiosity instead of killing it with a goal.",
  },
  "frag.path": { pl: "Droga", en: "Path" },
  "frag.path_short": { pl: "Codzienne, rzeczywiste ruszanie się.", en: "Daily, real movement." },
  "frag.path_detail": {
    pl: "Bez Uśmiechu i Perspektywy Droga staje się pustostanem. Razem trzy elementy tworzą układ, który podtrzymuje się sam — nawet gdy jeden z nich słabnie.",
    en: "Without Smile and Perspective, the Path becomes a hollow shell. Together the three form a system that sustains itself — even when one of them weakens.",
  },

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
    pl: "Brak Web Speech API — nagrywam audio (Whisper fallback).",
    en: "No Web Speech API — recording audio (Whisper fallback).",
  },

  // Załączniki (tekstowe → extra_context)
  "brief.attach.btn": { pl: "Dołącz plik", en: "Attach file" },
  "brief.attach.hint": {
    pl: "Pliki tekstowe oraz .pdf / .docx — treść trafia do kontekstu briefu.",
    en: "Text files plus .pdf / .docx — content is added to the brief context.",
  },
  "brief.attach.remove": { pl: "Usuń", en: "Remove" },
  "brief.attach.unsupported": {
    pl: "Pominięto (nieobsługiwany typ): ",
    en: "Skipped (unsupported type): ",
  },
  "brief.attach.truncated": {
    pl: "Załączniki przycięto do limitu kontekstu (8000 znaków).",
    en: "Attachments truncated to the context limit (8000 chars).",
  },

  // Dream Wizard (#1 v2)
  "wizard.title": { pl: "Architekt Marzenia", en: "Dream Architect" },
  "wizard.step.dream": { pl: "Twoje marzenie", en: "Your dream" },
  "wizard.step.pillars": { pl: "Filary", en: "Pillars" },
  "wizard.step.milestones": { pl: "Kamienie milowe", en: "Milestones" },
  "wizard.step.first_step": { pl: "Pierwszy krok", en: "First step" },
  "wizard.step.summary": { pl: "Podsumowanie", en: "Summary" },
  "wizard.close": { pl: "Zamknij", en: "Close" },
  "wizard.cancel": { pl: "Anuluj", en: "Cancel" },
  "wizard.back": { pl: "← Wstecz", en: "← Back" },
  "wizard.next": { pl: "Dalej →", en: "Next →" },
  "wizard.launch": { pl: "Uruchom Radę", en: "Launch the Council" },
  "wizard.dream.prompt": {
    pl: "Opisz swoje marzenie — co naprawdę chcesz stworzyć, osiągnąć, przeżyć?",
    en: "Describe your dream — what do you truly want to create, achieve, experience?",
  },
  "wizard.dream.placeholder": {
    pl: "Moje marzenie to...",
    en: "My dream is...",
  },
  "wizard.pillars.prompt": {
    pl: "Na jakich filarach stoi to marzenie? Podaj 2–5 wartości, obszarów lub fundamentów.",
    en: "What pillars hold this dream? List 2–5 values, areas, or foundations.",
  },
  "wizard.pillars.pillar": { pl: "Filar", en: "Pillar" },
  "wizard.pillars.add": { pl: "Dodaj filar", en: "Add pillar" },
  "wizard.milestones.prompt": {
    pl: "Jakie kamienie milowe wyznaczysz? Chociaż jeden z opcjonalną datą.",
    en: "What milestones will you set? At least one, with an optional date.",
  },
  "wizard.milestones.what": { pl: "Co osiągniesz?", en: "What will you achieve?" },
  "wizard.milestones.add": { pl: "Dodaj milestone", en: "Add milestone" },
  "wizard.first_step.prompt": {
    pl: "Jaki jest Twój najmniejszy konkretny pierwszy krok (≤60 minut), który zrobisz jeszcze dziś?",
    en: "What is your smallest concrete first step (≤60 min) that you will take today?",
  },
  "wizard.first_step.placeholder": {
    pl: "Dziś w ciągu godziny zrobię...",
    en: "Today within one hour I will...",
  },
  "wizard.summary.prompt": {
    pl: "Sprawdź — za chwilę Rada przeanalizuje Twoje marzenie z 9 perspektyw.",
    en: "Review — the Council will analyze your dream from 9 perspectives.",
  },
  "wizard.summary.dream": { pl: "Marzenie", en: "Dream" },
  "wizard.summary.pillars": { pl: "Filary", en: "Pillars" },
  "wizard.summary.milestones": { pl: "Kamienie milowe", en: "Milestones" },
  "wizard.summary.first_step": { pl: "Pierwszy krok", en: "First step" },

  // Notifications Panel (#2)
  "notif.title": { pl: "Powiadomienia", en: "Notifications" },
  "notif.empty": { pl: "Brak zaległych zobowiązań.", en: "No pending commitments." },
  "notif.needs_attention": { pl: "Wymaga uwagi", en: "Needs attention" },
  "notif.enable_browser": {
    pl: "Włącz powiadomienia w przeglądarce",
    en: "Enable browser notifications",
  },

  // Integrations (#3)
  "integrations.title": { pl: "Integracje", en: "Integrations" },
  "integrations.env_hint": {
    pl: "Klucze API ustawiasz w zmiennych środowiskowych backendu (np. NOTION_API_KEY). Nie wklejaj ich w UI.",
    en: "API keys are set via backend environment variables (e.g. NOTION_API_KEY). Do not paste them in the UI.",
  },
  "integrations.export.label": { pl: "Eksport:", en: "Export:" },
  "integrations.export.err": {
    pl: "Eksport nie powiódł się — spróbuj ponownie",
    en: "Export failed — try again",
  },

  // Offline (#5)
  "offline.banner": {
    pl: "Jesteś offline — briefy będą zakolejkowane i wysłane po powrocie do sieci.",
    en: "You are offline — briefs will be queued and sent when you reconnect.",
  },
  "offline.queued_count": {
    pl: "{n} zakolejkowanych briefów — kliknij aby wysłać.",
    en: "{n} queued briefs — click to send.",
  },
  "offline.replay": { pl: "Wyślij", en: "Send" },

  // Login (#7)
  "login.subtitle": {
    pl: "Zaloguj się, żeby Rada pamiętała Twój kontekst.",
    en: "Log in so the Council remembers your context.",
  },
  "login.tab_login": { pl: "Logowanie", en: "Login" },
  "login.tab_register": { pl: "Rejestracja", en: "Register" },
  "login.username": { pl: "Login", en: "Username" },
  "login.password": { pl: "Hasło", en: "Password" },
  "login.display_name": { pl: "Imię (opcjonalnie)", en: "Name (optional)" },
  "login.btn_login": { pl: "Zaloguj", en: "Log in" },
  "login.btn_register": { pl: "Zarejestruj", en: "Register" },
  "login.skip": {
    pl: "Kontynuuj bez logowania (tryb single-user)",
    en: "Continue without login (single-user mode)",
  },
  "login.logout": { pl: "Wyloguj", en: "Log out" },

  "demo.badge": { pl: "Wersja demo", en: "Demo version" },
  "demo.intro": {
    pl: "Uruchom interaktywną debatę Rady z własnym briefem. Sesja jest tymczasowa — bez rejestracji.",
    en: "Run an interactive Council debate with your own brief. Temporary session — no sign-up.",
  },
  "demo.limit_debates": {
    pl: "Do {n} debat na sesję",
    en: "Up to {n} debates per session",
  },
  "demo.limit_chars": {
    pl: "Brief do {n} znaków",
    en: "Brief up to {n} characters",
  },
  "demo.limit_ephemeral": {
    pl: "Dane sesji nie są trwałe",
    en: "Session data is not permanent",
  },
  "demo.btn_start": { pl: "Rozpocznij demo", en: "Start demo" },
  "demo.footer": {
    pl: "Pełna wersja (founders / lokalna instalacja) — bez limitów, z własnym kontem.",
    en: "Full version (founders / local install) — no limits, your own account.",
  },
  "demo.banner": {
    pl: "Demo — pozostało debat: {n}. Dane sesji są tymczasowe.",
    en: "Demo — debates remaining: {n}. Session data is temporary.",
  },
  "demo.banner_exhausted": {
    pl: "Limit demo wyczerpany. Pełna wersja: instalacja lokalna / founders.",
    en: "Demo limit reached. Full version: local install / founders.",
  },
  "demo.new_session": { pl: "Nowa sesja demo", en: "New demo session" },

  "device_lock.badge": {
    pl: "Instalacja zablokowana",
    en: "Installation locked",
  },
  "device_lock.title": {
    pl: "Architekt powiązany z innym komputerem",
    en: "Architect bound to another computer",
  },
  "device_lock.body": {
    pl: "Ta kopia Architekta została po raz pierwszy uruchomiona na innej maszynie i jest do niej przypisana. Uruchomienie skopiowanej wersji (pendrive, chmura, przeniesiony folder) na tym komputerze jest niemożliwe.",
    en: "This copy of the Architect was first launched on another machine and is bound to it. Running a copied version (USB stick, cloud, moved folder) on this computer is not possible.",
  },
  "device_lock.fp_current": { pl: "ta maszyna", en: "this machine" },
  "device_lock.fp_sealed": { pl: "pieczęć", en: "seal" },
  "device_lock.recovery_title": {
    pl: "Zmieniasz sprzęt lub reinstalujesz system? Uruchom reset:",
    en: "Changing hardware or reinstalling the OS? Run the reset:",
  },
  "device_lock.footer": {
    pl: "Reset zwalnia powiązanie i pozwala przypisać tę maszynę przy następnym uruchomieniu.",
    en: "Reset releases the binding and lets this machine be assigned on next launch.",
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
        lang === "pl" ? "Architekt Wolności" : "Freedom Architect";
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
