# Plan podziału working tree na PR-y — 2026-07-17

Stan: ~50 zmodyfikowanych plików + ~40 untracked w jednym working tree.
Review 2026-07-17 (zarzut #0): nie da się tego zbisectować ani selektywnie
zrevertować. Poniżej podział na 6 logicznych PR-ów w kolejności merge'owania —
każdy samodzielnie buildowalny i testowalny.

Zasada: `git add` TYLKO pliki wymienione w danym kroku, commit, test, dopiero
potem następny krok. Untracked komponenty wchodzą RAZEM z plikami, które je
importują (zarzut #1 — App.tsx importował untracked Council3D itd.).

---

## PR-1 — Fundament bezpieczeństwa: security_hardened() + boxed profile

Zakres (backend only, zero zależności od reszty):
- `api/settings.py` (is_boxed, security_hardened, CORS boxed)
- `api/http_guard.py`, `api/routers/personal.py`, `api/routers/feedback.py`,
  `api/routers/meta.py` (marker /health), `api/services/debate_orchestrator.py`
  (tylko hunki security_hardened), `config/llm_providers.py` (hunki
  security_hardened + anthropic_omits_temperature)
- `env_bootstrap.py` + `config/__init__.py` (bootstrap boxed, JWT secret,
  ratchet AW_ENV)
- `shared/utils/cache.py` (O_EXCL na kluczu Fernet)
- `core/device_seal.py` (stable machine id + migracja fp_version)
- testy: `tests/test_pricing_and_seal.py` (część seal), `tests/test_boxed_and_advisor.py`
  (część boxed)

## PR-2 — Cennik: config/pricing.py jako jedyne źródło prawdy

- NOWY `config/pricing.py` (prefix match + warning na nieznany model)
- `agents/base_agent.py` — WYŁĄCZNIE hunk `_PRICES_PER_M` → `_price_per_m`
- `shared/utils/llm.py` (delegacja do pricing)
- testy: `tests/test_pricing_and_seal.py` (część pricing)

## PR-3 — Migracja modelu Sonnet 4.6 → 5  ⚠️ BRAMKA EVAL

- `config/agent_models.py` (tylko `_SONNET`), `shared/utils/llm.py` (MODELS)
- `agents/base_agent.py` — hunk retry-temperature (BadRequestError)
- `config/agent_models.py` — timeout_s dla Syeza + SDK timeout zawsze
  (`tests/test_llm_timeout_config.py`)
- **WARUNEK MERGE**: przebieg eval-reviewer na min. 5 briefach (personal +
  fa2), porównanie syntez 4.6 vs 5 obok siebie, świadoma decyzja. Jakość
  promptów to świętość (CLAUDE.md) — zmiana modelu każdego głosu bez evala
  to zaprzeczenie tej zasady.

## PR-4 — Advisor tool (feature, domyślnie wyłączony)

- `config/agent_models.py` (ADVISOR_*), `agents/base_agent.py` (cała ścieżka
  advisora: _call_with_advisor, _AdvisorPathError, _extract_advisor_response,
  klucz v10/v11, koszt utopiony), `api/services/debate_orchestrator.py`
  (advisor_override=False w audycie)
- testy: `tests/test_boxed_and_advisor.py` (część advisor)
- **WARUNEK MERGE**: jeden realny przebieg z AW_ADVISOR_ENABLED=true na
  własnym kluczu — weryfikacja kształtu usage.iterations i realnych kosztów
  (komentarz w kodzie jawnie mówi, że nie było odpalone przeciw API).

## PR-5 — Paczka desktop: sidecar Tauri + launcher

- `src/src-tauri/src/lib.rs` (sidecar, PID-file, health preflight z retry,
  launcher.log, backend_startup_status, graceful exit)
- `src/src-tauri/tauri.conf.json`, `capabilities/*.json`, `scripts/build-backend-sidecar.sh`,
  `scripts/windows/build-backend-sidecar.ps1` (untracked — wchodzą TU),
  `boxed_entry.py` (untracked — wchodzi TU), `src/scripts/make-dmg.sh`,
  `.github/workflows/tauri-release.yml`, `docs/TAURI_RELEASE.md`, `INSTALL.md`
- CSP: `src/scripts/sync-tauri-csp.mjs`, `src/scripts/tauri-release-env-check.mjs`
- NAJMNIEJSZY NASTĘPNY RUCH po merge: frontend woła `backend_startup_status`
  przy błędzie /health i mapuje `port_blocked` na dedykowany komunikat i18n
  (klucz `debate.network.port_blocked`) — ≤60 min.

## PR-6 — Frontend 3D + brand

- `src/src/App.tsx` RAZEM z untracked: `Council3D.tsx`, `Backdrop3D.tsx`,
  `BootSequence.tsx`, `BrandVisual.tsx`, `sceneBus.ts`, `agentForms.ts`,
  `src/public/brand/`
- `BriefForm.tsx`, `CouncilCircle.tsx` (deprecacja), `LoginScreen.tsx`,
  `WorkspaceHeader.tsx`, `index.css`, `tailwind.config.ts`, `i18n.tsx`,
  `fetchErrors.ts`, `main.tsx` (fonty @fontsource), `package.json`,
  `package-lock.json`
- Assety agentów: `assets/agents/*.png|*.glb` (przeniesione z `agents/` —
  pakiet Pythona ma być czysty; jeśli frontend ich używa, właściwe miejsce
  to `src/public/`)

## Poza PR-ami — do decyzji osobno

- `landing/`, `widmo/`, `wieza-rady/`, `polifonia/`, `reels/`,
  `obsydianowa-rada.html` — eksperymenty/prototypy. Decyzja: osobne repo
  (jak architekt-demo w 096ff68) albo `experiments/` z wpisem w .gitignore
  builda. NIE mieszać z PR-ami wyżej.
- Usunięcia (`CZYTAJ_MNIE*.txt`, `SPRZEDAZ_CHECKLIST.md`, `coverage_baseline.txt`,
  `scripts/build-sponsor-embed.py`, stary `tools/reels-generator/`) — jeden
  commit porządkowy na końcu.

## Kolejność merge i dlaczego

1 → 2 → 3 → 4 → 5 → 6. PR-1 nie zależy od niczego. PR-2 dotyka linii obok
PR-4 w base_agent.py — dlatego przed. PR-3 przed PR-4 (advisor zakłada
Sonnet 5 jako executora). PR-5 zakłada boxed profile z PR-1. PR-6 czysto
frontendowy — na końcu, bo jedyny bez wpływu na tor pieniędzy i security.
