#!/usr/bin/env bash
# pack-founders-archive.sh — paczka founders / beta (backend + src/, bez sekretów).
#
# Użycie:
#   ./scripts/pack-founders-archive.sh [katalog_wyjściowy] [--sponsor]
#   make pack [OUT=./build]
#   make pack-sponsor [OUT=./build]
#
# --sponsor / PACK_SPONSOR=1:
#   Klucze API z lokalnego src/.env → config/sponsor_payload.py (zakodowane).
#   Znajomy NIE dostaje czytelnych kluczy w .env. NIE commituj archiwum.
#
# Tworzy:
#   architekt-wolnosci-beta-YYYYMMDD-<git>[-sponsor].tar.gz
#   architekt-wolnosci-beta-YYYYMMDD-<git>[-sponsor].zip
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${ROOT}/build"
SPONSOR=0

for arg in "$@"; do
  case "$arg" in
    --sponsor) SPONSOR=1 ;;
    *) OUT_DIR="$arg" ;;
  esac
done

[[ "${PACK_SPONSOR:-}" == "1" ]] && SPONSOR=1

OUT_DIR="$(mkdir -p "$OUT_DIR" && cd "$OUT_DIR" && pwd)"
DATE_STAMP="$(date +%Y%m%d)"
GIT_SHORT="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo "nogit")"
SUFFIX=""
[[ "$SPONSOR" -eq 1 ]] && SUFFIX="-sponsor"
BASENAME="architekt-wolnosci-beta-${DATE_STAMP}-${GIT_SHORT}${SUFFIX}"
TAR_PATH="$OUT_DIR/${BASENAME}.tar.gz"
ZIP_PATH="$OUT_DIR/${BASENAME}.zip"

EXCLUDES=(
  --exclude='.git'
  --exclude='venv'
  --exclude='.venv'
  --exclude='**/node_modules'
  --exclude='**/dist'
  --exclude='**/.vite'
  --exclude='.env'
  --exclude='./src/.env'
  --exclude='config/sponsor_payload.py'
  --exclude='BETA_SPONSOR.marker'
  --exclude='data'
  --exclude='build'
  --exclude='*.tar.gz'
  --exclude='*.zip'
  --exclude='.DS_Store'
  --exclude='._*'
  --exclude='.pytest_cache'
  --exclude='.ruff_cache'
  --exclude='**/__pycache__'
  --exclude='**/*.py[cod]'
  --exclude='src/src-tauri/target'
  --exclude='src-tauri/target'
  --exclude='.idea'
  --exclude='.vscode'
  --exclude='.claude'
  --exclude='.grok'
  --exclude='_tools'
  --exclude='personal_v1'
  --exclude='marketing'
  --exclude='ab_out'
  --exclude='cost_log.jsonl'
  --exclude='events.jsonl'
  --exclude='*.db'
  --exclude='*.db.bak'
  --exclude='Thumbs.db'
)

echo "→ Pakowanie z $ROOT"
[[ "$SPONSOR" -eq 1 ]] && echo "  tryb: SPONSOR (klucze w config/sponsor_payload.py, zakodowane)"
echo "  tar: $TAR_PATH"
echo "  zip: $ZIP_PATH"

BASE_TAR="$OUT_DIR/.pack-base-$$.tar.gz"
STAGING="$OUT_DIR/.pack-staging-$$"
cleanup() { rm -rf "$BASE_TAR" "$STAGING"; }
trap cleanup EXIT

(
  cd "$ROOT"
  tar -czf "$BASE_TAR" "${EXCLUDES[@]}" .
)

mkdir -p "$STAGING"
tar -xzf "$BASE_TAR" -C "$STAGING"

if [[ "$SPONSOR" -eq 1 ]]; then
  "$ROOT/scripts/build-sponsor-embed.py" "$ROOT/src/.env" "$STAGING"
  cp "$ROOT/CZYTAJ_MNIE_SPONSOR.txt" "$STAGING/CZYTAJ_MNIE.txt"
  cat > "$STAGING/docs/BETA_SPONSOROWANA.txt" <<'EOF'
Paczka beta sponsorowana — koszty LLM opłaca osoba, która wysłała Ci tę paczkę.
Nie szukaj kluczy API w plikach — są wbudowane w backend. Nie przekazuj paczki dalej.
EOF
fi

(
  cd "$STAGING"
  tar -czf "$TAR_PATH" .
)

if command -v zip >/dev/null 2>&1; then
  (
    cd "$STAGING"
    zip -rq "$ZIP_PATH" .
  )
else
  echo "⚠ brak polecenia zip — pominięto .zip (tar.gz gotowy)" >&2
fi

echo "→ Walidacja archiwum"
if [[ "$SPONSOR" -eq 0 ]]; then
  for forbidden in '.env' 'src/.env' 'config/sponsor_payload.py' 'BETA_SPONSOR.marker' 'venv/bin/python' 'data/architekt.db'; do
    if tar -tzf "$TAR_PATH" "$forbidden" 2>/dev/null | grep -q .; then
      echo "  ✗ w archiwum jest zabroniony plik: $forbidden" >&2
      exit 1
    fi
  done
else
  for required_sponsor in 'config/sponsor_payload.py' 'BETA_SPONSOR.marker' 'config/sponsor_runtime_loader.py'; do
    if ! tar -tzf "$TAR_PATH" "./$required_sponsor" 2>/dev/null | grep -q .; then
      echo "  ✗ brak w paczce sponsorowanej: $required_sponsor" >&2
      exit 1
    fi
    echo "  ✓ $required_sponsor"
  done
  if tar -xOf "$TAR_PATH" ./src/.env 2>/dev/null | grep -qE '^(ANTHROPIC_API_KEY|XAI_API_KEY|ARCHITEKT_JWT_SECRET|ARCHITEKT_API_KEY)='; then
    echo "  ✗ src/.env zawiera sekrety w paczce sponsorowanej" >&2
    exit 1
  fi
  echo "  ✓ src/.env bez kluczy API"
  if tar -xOf "$TAR_PATH" 2>/dev/null | grep -q 'sk-ant-'; then
    echo "  ✗ w archiwum wykryto jawny prefiks sk-ant-" >&2
    exit 1
  fi
  echo "  ✓ brak jawnych kluczy Anthropic w archiwum"
fi

for required in 'main.py' 'src/package.json' 'requirements.txt' 'scripts/pack-founders-archive.sh' 'CZYTAJ_MNIE.txt' 'docs/BETA_TESTER_WINDOWS.md' 'env/src.env.example' 'scripts/windows/start-backend.ps1' 'scripts/windows/start-ui.ps1'; do
  if ! tar -tzf "$TAR_PATH" "./$required" 2>/dev/null | grep -q .; then
    echo "  ✗ brak wymaganego pliku: $required" >&2
    exit 1
  fi
  echo "  ✓ $required"
done

if [[ -f "$ZIP_PATH" ]]; then
  echo "  ✓ zip: $(du -h "$ZIP_PATH" | awk '{print $1}')"
fi
echo "  ✓ tar: $(du -h "$TAR_PATH" | awk '{print $1}')"

if [[ "$SPONSOR" -eq 1 ]]; then
  echo ""
  echo "⚠  Klucze są zakodowane w paczce — nadal wyślij tylko zaufanej osobie."
  echo "   Po teście rozważ rotację klucza w console.anthropic.com."
fi
echo "Gotowe."
