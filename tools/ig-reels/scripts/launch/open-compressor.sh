#!/usr/bin/env bash
# Otwiera gotowy reel w Compressorze do eksportu IG (1080×1920, H.264).
# Użycie: ./open-compressor.sh [plik.mp4 | katalog_sesji]
set -euo pipefail
APP="Compressor"
BID="com.apple.Compressor"
IG="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

open_in(){
  if open -b "$BID" "$1" 2>/dev/null; then return 0; fi
  if open -a "$APP" "$1" 2>/dev/null; then return 0; fi
  echo "  ✗ Nie znaleziono '$APP' ($BID). Alternatywa: eksport z Final Cut (Master File)." >&2
  echo "    Plik czeka: $1" >&2
  return 1
}

arg="${1:-}"
if [[ -n "$arg" && -f "$arg" ]]; then
  MP4="$arg"
elif [[ -n "$arg" && -d "$arg" ]]; then
  MP4="$(ls -t "$arg"/*-ready.mp4 "$arg"/*.mp4 2>/dev/null | head -1 || true)"
else
  MP4="$(ls -t "$IG"/output/*/*-ready.mp4 2>/dev/null | head -1 || true)"
fi

if [[ -z "${MP4:-}" || ! -f "$MP4" ]]; then
  echo "Brak *-ready.mp4. Najpierw wyrenderuj reel (run_today.sh / aw-reels publish)." >&2
  exit 1
fi

echo "Compressor → źródło: $MP4"
echo "Ustaw setting: H.264, 1080×1920, 30fps. Dodaj job ręcznie po otwarciu."
open_in "$MP4"
