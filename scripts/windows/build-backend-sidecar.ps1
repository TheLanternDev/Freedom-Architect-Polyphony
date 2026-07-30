# build-backend-sidecar.ps1 — zamraza backend (PyInstaller --onefile) i kladzie
# wynikowa binarke jako Tauri sidecar pod wlasciwa nazwa platformy.
#
# Uruchom z katalogu glownego repo w PowerShell:
#
#   .\scripts\windows\build-backend-sidecar.ps1
#
# Wymaga: Python 3.12/3.13 na PATH ("Add python.exe to PATH" przy instalacji),
# Rust toolchain (rustc — uzywany do ustalenia target-triple; i tak wymagany
# przez `tauri build`).
#
# Efekt: src\src-tauri\binaries\architekt-backend-<target-triple>.exe
#
# Po tym kroku: cd src; npm run tauri:build   (patrz docs\TAURI_RELEASE.md)

$ErrorActionPreference = "Stop"

$Root = Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
if (-not (Test-Path (Join-Path $Root "main.py"))) {
    # Uklad: scripts\windows\build-backend-sidecar.ps1 -> repo root jest 2 katalogi wyzej
    $Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}
Set-Location $Root

$BinName = "architekt-backend"
$OutDir = Join-Path $Root "src\src-tauri\binaries"
$VenvDir = Join-Path $Root ".venv-sidecar"
$Port = if ($env:AW_BACKEND_PORT) { $env:AW_BACKEND_PORT } else { "8000" }

if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) {
    Write-Error "rustc nie znaleziony — zainstaluj Rust toolchain (i tak wymagany przez 'tauri build')."
}
$TargetTriple = (rustc --print host-tuple 2>$null)
if (-not $TargetTriple) {
    $TargetTriple = ((rustc -Vv | Select-String "host:").Line -split " ")[1]
}
if (-not $TargetTriple) {
    Write-Error "Nie udalo sie ustalic target-triple (rustc --print host-tuple)."
}
Write-Host "-> target triple: $TargetTriple"

if (-not (Test-Path $VenvDir)) {
    Write-Host "-> Tworzenie srodowiska builda: $VenvDir"
    python -m venv $VenvDir
}
$venvPython = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "-> Instalacja zaleznosci (requirements.txt + pyinstaller)"
& $venvPython -m pip install --upgrade pip | Out-Null
& $venvPython -m pip install -r requirements.txt pyinstaller | Out-Null

# ── Stempel builda (review 2026-07-30) ──────────────────────────────────────
# config\build_info.py jest wersjonowany z wartosciami "dev"; na czas freeze'u
# nadpisujemy go realnymi danymi (PyInstaller wciaga nadpisana wersje), po
# buildzie przywracamy z gita — inaczej drzewo zrodel zostaje brudne.
$BuildInfo = Join-Path $Root "config\build_info.py"
$GitRev = (git -C $Root rev-parse HEAD 2>$null); if (-not $GitRev) { $GitRev = "unknown" }
$GitShort = (git -C $Root rev-parse --short HEAD 2>$null); if (-not $GitShort) { $GitShort = "nogit" }
$BuiltAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$BuildId = "$GitShort-" + (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmm")
git -C $Root diff --quiet 2>$null; $dirtyWork = ($LASTEXITCODE -ne 0)
git -C $Root diff --cached --quiet 2>$null; $dirtyIndex = ($LASTEXITCODE -ne 0)
if ($dirtyWork -or $dirtyIndex) {
    # Freeze z niescommitowanych zmian — build_id musi to mowic, bo rev nie
    # opisuje tego, co realnie wlecialo do binarki.
    $BuildId = "$BuildId-dirty"
}

function Restore-BuildInfo {
    git -C $Root ls-files --error-unmatch config/build_info.py 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        git -C $Root checkout -- config/build_info.py 2>$null | Out-Null
    }
}

Write-Host "-> Stempel builda: $BuildId"
@"
"""WYGENEROWANE przez scripts\windows\build-backend-sidecar.ps1 — nie edytuj recznie."""

from __future__ import annotations

BUILD_ID: str = "$BuildId"
BUILT_AT: str = "$BuiltAt"
GIT_REV: str = "$GitRev"
FROZEN_BUILD: bool = True


