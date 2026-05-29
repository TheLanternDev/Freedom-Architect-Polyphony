#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

Write-Host "Architekt Wolności — backend" -ForegroundColor Cyan
Write-Host "Katalog: $RepoRoot"

$sponsor = Test-Path "BETA_SPONSOR.marker"
if (-not $sponsor -and -not (Test-Path "src\.env")) {
    Write-Host ""
    Write-Host "Brak pliku src\.env" -ForegroundColor Red
    Write-Host "Skopiuj env\src.env.example do src\.env i uzupełnij ANTHROPIC_API_KEY oraz ARCHITEKT_JWT_SECRET."
    Write-Host "Szczegóły: docs\BETA_TESTER_WINDOWS.md"
    exit 1
}

if ($sponsor) {
    Write-Host "Paczka sponsorowana — klucze API wczytuje backend automatycznie." -ForegroundColor DarkGray
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Nie znaleziono python w PATH. Zainstaluj Python 3.12+ z python.org (Add to PATH)." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "Tworzenie venv..."
    & python -m venv venv
}

Write-Host "Instalacja zależności (pip)..."
& "venv\Scripts\python.exe" -m pip install -q -r requirements.txt

Write-Host ""
Write-Host "Start uvicorn na http://127.0.0.1:8000 (Ctrl+C = stop)" -ForegroundColor Green
& "venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
