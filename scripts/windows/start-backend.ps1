# Uruchom backend (venv + uvicorn). Uruchom z katalogu głównego projektu.
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path (Join-Path $Root "main.py"))) {
    $Root = (Get-Location).Path
}
Set-Location $Root

$venvPython = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "→ Tworzenie venv..."
    python -m venv venv
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
}

if (-not (Test-Path (Join-Path $Root "src\.env"))) {
    Write-Warning "Brak src\.env — skopiuj env\src.env.example i uzupełnij klucze (patrz docs\BETA_TESTER_WINDOWS.md)."
}

Write-Host "→ Backend http://127.0.0.1:8000 (Ctrl+C aby zatrzymać)"
& $venvPython -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