def build_info() -> dict[str, object]:
    return {
        "build_id": BUILD_ID,
        "built_at": BUILT_AT,
        "git_rev": GIT_REV,
        "frozen_build": FROZEN_BUILD,
    }
"@ | Set-Content -Path $BuildInfo -Encoding UTF8

Write-Host "-> pyinstaller build ($BinName)"
$distPath = Join-Path $Root "build\sidecar-dist"
$workPath = Join-Path $Root "build\sidecar-work"
$specPath = Join-Path $Root "build"
Remove-Item -Recurse -Force $distPath, $workPath -ErrorAction SilentlyContinue

& $venvPython -m PyInstaller `
    --name $BinName `
    --onefile `
    --clean `
    --noconfirm `
    --distpath $distPath `
    --workpath $workPath `
    --specpath $specPath `
    --copy-metadata anthropic `
    --copy-metadata openai `
    --copy-metadata httpx `
    --copy-metadata tqdm `
    --copy-metadata fastapi `
    --copy-metadata starlette `
    --copy-metadata sentry-sdk `
    --copy-metadata uvicorn `
    --hidden-import env_bootstrap `
    --hidden-import config `
    --hidden-import config.sponsor_runtime_loader `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.loops.auto `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan.on `
    --collect-submodules agents `
    --collect-submodules api `
    --collect-submodules core `
    --collect-submodules db `
    --collect-submodules config `
    --collect-submodules business_fa2 `
    --add-data "$(Join-Path $Root 'db\schema.sql');db" `
    --add-data "$(Join-Path $Root 'db\schema_postgres.sql');db" `
    --add-data "$(Join-Path $Root 'db\migrations');db/migrations" `
    --add-data "$(Join-Path $Root 'core\fonts');core/fonts" `
    "$(Join-Path $Root 'boxed_entry.py')"

if ($LASTEXITCODE -ne 0) {
    Restore-BuildInfo
    Write-Error "PyInstaller build nie powiodl sie (kod $LASTEXITCODE)."
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$dest = Join-Path $OutDir "$BinName-$TargetTriple.exe"
Copy-Item (Join-Path $distPath "$BinName.exe") $dest -Force

# Stempel obok binarki — czyta go src\scripts\check-sidecar-fresh.mjs.
"$BuildId`n$BuiltAt`n$GitRev" | Set-Content -Path (Join-Path $OutDir "BUILD_STAMP") -Encoding UTF8

# Zrodla zamrozone — przywroc wersjonowany fallback, zeby smoke test i dalsze
# kroki chodzily na czystym drzewie.
Restore-BuildInfo

Write-Host "-> Smoke test: uruchamiam binarke i sprawdzam GET /health"
$smokeDataDir = Join-Path $Root "build\sidecar-smoke-data"
$env:AW_APP_DATA_DIR = $smokeDataDir
$env:AW_BACKEND_PORT = $Port
$proc = Start-Process -FilePath $dest -PassThru -WindowStyle Hidden

$healthOk = $false
$healthBody = ""
# 60 x 500 ms = 30 s. Bylo 20 (10 s) — a PyInstaller --onefile na zimnym starcie
# rozpakowuje sie 12-20 s, wiec smoke test potrafil padac bez zadnej realnej
# usterki (wariant bash mial 30 s od zawsze — rozjazd naprawiony).
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $healthOk = $true; $healthBody = $resp.Content; break }
    } catch {
        # jeszcze nie wstal — ponow
    }
}

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $smokeDataDir -ErrorAction SilentlyContinue
Remove-Item Env:\AW_APP_DATA_DIR, Env:\AW_BACKEND_PORT -ErrorAction SilentlyContinue

if (-not $healthOk) {
    Write-Error "/health nie odpowiedzial w 30s — sprawdz logi powyzej (zwykle brakujacy --hidden-import/--collect-submodules)."
}

# Stempel MUSI byc widoczny przez /health — inaczej detekcja rozjazdu wersji
# jest martwa, mimo ze build "przeszedl".
if ($healthBody -notlike "*$BuildId*") {
    Write-Error "/health nie zwraca build_id=$BuildId — stempel nie wszedl do binarki. Sprawdz --collect-submodules config. Odpowiedz: $healthBody"
}

Write-Host "OK /health OK, build_id=$BuildId — sidecar gotowy: $dest"
Write-Host "-> Dalej: cd src; npm run tauri:build"
