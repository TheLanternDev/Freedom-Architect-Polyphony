#!/usr/bin/env bash
# smoke_week1.sh — tygodniowy smoke founders/BYOK (health + opcjonalnie paczka).
#
# Użycie:
#   ./scripts/smoke_week1.sh
#   ./scripts/smoke_week1.sh --pack   # dodatkowo: podgląd pack-founders-archive --help
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== smoke_week1: health =="
export SMOKE_SKIP_DEBATE="${SMOKE_SKIP_DEBATE:-1}"
python3 scripts/smoke_live.py

if [[ "${1:-}" == "--pack" ]]; then
  echo "== smoke_week1: pack script present =="
  test -x scripts/pack-founders-archive.sh || chmod +x scripts/pack-founders-archive.sh
  head -n 12 scripts/pack-founders-archive.sh
fi

echo "OK smoke_week1"
