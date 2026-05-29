#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$UiRoot = Join-Path $RepoRoot "src"
Set-Location $UiRoot

Write-Host "Architekt Wolności — UI (Vite)" -ForegroundColor Cyan
Write-Host "Katalog: $UiRoot"

$node = Get-Command node -ErrorAction SilentlyContinue
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $node -or -not $npm) {
    Write-Host "Nie znaleziono node/npm. Zainstaluj Node.js LTS z nodejs.org." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "node_modules")) {
    Write-Host "Instalacja zależności (npm install)..."
    npm install
}

Write-Host ""
Write-Host "Start dev server (Ctrl+C = stop). Otwórz URL z konsoli (zwykle http://localhost:1420)" -ForegroundColor Green
npm run dev
