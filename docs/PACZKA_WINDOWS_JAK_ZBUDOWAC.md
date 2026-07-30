# Paczka Windows — jak ją zrobić i co powiedzieć odbiorcy

## Dlaczego nie da się jej zbudować na Macu

PyInstaller **nie cross-kompiluje**. Zamrożony backend dla Windows musi powstać
na Windowsie — to nie kwestia flagi, tylko tego, że PyInstaller wkłada do binarki
interpreter i biblioteki systemowe hosta. Tauri na Windows dodatkowo potrzebuje
toolchainu MSVC i bundlerów WiX/NSIS.

Zostają dwie drogi.

## Droga A — GitHub Actions (zalecana, nie potrzebujesz Windowsa)

Workflow `.github/workflows/tauri-release.yml` ma job `build-windows` na
`windows-latest`, który buduje sidecara, potem instalator, i sprawdza że
faktycznie powstał.

1. Wypchnij branch i scal do `main` (workflow czyta `main`):

   ```bash
   git push -u origin fix/review-2026-07-30
   # po review: merge do main
   ```

2. GitHub → zakładka **Actions** → `tauri-release` → **Run workflow**.

3. W polu „Pomiń walidację certyfikatów" wybierz **`true`** — chyba że masz
   kupiony certyfikat Authenticode i wgrane sekrety `WINDOWS_CERTIFICATE` /
   `WINDOWS_CERTIFICATE_PASSWORD`. Bez tego wyboru job celowo przerwie build.

4. Po ~10–20 min pobierz artefakt **`tauri-windows-bundle`**. W środku:
   - `Freedom Architect_0.1.0_x64-setup.exe` — instalator NSIS, **ten wyślij
     kumplowi** (instaluje per-user, bez praw administratora),
   - `Freedom Architect_0.1.0_x64_en-US.msi` — wariant MSI, jeśli ktoś woli.

## Droga B — na maszynie z Windows

```powershell
git clone <repo>; cd architekt-wolnosci
.\scripts\windows\build-backend-sidecar.ps1   # zamraża backend + smoke test /health
cd src
npm ci
$env:VITE_API_URL = "http://127.0.0.1:8000"   # KONIECZNIE — inaczej apka szuka backendu w internecie
npm run tauri:build
```

Instalatory wylądują w `src\src-tauri\target\release\bundle\nsis\` i `\msi\`.

## Co powiedzieć kumplowi

**1. SmartScreen go nastraszy.** Paczka jest niepodpisana (`signingIdentity: null`,
brak certyfikatu Authenticode — kosztuje ~300–500 €/rok). Windows pokaże
„Windows protected your PC". Trzeba kliknąć **More info → Run anyway**.
Antywirus może dodatkowo zgłosić fałszywy alarm na binarce PyInstallera —
to znany, częsty false positive dla `--onefile`.

**2. Potrzebuje WŁASNEGO klucza Anthropic.** Aplikacja działa w modelu BYOK
i w trybie boxed jest fail-closed: bez klucza użytkownika Rada nie startuje
i żaden klucz z Twojej strony nie jest do niej dołączony. Kumpel musi:
- założyć konto na `console.anthropic.com`, doładować kredyty,
- wygenerować klucz API,
- wkleić go w aplikacji: **Połączenie → pole BYOK**.

Klucz trafia do Credential Managera Windows i jest wysyłany per żądanie —
serwer go nie zapisuje. Koszty debat idą na jego kredyty (jedna pełna debata
9 głosów + synteza: rząd kilkudziesięciu groszy do kilku złotych, zależnie
od długości).

**3. Pierwsze uruchomienie jest wolne.** Zamrożony backend rozpakowuje się do
katalogu tymczasowego — 3–15 s przy pierwszym starcie. Aplikacja pokaże baner
„Uruchamiam silnik Rady…". To normalne, nie zawieszenie.

**4. Gdyby coś nie działało**, w aplikacji pojawi się baner z konkretnym powodem
i ścieżką do logów. Logi są w:

```
%APPDATA%\ArchitektWolnosci\logs\
    launcher.log          — start backendu, konflikty portu
    backend-stderr.log    — błędy samego backendu
```

Do zgłoszenia buga wystarczą te dwa pliki + `build_id` z banera.

**5. Port 8000 musi być wolny.** Jeśli kumpel ma tam coś innego (Docker, inny
dev server), aplikacja to wykryje i powie wprost — ale samo tego nie obejdzie,
bo adres backendu jest zapieczony w CSP przy buildzie.

## Czego ta paczka jeszcze nie ma

- **brak podpisu** — SmartScreen przy każdej instalacji, brak auto-update
  (`createUpdaterArtifacts: false`),
- **baza SQLite plaintext** w `%APPDATA%\ArchitektWolnosci\data\` — znany
  otwarty bloker, treść debat nie jest szyfrowana at-rest,
- **sekret sesji w plaintext** (`jwt.secret` w tym samym katalogu; na Windows
  chroniony tylko ACL profilu użytkownika),
- **brak EULA i disclaimerów** — przy wysyłce do kogoś poza kręgiem zaufania
  warto to domknąć (roadmap NOW N1–N6).

Dla kumpla-testera: akceptowalne. Dla sprzedaży: nie.
