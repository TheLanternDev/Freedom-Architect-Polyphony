Freedom Architect: Polyphony — Comprehensive Project Context (dla asystentów AI)
Pełna nazwa: Freedom Architect: Polyphony (Rada Nadzorcza „Mój Świat”)

> **Stan na 2026-06-18.** Funkcjonalny opis kodu: `docs/ARCHITEKT_WOLNOSCI_OPIS.md`. Strategia: `docs/roadmap/ROADMAP_2026-06-17.md`. Baseline bezpieczeństwa: `CODE_REVIEW_2026-06-16.md` (4 blokery z 2026-06-02 = zamknięte).

Misja projektu:
Stworzenie świadomego, wieloperspektywicznego systemu multi-agentowego, który wspiera człowieka w procesie stawania się wolnym — poprzez lepsze rozumienie siebie, integrację wewnętrznych konfliktów i podejmowanie decyzji wysokiej jakości, zarówno w życiu osobistym, jak i w budowaniu biznesu. System nie zastępuje myślenia ani odpowiedzialności użytkownika. Ma za zadanie podnosić jakość sygnału i zmniejszać wpływ szumu, automatycznych wzorców i nieuświadomionych lojalności.

Głęboka tożsamość projektu:
Freedom Architect to nie chatbot ani asystent zadaniowy. To wewnętrzna Rada Nadzorcza — symulacja dojrzałego, zintegrowanego procesu myślowego. Składa się z dziewięciu wyspecjalizowanych agentów, z których każdy reprezentuje inną warstwę psychiki i inteligencji, oraz Syeza — syntezatora, który nie dodaje własnego głosu, tylko uczciwie konsoliduje to, co Rada naprawdę powiedziała, pokazując napięcia i sprzeczności.
Projekt wyrasta z osobistej drogi autora i opiera się na prywatnej kosmologii opisanej w tekście „Fragment”. Jego najgłębszym fundamentem nie jest dążenie do celu, lecz utrzymanie żywego, samopodtrzymującego się systemu trzech elementów: Uśmiechu, Perspektywy i Drogi. System nie służy „byciu bardziej produktywnym”. Jest narzędziem do bycia bardziej sobą w sposób, który przekłada się na czystsze decyzje i autentyczne działanie.

Dziewięć głosów Rady:

Kogit — Kognitywny: mapuje ukryte przekonania i odziedziczone założenia.
Szow — Cień (Jung): brutalnie szczerze nazywa to, co wyparte i sabotujące.
Kidi — Dziecko: reprezentuje czystą ciekawość i instynktowną prawdę sprzed internalizacji ograniczeń.
Tai — Czasowy: widzi pętle czasowe i powtarzające się wzorce.
Obver — Obserwator: utrzymuje meta-perspektywę, opisuje sekwencje bez oceniania.
Relacjan — Relacyjny: mapuje sieć relacji, lojalności i oczekiwań innych ludzi.
Emojy — Emocjonalny: pracuje z emocją jako informacją, zanim zostanie nazwana.
Smaty — Somatyczny: zwraca uwagę na sygnały ciała jako najszybsze źródło prawdy.
Deega — Głęboka Diagnoza: szuka starszych wzorców i lojalności wobec przeszłości.

Syez pełni rolę syntezatora i strażnika jakości. Nie jest dziesiątym głosem. Jest lustrem Rady + Architektury Marzenia. Jego zadaniem jest pokazywanie napięć, wyłanianie wspólnego mianownika i prowadzenie do domknięcia.

AKSJOMAT 0 – Filozofia Fragmentu (Uśmiech ↔ Perspektywa ↔ Droga)
AKSJOMAT 0 jest najbardziej fundamentalną warstwą całego projektu — głębszą i bardziej pierwotną niż AKSJOMAT 1 i 2.
Zamiast linearnego modelu „cel → osiągnięcie → pustka”, projekt opiera się na symetrycznym, samopodtrzymującym się systemie trzech elementów:

Uśmiech — nie jest emocją, lecz postawą. Jest ciekawością skierowaną w siebie. Postawą „ciekawe, jak sobie z tym poradzę”, nawet gdy jest trudno. Poszerza wewnętrzny horyzont i zmniejsza spinę.
Perspektywa — zmiana centrum z „gdzie dojść” na „jak patrzeć”. Perspektywa nigdy się nie kończy, bo zawsze jest coś, czego jeszcze nie widziałeś. Karm i ciekawość zamiast ją zabijać (jak robi to cel).
Droga — rzeczywiste, codzienne poruszanie się. Droga bez Uśmiechu i Perspektywy staje się pustostanem. Razem trzy elementy tworzą system, który może być podtrzymywany nawet wtedy, gdy jeden z nich słabnie.

System jest symetryczny — można wejść z każdego z trzech punktów. Jest kompasem, a nie mapą. Nie wskazuje konkretnego miejsca docelowego, tylko kierunek patrzenia. Kluczowym warunkiem wejścia w ten system jest zatrzymanie — wewnętrzna pauza, w której można zobaczyć, że schemat linearnego celu jest pułapką.
AKSJOMAT 1 i AKSJOMAT 2 są narzędziami służącymi AKSJOMATOWI 0. Mają pomagać w utrzymaniu tego żywego, samopodtrzymującego się układu w codziennym działaniu.
Dwa fundamentalne Aksjomaty:

