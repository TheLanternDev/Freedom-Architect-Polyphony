#!/usr/bin/env bash
# Otwiera Keynote do budowy plansz/tytułów reela (9:16 → eksport do FCP/Compressor).
# Keynote nie czyta FCPXML — otwiera .key lub pusty dokument z importem portretów.
# Użycie: ./open-keynote.sh [plik.key | katalog_bundle]
set -euo pipefail
APP="Keynote"
BID="com.apple.iWork.Keynote"
IG="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

open_in(){
  if [[ -n "${1:-}" ]]; then open -b "$BID" "$1" 2>/dev/null && return 0; open -a "$APP" "$1" 2>/dev/null && return 0
  else open -b "$BID" 2>/dev/null && return 0; open -a "$APP" 2>/dev/null && return 0; fi
  echo "  ✗ Nie znaleziono '$APP' ($BID). Zainstaluj Keynote lub pomiń etap plansz." >&2
  return 1
}

arg="${1:-}"
if [[ -n "$arg" && -f "$arg" ]]; then
  open_in "$arg"; echo "Keynote → $arg"; exit $?
fi

if [[ -n "$arg" && -d "$arg" ]]; then SRC="$arg/Portraits"; else
  BUNDLE="$(ls -dt "$IG"/output/fcp-*/ 2>/dev/null | head -1 || true)"
  SRC="${BUNDLE:-$IG/assets/council}"
fi

echo "Keynote: utwórz dokument 1080×1920 (Slide Size → Custom)."
echo "Importuj portrety z: $SRC"
echo "Eksport: Plik → Eksportuj → Wideo/Obraz, 1080×1920 → do FCP lub Compressor."
open_in
