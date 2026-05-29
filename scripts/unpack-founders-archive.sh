#!/usr/bin/env bash
# unpack-founders-archive.sh — rozpakowuje archiwum founders / beta (architekt-wolnosci-*.tar.gz).
#
# Użycie:
#   ./scripts/unpack-founders-archive.sh plik.tar.gz [katalog_docelowy]
#   make unpack ARCHIVE=plik.tar.gz [DEST=katalog]
#
# Wyklucza przy rozpakowaniu (legacy): node_modules/, dist/, cache Apple.
# Sprawdza core/, agents/, api/, db/, src/package.json.
set -euo pipefail

ARCHIVE="${1:-}"
DEST="${2:-.}"

usage() {
  echo "Użycie: $0 architekt-wolnosci-*.tar.gz [katalog_docelowy]" >&2
  exit 1
}

[[ -n "$ARCHIVE" ]] || usage
[[ -f "$ARCHIVE" ]] || { echo "Brak pliku: $ARCHIVE" >&2; exit 1; }
case "$(basename "$ARCHIVE")" in
  architekt-wolnosci-*.tar.gz) ;;
  *) echo "Oczekiwano architekt-wolnosci-*.tar.gz, dostałem: $(basename "$ARCHIVE")" >&2; exit 1 ;;
esac

mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"
ARCHIVE="$(cd "$(dirname "$ARCHIVE")" && pwd)/$(basename "$ARCHIVE")"

EXCLUDES=(
  --exclude='node_modules'
  --exclude='dist'
  --exclude='.DS_Store'
  --exclude='._*'
  --exclude='.pytest_cache'
  --exclude='.ruff_cache'
)

echo "→ Rozpakowywanie $(basename "$ARCHIVE") do $DEST"

extract_with_progress() {
  if command -v pv >/dev/null 2>&1; then
    pv "$ARCHIVE" | tar -xz "${EXCLUDES[@]}" -f - -C "$DEST"
    return
  fi

  local count=0
  while IFS= read -r _; do
    count=$((count + 1))
    if (( count % 500 == 0 )); then
      echo "  … $count plików"
    fi
  done < <(tar -xzf "$ARCHIVE" "${EXCLUDES[@]}" -C "$DEST" -v 2>&1)
  echo "  … $count plików (gotowe)"
}

extract_with_progress

echo "→ Czyszczenie metadanych Apple"
find "$DEST" \( -name '.DS_Store' -o -name '._*' \) -delete 2>/dev/null || true
if [[ "$(uname -s)" == Darwin ]] && command -v xattr >/dev/null 2>&1; then
  xattr -cr "$DEST" 2>/dev/null || true
fi

echo "→ Walidacja katalogów"
ROOT="$DEST"
for try in "$DEST" "$DEST"/*/; do
  [[ -d "$try" ]] || continue
  try="${try%/}"
  if [[ -d "$try/core" && -d "$try/agents" && -d "$try/api" && -d "$try/db" ]]; then
    ROOT="$try"
    break
  fi
done

missing=0
for dir in core agents api db; do
  if [[ ! -d "$ROOT/$dir" ]]; then
    echo "  ✗ brak: $dir/" >&2
    missing=1
  else
    echo "  ✓ $dir/"
  fi
done

if [[ ! -f "$ROOT/src/package.json" ]]; then
  echo "  ✗ brak: src/package.json" >&2
  missing=1
else
  echo "  ✓ src/package.json"
fi

if (( missing )); then
  echo "Walidacja nie powiodła się." >&2
  exit 1
fi

echo "Gotowe. Katalog projektu: $ROOT"
