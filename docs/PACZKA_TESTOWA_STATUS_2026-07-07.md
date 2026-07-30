# Paczka testowa (macOS + Windows) — status i workflow — 2026-07-07

Kontynuacja `docs/REVIEW_I_PACZKA_TESTOWA_2026-06-25.md` (Tor B: paczka
desktop self-contained). Ten plik opisuje co zostało **zaimplementowane w
kodzie dzisiaj**, co to realnie zamyka, i co **musisz jeszcze zrobić Ty**
(decyzje biznesowe/konta + realne buildy na macOS/Windows — obu nie da się
wykonać z tej sesji, patrz „Czego NIE zrobiono i dlaczego” niżej).

## Co było potrzebne (diagnoza)

Trzy rzeczy, niezależnie od siebie:

1. **Samowystarczalna binarka** — `.app`/`.msi` nie może polegać na tym, że
   tester ma Pythona, Node i sklonowane repo z `.venv`. Backend musi być
   zamrożony (PyInstaller) i wpięty do Tauri jako *sidecar*.
2. **Zero-terminal desktop entry** — ikona na pulpicie ma odpalać jeden
   proces (Tauri), który sam startuje backend w tle i sam się o niego troszczy
   (start, logi, zamknięcie). Użytkownik nigdy nie widzi terminala.
3. **Konfiguracja bez ręcznej edycji plików** — `ARCHITEKT_JWT_SECRET` jest
   dziś wymagany do rejestracji/logowania (fail-closed w `auth.py`) i musi
   powstać automatycznie, bo tester nie ma terminala żeby go wygenerować.

Do tego dwa blokery z poprzedniego review, które NIE są kodem tylko
decyzjami/kontami: podpis binarek (B2) i szyfrowanie danych at-rest (B3).

## Co zostało zrobione dzisiaj (kod, w repo)

**1 — sidecar (zamyka blocker B1 na poziomie kodu):**

- `boxed_entry.py` (nowy) — punkt wejścia dla zamrożonej binarki, bez
  `--reload`/multi-workera (PyInstaller onefile nie umie się re-spawnować).
- `scripts/build-backend-sidecar.sh` + `scripts/windows/build-backend-sidecar.ps1`
  (nowe) — PyInstaller `--onefile` z `--copy-metadata` dla anthropic/openai/
  fastapi/starlette/sentry-sdk/uvicorn (inaczej `importlib.metadata.
  PackageNotFoundError` w zamrożonej binarce — znany gotcha tych SDK-ów) +
  `--collect-submodules` dla `agents/api/core/db/config/business_fa2` +
  `--add-data` dla `db/schema*.sql`, `db/migrations/`, `core/fonts/` (font
  DejaVu — bez niego PDF-y z polskimi znakami wyglądają źle). Oba skrypty
  kończą się smoke-testem `GET /health` na świeżo zbudowanej binarce.
- `src/src-tauri/tauri.conf.json` — `bundle.externalBin: ["binaries/architekt-backend"]`.
- `src/src-tauri/capabilities/default.json` — permission `shell:allow-spawn`
  zawężony do tego jednego sidecara (`sidecar: true, args: false`).
- `src/src-tauri/src/lib.rs` — przepisany. Dwie ścieżki:
  - **sidecar** (produkcja/paczka testowa) — `app.shell().sidecar(...)`,
    stdout/stderr lecą do plików w katalogu danych (nie `/dev/null` —
    naprawia też finding S5 z poprzedniego review: bez tego zgłoszenie buga
    testera nie miało z czego czerpać).
  - **dev fallback** — dokładnie stare zachowanie (`python -m uvicorn
    main:app --reload` z `.venv` obok repo), używane automatycznie gdy
    sidecar nie jest zbudowany (typowe w `npm run tauri:dev`). Zero regresji
    w dotychczasowym dev-loopie.
  - `AW_DISABLE_AUTOSPAWN=1` nadal wyłącza obie ścieżki.

**2 — zero-config przy pierwszym starcie (nowe, nie było w poprzednim review):**

