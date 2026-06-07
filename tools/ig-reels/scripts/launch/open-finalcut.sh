#!/usr/bin/env bash
# Otwiera najnowszy (lub wskazany) bundle FCPXML w Final Cut Pro.
# Użycie: ./open-finalcut.sh [katalog_bundle | plik.fcpxml]
set -euo pipefail
APP="Final Cut Pro"
BID="com.apple.FinalCut"
IG="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # .../tools/ig-reels

# Otwiera plik w aplikacji po bundle ID (pewniejsze niż nazwa), fallback na nazwę.
open_in(){  # $1 = plik/cel
  if open -b "$BID" "$1" 2>/dev/null; then return 0; fi
  if open -a "$APP" "$1" 2>/dev/null; then return 0; fi
  echo "  ✗ Nie znaleziono aplikacji '$APP' ($BID). Zainstaluj z App Store lub pomiń etap." >&2
  echo "    Plik czeka: $1" >&2
  return 1
}

arg="${1:-}"
if [[ -n "$arg" && -f "$arg" ]]; then
  XML="$arg"
elif [[ -n "$arg" && -d "$arg" ]]; then
  XML="$arg/Rada-Polyphony.fcpxml"
else
  XML="$(ls -t "$IG"/output/fcp-*/Rada-Polyphony.fcpxml 2>/dev/null | head -1 || true)"
fi

if [[ -z "${XML:-}" || ! -f "$XML" ]]; then
  echo "Brak FCPXML. Najpierw zbuduj bundle:  cd $IG && .venv/bin/aw-reels fcp-bundle" >&2
  exit 1
fi

echo "Final Cut Pro → import: $XML"
open_in "$XML"
