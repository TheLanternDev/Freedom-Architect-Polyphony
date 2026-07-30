# Naprawy po review 2026-07-17 — wykonane

Baza: review „senior dev hates this” z 2026-07-17. Status per zarzut.

## #2 Advisor — tor pieniędzy (agents/base_agent.py, config/agent_models.py)

- **2a cache poisoning NAPRAWIONE**: fallback po awarii advisora przelicza
  `cache_key` z `advisor=False` przed zapisem — wynik bez advisora nigdy nie
  ląduje pod kluczem advisorowym.
- **2b koszt utopiony NAPRAWIONE**: `_AdvisorPathError` niesie częściowe
  odpowiedzi API; zafakturowane iteracje nieudanej tury (executor + advisor)
  wchodzą do `advisor_cost` i logu kosztów zamiast znikać (`advisor_cost=0.0`
  usunięte).
- **2c komentarz vs kod NAPRAWIONE**: `ADVISOR_SCOPE` — komentarz mówi teraz
  prawdę (default `syez`, rozszerzenie świadome przez `AW_ADVISOR_SCOPE=all`).
- **2d zimny cache NAPRAWIONE**: wywołania bez advisora zostają na kluczu
  v10 bajt-w-bajt (ciepły cache przeżywa wdrożenie); v11 tylko dla advisora.
- **2e sniffing błędów NAPRAWIONE**: retry-bez-temperature tylko na typowanym
  `BadRequestError` + nazwa parametru; timeouty/5xx nie wchodzą w gałąź.
- **2f dedup NAPRAWIONE**: `_extract_advisor_response` wykrywa treść
  skumulowaną po `pause_turn` (prefiks) i zastępuje zamiast dokleić.
- OTWARTE (świadomie): jeden realny przebieg z `AW_ADVISOR_ENABLED=true`
  przed zaufaniem kosztom — bramka merge w PR-4 (plan podziału).

## #3 pricing.py NAPRAWIONE

Prefiksowe dopasowanie datowanych snapshotów (`claude-sonnet-5-YYYYMMDD`,
`claude-opus-4-8-...`) + warning raz-na-model przy nieznanym modelu.
Dashboard z zerem ma teraz ślad w logach.

## #4 device_seal NAPRAWIONE

- `_FP_VERSION=2` + `_legacy_fingerprints()`: pieczęć starego algorytmu na
  tej samej maszynie → cicha migracja (created_at zachowany), nie „locked”.
- Fallback: trwały `machine.id` (0600, O_EXCL) w katalogu pieczęci zamiast
  `platform.node()` — koniec klasy false-locków mDNS/DHCP przy awarii
  ioreg/winreg. Limit machine-id w klonach VM udokumentowany jako świadomy.

## #5 env_bootstrap NAPRAWIONE

- Ratchet `AW_ENV` w boxed: tylko `production`/`boxed`; `development` z
  config.env wymuszane z powrotem na `boxed` + warning. Furtka zamknięta.
- Komentarz 0600 uczciwy: POSIX-only; Windows chroni ACL profilu.

## #6 lib.rs NAPRAWIONE

- `log_launcher()` → `logs/launcher.log` (rotacja 5 MB) dla CAŁEJ diagnostyki
  preflightu/spawnu/exitu — zgłoszenie testera ma z czego czerpać.
- `pid_looks_like_backend(pid, port)`: sidecar po nazwie ALBO
  uvicorn+main:app+nasz port; Windows przez CIM CommandLine (tasklist tylko
  dla unikalnej nazwy sidecara — koniec ubijania cudzych pythonów).
- `health_marker`: read timeout 1000→2500 ms + `health_marker_with_retry`
  (3 próby) zanim port zostanie uznany za OBCY.
- `PortState::Blocked` widoczny: managed `BackendStartupStatus` + komenda IPC
  `backend_startup_status` (pending/spawned_sidecar/spawned_dev/
  reused_existing/port_blocked/spawn_failed/autospawn_disabled).
  NAJMNIEJSZY NASTĘPNY RUCH (≤60 min): frontend woła ją przy błędzie /health
  i mapuje `port_blocked` na dedykowany klucz i18n.
- Exit: 700 ms→400 ms (sidecar), 1.5 s→0.4 s (dev) na wątku głównym.
- UWAGA: brak cargo w środowisku naprawy — wymagane `cargo check` przy
  najbliższym buildzie (wzorce zgodne z istniejącym kodem).

## #7 timeouty NAPRAWIONE

SDK timeout ustawiany ZAWSZE (`wait_for` > SDK dla każdego agenta, nie tylko
z `timeout_s`). SSE pod 150 s syntezy fa2 ZWERYFIKOWANE: `synthesis_heartbeat`
co 8 s + frontend bez własnego timeoutu odczytu — udokumentowane w
config/agent_models.py.

## #1/#0/#8 higiena repo

- Assety `.glb/.png` przeniesione z `agents/` (pakiet Pythona) do
  `assets/agents/` — zero referencji w kodzie, sidecar czysty.
- Plan podziału na 6 PR-ów: `docs/PLAN_PODZIALU_PR_2026-07-17.md`
  (kolejność, zawartość, bramka eval dla migracji Sonnet 4.6→5 w PR-3,
  bramka realnego przebiegu advisora w PR-4).
- Untracked komponenty 3D wchodzą RAZEM z App.tsx w PR-6 (naprawa zarzutu #1).

## Testy

- Nowe: klucz v10/v11, fallback→v10 (anty-poisoning), koszt utopiony w logu,
  dedup pause_turn, migracja seal + trwały machine.id, ratchet AW_ENV,
  pricing prefiks+warning.
- Naprawione pułapki suity (znalezione przy okazji):
  - `monkeypatch.delenv` na nieobecnej zmiennej nie zapisuje restore —
    testy boxed przeciekały `AW_ENV=boxed`/JWT do procesu → masowe 401
    (73 pozorne faile). Wzorzec setenv-przed-delenv w `_boxed_env` +
    `os.environ.pop` w środku testów.
  - proces-wide cache seal-checka przeżywał granice testów → 423 w cudzych
    testach; conftest bustuje przed/po każdym teście.
  - `test_cache._fake_call` bez `advisor_override` (rozjazd z working tree).
- Wynik: pełna suita = te same 32 pre-existing faile co HEAD w tym samym
  środowisku (braki zależności sandboxa), **0 nowych regresji**.
