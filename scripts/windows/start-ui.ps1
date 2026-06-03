# Uruchom UI (npm install + dev server). Drugie okno PowerShell obok backendu.
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path (Join-Path $Root "main.py"))) {
    $Root = (Get-Location).Path
}
$Src = Join-Path $Root "src"
if (-not (Test-Path (Join-Path $Src "package.json"))) {
    Write-Error "Nie znaleziono src\package.json w $Root"
}
Set-Location $Src

if (-not (Test-Path "node_modules")) {
    Write-Host "→ npm install (pierwsze uruchomienie)..."
    npm install
}

Write-Host "→ UI dev server (adres w konsoli, zwykle http://localhost:1420)"
npm run dev
