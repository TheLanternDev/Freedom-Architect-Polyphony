#!/usr/bin/env bash
# Otwiera media bundle'u w Apple Motion (tytuły/animacje 9:16).
# Motion nie importuje FCPXML osi czasu — otwiera projekt .motn lub media.
# Użycie: ./open-motion.sh [katalog_bundle | plik.motn | plik medialny]
set -euo pipefail
APP="Motion"
BID="com.apple.motionapp"
IG="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

open_in(){
  if open -b "$BID" "$1" 2>/dev/null; then return 0; fi
  if open -a "$APP" "$1" 2>/dev/null; then return 0; fi
  echo "  ✗ Nie znaleziono '$APP' ($BID) — pomiń etap animacji lub zrób tytuły w FCP/Keynote." >&2
  echo "    Cel czeka: $1" >&2
  return 1
}

arg="${1:-}"
if [[ -n "$arg" && -e "$arg" ]]; then
  TARGET="$arg"
else
  BUNDLE="$(ls -dt "$IG"/output/fcp-*/ 2>/dev/null | head -1 || true)"
  if [[ -z "${BUNDLE:-}" ]]; then
    echo "Brak bundle. Najpierw:  cd $IG && .venv/bin/aw-reels fcp-bundle" >&2
    exit 1
  fi
  TARGET="$(ls "$BUNDLE"*.motn 2>/dev/null | head -1 || true)"
  if [[ -z "${TARGET:-}" ]]; then
    TARGET="$(ls -t "$BUNDLE"Clips/*.mp4 2>/dev/null | head -1 || echo "$BUNDLE")"
    echo "Brak .motn — otwieram media do animacji ręcznej. Zbuduj tytuł 1080×1920, 30fps." >&2
  fi
fi

echo "Motion → otwórz: $TARGET"
open_in "$TARGET"