AKSJOMAT 1 – Architektura Marzenia (Dream Architecture):
Każdy agent i każda synteza ma dostęp do szerszego kontekstu — marzenia, wartości i kierunku, któremu dana decyzja ma służyć. Bez tego kontekstu system traci sens. AKSJOMAT 1 istnieje po to, żeby wspierać realizację AKSJOMATU 0.
AKSJOMAT 2 – Domknięcie (Completion Enforcer):
Rada zawsze prowadzi do konkretnego, najmniejszego możliwego ruchu do przodu. Audytuje, co blokuje realizację i wskazuje, co można zrobić w ciągu najbliższych 60 minut. Bez domknięcia system staje się jedynie intelektualną rozrywką. AKSJOMAT 2 istnieje po to, żeby chronić AKSJOMAT 0 przed rozpadem na poziomie codziennego działania.

Aktualny kierunek rozwoju:
Warstwa Daily Signal Vision — codzienny, wysokosygnałowy filtr na najbliższe 18h (nie lista zadań, lecz świadomy wybór elementów Uśmiech ↔ Perspektywa ↔ Droga). Szczegóły w `core/dream_architect.py` i `GET /personal/ritual/daily`.

Model dystrybucji (decyzja 2026-06-17):
**Pudełko local-first BYOK** — nie SaaS. Klient dostaje izolowaną paczkę (lokalny SQLite, własny klucz LLM, device-seal). Dane debat nie przechodzą przez naszą infrastrukturę. Warstwa multi-tenant/RLS zostaje w repo jako defense-in-depth, ale jest **uśpiona** dopóki nie ruszy hosting (roadmap Later L1). Blokery sprzedaży paczki: szyfrowanie at-rest, keychain BYOK, disclaimery, podpisane buildy, EULA, forma prawna — patrz roadmap NOW N1–N6.

Dwa tryby działania (oba w kodzie):

personal — głęboka praca nad sobą; A0 (destylacja marzenia), Obraz Użytkownika, ton transformacyjny.
fa2 (Freedom Architect Business) — analityczno-biznesowy; mount `/business`, nagłówek `X-Council-Mode: fa2`; bez A0 i bez Obrazu; Syez z wyższym limitem tokenów. Te same 9 agentów, inne prompty (`business_fa2/`).

Architektura techniczna (stan 2026-06-18):
- Backend: Python 3.13, FastAPI **3.3.0**, Uvicorn
- Frontend: **Tauri 0.1.0** + React 19 + TypeScript + Vite 6 + Tailwind
- Model LLM: **claude-sonnet-4-6** dla wszystkich agentów i Syeza (`config/agent_models.py`)
- Backends LLM: `LLM_BACKEND=auto|anthropic|xai|ollama` (`config/llm_providers.py`); BYOK przez nagłówek `X-LLM-Key`; w produkcji bez klucza usera → fail-closed
- Baza dev: SQLite; prod/hosted: PostgreSQL + RLS (migracje `0001`–`0009`)
- Cache/stan: Redis (JTI blocklist, rate-limit, idempotency debat)
- Wszystkie agenty dziedziczą po `BaseAgent`: async LLM, retry, cache per-user, koszty tokenów, Dream Architecture, domknięcie

Kluczowe pliki:

agents/base_agent.py — rdzeń LLM i wspólne mechanizmy
agents/syez.py — syntezator (najbardziej rozbudowany prompt)
core/dream_architect.py — AKSJOMAT 1 + Fragment + Daily Signal
core/completion_enforcer.py — AKSJOMAT 2 (audyt prozy syntezy, limity projektów)
api/services/debate_orchestrator.py — pipeline SSE debaty
api/http_guard.py — auth, tenant, device seal
business_fa2/api/main.py — sub-app `/business`

Bezpieczeństwo (baseline `CODE_REVIEW_2026-06-16.md`):
Cztery blokery z 2026-06-02 zamknięte fail-closed: auth bez sekretów → 401, legacy API key pod JWT odrzucony, admin token-gated, Tauri CSP pełne. Dodatkowo: JTI revocation fail-closed w prod, RLS hardening (migracja 0009), Idempotency-Key na `/debate/stream`, SSE single-retry guard. **Otwarte bloker GTM (nie security):** buildy desktop niepodpisane (`signingIdentity: null`), SQLite plaintext at-rest w modelu pudełkowym.

Zasady pracy nad projektem:

AKSJOMAT 0 jest nadrzędny — każda większa zmiana musi wzmacniać Uśmiech ↔ Perspektywa ↔ Droga, nie przywracać linearnego myślenia o celu.
Sygnał ponad szum — nie dodawaj funkcji „bo można”.
Szacunek do architektury — zmiany chirurgiczne, bez refaktorów na siłę.
Autentyczność głosów — nie łagodź Szowa, nie coachinguj Kidi, nie czynij Obvera empatycznym.
Jakość promptów systemowych — świętość; zmiany precyzyjne i spójne z Radą.
Domknięcie — przy większych zmianach podawaj najmniejszy możliwy następny krok (≤60 min).
Daily Signal — projektuj pod horyzont 18h użytkownika.
Unikaj nadmiernego entuzjazmu — dyscyplina i precyzja ponad kreatywność dla samej kreatywności.

Styl komunikacji Rady:
Rada komunikuje się bezpośrednio, konkretnie i bez owijania w bawełnę. Potrafi być surowa, gdy wymaga tego sytuacja (szczególnie Szow i Deega). Jednocześnie szanuje inteligencję użytkownika. Nie stosuje taniego motywowania ani pustych afirmacji.