- `env_bootstrap.py` — rozbudowany o `app_data_dir()` (macOS: `~/Library/
  Application Support/ArchitektWolnosci`, Windows: `%APPDATA%\
  ArchitektWolnosci`, Linux: `~/.local/share/ArchitektWolnosci`) i tryb
  „boxed”: gdy `sys.frozen` (czyli wewnątrz sidecara), moduł **sam generuje
  `ARCHITEKT_JWT_SECRET`** (32 losowe bajty) i **zapisuje go trwale** do
  `config.env` w tym katalogu — bez tego każdy restart wylogowywałby
  wszystkich. Ustawia też domyślne `ARCHITEKT_DB_PATH` / `COST_LOG_PATH` /
  `EVENTS_LOG_PATH` w tym samym katalogu (zamiast efemerycznego katalogu
  ekstrakcji PyInstallera, który znika po zamknięciu procesu — to by
  kasowało bazę tester co restart).
- **Klucz LLM (Anthropic) nadal NIE przechodzi przez ten plik** — idzie przez
  Keychain/Credential Manager OS (`store_llm_key`/`get_llm_key` w `lib.rs`,
  już istniejące) i nagłówek `X-LLM-Key` per-request. Tester wpisuje klucz
  raz w UI (Ustawienia), nie w pliku.
- `main.py` i `config/__init__.py` — poprawiony sposób ładowania
  `env_bootstrap.py` w trybie frozen. Poprzedni kod ładował go dynamicznie
  po ścieżce pliku (`Path(__file__).parent / "env_bootstrap.py"`) — w
  PyInstaller `--onefile` ten plik fizycznie nie istnieje na dysku (moduły
  Pythona są zaszyte w binarce, nie rozpakowane), więc to zawsze cicho
  failowało (złapane przez `except Exception: pass`) i **JWT secret nigdy
  by się nie wygenerował**. To był realny, nieoczywisty bug, który
  wypłynąłby dopiero przy pierwszym uruchomieniu binarki u testera.

**3 — prywatność (finding NIE z poprzedniego review, znaleziony dzisiaj):**

- `config/patryk_identity.json` (Twój prywatny plik tożsamości — wartości,
  jakość snu, AKSJOMAT 3, `core/identity.py`) **nie był wykluczony** z
  `scripts/pack-founders-archive.sh`. Każda dotychczasowa paczka beta
  (`make pack` / `make pack-sponsor`) mogła zawierać Twoje prywatne dane.
  Naprawione: dodany do excludes + twardej walidacji archiwum (skrypt teraz
  **failuje**, jeśli ten plik jednak trafi do archiwum). PyInstoller build
  też go nie bundluje — `core/identity.py` gracefully degraduje do „soft
  mode” (pusty model) gdy plik nie istnieje, więc to bezpieczne dla testerów
  (dostają Radę bez Twojego osobistego filtra zgodności).
- Ten sam problem sprawdzony i wykluczony dla `db/backend.py` (Postgres —
  nieużywany w boxed/SQLite) i `core/device_seal.py` (już bezpieczny, żyje w
  `~/.architekt-wolnosci/`, poza folderem aplikacji — bez zmian).

**4 — drobna naprawa przy okazji:**

- `src/scripts/tauri-release-env-check.mjs` — porównanie
  `AW_TAURI_SKIP_SIGN_CHECK === "1"` nigdy nie było spełnione przez
  `workflow_dispatch` input w `.github/workflows/tauri-release.yml` (ten
  przekazuje string `"true"`/`"false"`, nie `"1"`) — czyli wybór „pomiń
  walidację certów” w GitHub UI nic nie robił. Naprawione (`"1"|"true"|"yes"`,
  case-insensitive, zgodnie z konwencją reszty repo).
- `.github/workflows/tauri-release.yml` — dodany krok budowy sidecara
  (`build-backend-sidecar.sh`/`.ps1`) PRZED `tauri build` na obu jobach, i
  **nowy job `build-windows` (windows-latest)** — poprzednio istniał
  wyłącznie `build-macos`, czyli CI w ogóle nie potrafiło wyprodukować
  paczki na Windows.

## Workflow — jak zrobić paczkę testową OD ZERA

**Najszybciej: przez CI (jeden przycisk, oba OS-y).**

1. `Actions` → `tauri-release` → `Run workflow`. `skip_sign_check=true` jeśli
   nie masz jeszcze certów (patrz sekcja niżej — dostaniesz niepodpisaną
   paczkę, wystarczającą do zamkniętej grupy testerów).
2. Poczekaj na oba joby (`build-macos`, `build-windows`).
3. Pobierz artefakty `tauri-macos-bundle` (.dmg) i `tauri-windows-bundle`
   (.msi/.exe) z zakładki workflow run.

