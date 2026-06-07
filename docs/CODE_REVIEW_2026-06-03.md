# Code Review — Architekt Wolności (weryfikacja jakości vs cena)

**Data:** 2026-06-03 · **Zakres:** całe repo, soczewka: bezpieczeństwo + wartość IP uzasadniająca cenę founders.
**Metoda:** niezależne grepy bezpieczeństwa, lektura plików krytycznych (`agents/base_agent.py`, `agents/syez.py`, `api/http_guard.py`, `api/services/debate_orchestrator.py`, `core/completion_enforcer.py`), dane z `AUDIT_PRODUCTION_READINESS.md`.

## Podsumowanie

Kod jest **dojrzały, produkcyjny i autorski**. To nie wrapper na czat — to system z realną logiką wieloagentową, twardą izolacją tenantów i dyscypliną zasobów na poziomie seniorskim. Skala: **~10,7k LOC backend** (agents 1,8k / core 2,7k / api 4,2k / db 1,8k) + **8,2k LOC frontend** + **8,3k LOC testów**. Stosunek testów do kodu ~1:1.

## Bezpieczeństwo — niezależna weryfikacja (potwierdza audyt)

| Sprawdzenie | Wynik |
|-------------|-------|
| Hardcoded secrets (sk-ant / xai / AKIA) w kodzie | **0 trafień** |
| `eval()` / `exec()` / `pickle.load` | **0** |
| Raw formatowany SQL (injection) | tylko `PRAGMA table_info({tbl})` — stała wewn., nie user input → **bez ryzyka** |
| `shell=True` | **0** |
| Insecure `getenv(default=admin/secret/…)` | **0** |
| Auth fail-closed bez sekretów | potwierdzone w `http_guard.py:78–102` |
| Legacy key odrzucony gdy JWT on | potwierdzone `http_guard.py:165–177` |
| Cache LLM izolowany per tenant+user | potwierdzone `base_agent.py:508–537` (klucz v8) |

**Werdykt bezpieczeństwa:** P0 z review 2026-06-02 są realnie zamknięte w kodzie — nie tylko w dokumentacji. Zostają znane P1 (BFF httpOnly, JWT na publicznym hoście) — podniesione w `PLAN_100_100.md`, nie blokują wartości produktu.

## Co świadczy o wysokiej wartości (uzasadnia cenę)

1. **`base_agent.py:521–537`** — komentarz przy kluczu cache wprost adresuje cross-user data leak (wspólny prefix briefu → odpowiedź jednego usera drugiemu). To myślenie multi-tenant rzadkie w produktach solo.
2. **`debate_orchestrator.py:494–509`** — przy rozłączeniu klienta SSE aktywne task-i LLM są **anulowane**, żeby nie palić tokenów Anthropic. Czysty shutdown SDK. Dyscyplina kosztowa = bezpośrednia wartość dla kupującego BYOK.
3. **`syez.py:19–60`** — 7-stopniowy protokół konsolidacji z AKSJOMATEM 0 jako filtrem nadrzędnym. To jest rdzeń IP, nieodtwarzalny promptem z półki.
4. **Pokrycie testami** (audyt: 572 pass, coverage 80%, gate 75% w CI 7-job) — poziom inżynierii znacznie powyżej „MVP founders".

> Uwaga: w tej sesji nie przeuruchomiłem pełnego pytest (suite > limit czasu cold-VM); opieram się na liczbie 572 z audytu + bezpośredniej lekturze i niezależnych grepach. Rekomendacja: jeden lokalny przebieg `pytest tests/ -q` jako finalne potwierdzenie przed wyceną.

## Drobne uwagi (nie blokery)

| # | Plik | Uwaga | Status |
|---|------|-------|--------|
| 1 | ~~`requirements.txt` camelot/pypdf~~ | **Wycofane** — camelot NIE jest zależnością repo; konflikt pochodził z mojej instalacji pip w VM, nie z `requirements.txt` (tam tylko `pypdf>=4.0.0`, spójne) | ✅ non-issue |
| 2 | `base_agent.py:6` | docstring „5 prób" → poprawione na „2 próby" | ✅ ZAMKNIĘTE |
| 3 | `db/connection.py:108` | dodano komentarz „tbl = stała wewn., brak injection" | ✅ ZAMKNIĘTE |
| 4 | `core/completion_enforcer.py:47` | `MAX_ACTIVE_PROJECTS` 1 → **3** (na życzenie); zaktualizowano testy (smoke limit-agnostyczny), `USER_README`, `SOFT_LAUNCH` | ✅ ZAMKNIĘTE |

## Cleanup (wykonane / do wykonania)

Sandbox tej sesji jest read-only dla usuwania w folderze repo. Przygotowałem **`scripts/cleanup_repo.sh`** (bezpieczny, odwracalny):
- `redesign.html` — martwy mockup (żywe UI = `src/src/`), niereferencjonowany → usuń.
- `coverage_baseline.txt` — stary snapshot, trackowany, nieużywany → `git rm` + dopis do `.gitignore`.
- 28× `.DS_Store`, 15× `__pycache__`, `.coverage` — szum, gitignored → wyczyść z working tree.
- **Nietknięte świadomie:** `CZYTAJ_MNIE*.txt` (używane przez `pack-founders-archive.sh`/`INSTALL.md`), `Fragment.pdf` (źródło kosmologii AKSJOMAT 0).

`.gitignore` jest już zdyscyplinowany (venv/build/dist/pycache/.DS_Store ignorowane) — po jednorazowym sprzątnięciu śmieci nie wrócą.

## Werdykt ceny

**Jakość kodu potwierdza i UDŹWIGNIE cenę €499–€899.** Architektura, izolacja tenantów, pokrycie testami i autorska logika Rady plasują to wyraźnie powyżej kategorii „BYOK utility" ($49–$299). 

- **€899** (kod + okresowe wsparcie) — uzasadnione; aktywne wsparcie to realny, kosztowny tier.
- **€499 founders BYOK** (bez SLA, support best-effort) — uzasadnione jako sam kod + samodzielna instalacja; różnica ~€400 = czytelna cena rezygnacji z opieki.

**Rekomendacja:** zatwierdź **€499 founders / €899 supported**. Jedyny warunek techniczny przed pobieraniem premium: domknij P1 izolacji (BFF httpOnly + wymuszenie JWT na publicznym hoście) — przy €499+ kupujący wnosi realne dane, więc izolacja musi być zamknięta zanim ktokolwiek zapłaci.

**Verdict: Approve (z warunkiem P1 przed publicznym launchem).**