**Lokalnie (per OS, jeśli wolisz nie używać CI):**

```bash
# Na Macu:
./scripts/build-backend-sidecar.sh
cd src && npm ci && npm run tauri:build
# → src/src-tauri/target/release/bundle/dmg/*.dmg

# Na Windowsie (PowerShell):
.\scripts\windows\build-backend-sidecar.ps1
cd src; npm ci; npm run tauri:build
# → src\src-tauri\target\release\bundle\msi\*.msi
```

## Co zostaje po Twojej stronie (decyzje, nie kod)

To są dokładnie blokery B2 i B3 z poprzedniego review — kod ich nie zamyka,
bo to nie są problemy techniczne, tylko decyzje z realnymi kosztami/kontami:

| # | Co | Koszt/czas | Bez tego |
|---|---|---|---|
| B2-mac | Konto Apple Developer Program + certyfikat Developer ID + notaryzacja (`docs/TAURI_RELEASE.md`) | 99 USD/rok, ~1-2 dni na weryfikację Apple | Gatekeeper blokuje `.app` — tester musi: prawy klik → Otwórz |
| B2-win | Certyfikat podpisu Windows (OV lub EV) | Zwykle 100-400 USD/rok zależnie od CA | SmartScreen ostrzega — tester musi: „Więcej informacji” → „Uruchom mimo to” |
| B3 | SQLCipher (szyfrowanie SQLite at-rest) **lub** świadomy disclaimer w onboardingu, że dane debat leżą lokalnie plaintext | SQLCipher: 1-2 dni implementacji. Disclaimer: <1h | Dane debat (potencjalnie wrażliwe, zdrowotne) leżą jawnie na dysku testera |

**Rekomendacja dla PIERWSZEJ fali testerów (≤10 zaufanych osób):** most bez
certów (`skip_sign_check=true`) + disclaimer zamiast SQLCipher. To dokładnie
to, co poprzedni review nazwał „most na teraz” — nie do publicznej
dystrybucji, ale wystarczające żeby zacząć zbierać feedback **teraz**, bez
czekania na weryfikację Apple czy zakup certyfikatu. Decyzja o SQLCipher /
certyfikatach zostaje osobnym ruchem, gdy będziesz gotów na szerszą falę.

## Czego NIE zrobiono i dlaczego (uczciwie)

Środowisko, w którym pracowałem, nie ma dostępu do sieci PyPI (build
zależności zablokowany na poziomie proxy) i nie utrzymuje procesów/plików
między kolejnymi krokami poza zamontowanym folderem repo — więc **nie
mogłem realnie uruchomić `pyinstaller` i zweryfikować empirycznie, że
`--hidden-import`/`--collect-submodules` w skryptach budujących jest
kompletne.** Dodatkowo PyInstaller i tak nie cross-kompiluje — nawet z pełnym
dostępem do sieci nie zbuduję tu binarki macOS ani Windows (ten sandbox jest
Linuksem).

Co to znaczy praktycznie: kod i skrypty są napisane z pełną precyzją na
podstawie statycznej analizy repo (sprawdziłem realnie, które moduły czytają
pliki po ścieżce względem `__file__`, gdzie są dynamiczne importy, jakie dane
trzeba zbundlować) i oficjalnej dokumentacji Tauri v2 / PyInstaller — ale
**pierwszy realny build (`./scripts/build-backend-sidecar.sh` lokalnie albo
przez CI) jest jednocześnie pierwszym prawdziwym testem tego kodu.** Jeśli
padnie na `--hidden-import`, komunikat błędu (`ModuleNotFoundError` w logu
PyInstallera) mówi wprost, czego brakuje — dopisz do listy w skrypcie i
uruchom ponownie. To jest dokładnie ten sam "spike" co proponował poprzedni
review, tylko że wykonujesz go Ty (lub CI), bo ja nie mam do tego maszyny.

## Najmniejszy następny ruch (≤60 min)

Odpal `Actions → tauri-release → Run workflow` z `skip_sign_check=true` i
poczekaj na oba joby. Jeśli `build-backend-sidecar` padnie w logu — to jest
dokładnie sygnał, którego szukamy (brakujący hidden-import), i naprawa to
dopisanie jednej linijki w skrypcie, nie redesign.
