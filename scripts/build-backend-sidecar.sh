#!/usr/bin/env bash
# build-backend-sidecar.sh — zamraża backend (PyInstaller --onefile) i kładzie
# wynikową binarkę jako Tauri sidecar pod właściwą nazwą platformy.
#
# Uruchom z KAŻDEGO wspieranego OS-u osobno (PyInstaller NIE cross-kompiluje —
# binarkę macOS buduje się NA macOS, binarkę Windows NA Windows):
#
#   macOS / Linux:  ./scripts/build-backend-sidecar.sh
#   Windows:        scripts\windows\build-backend-sidecar.ps1
#
# Wymaga: Python 3.12/3.13 na PATH, Rust toolchain (rustc — używany tylko do
# ustalenia target-triple; i tak jest wymagany przez `tauri build`).
#
# Efekt: src/src-tauri/binaries/architekt-backend-<target-triple>[.exe]
#
# Po tym kroku: `cd src && npm run tauri:build` (patrz docs/TAURI_RELEASE.md).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv-sidecar}"
BIN_NAME="architekt-backend"
OUT_DIR="$ROOT/src/src-tauri/binaries"
PORT="${AW_BACKEND_PORT:-8000}"

if ! command -v rustc >/dev/null 2>&1; then
  echo "✗ rustc nie znaleziony — zainstaluj Rust toolchain (i tak wymagany przez 'tauri build')." >&2
  exit 1
fi

TARGET_TRIPLE="$(rustc --print host-tuple 2>/dev/null || true)"
if [[ -z "$TARGET_TRIPLE" ]]; then
  TARGET_TRIPLE="$(rustc -Vv | awk '/^host:/{print $2}')"
fi
if [[ -z "$TARGET_TRIPLE" ]]; then
  echo "✗ nie udało się ustalić target-triple (rustc --print host-tuple / rustc -Vv)." >&2
  exit 1
fi
echo "→ target triple: $TARGET_TRIPLE"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "→ Tworzenie środowiska builda: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "→ Instalacja zależności (requirements.txt + pyinstaller)"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt pyinstaller >/dev/null

# ── Stempel builda (review 2026-07-30) ──────────────────────────────────────
# `config/build_info.py` jest wersjonowany z wartościami "dev"; na czas freeze'u
# NADPISUJEMY go realnymi danymi (PyInstaller wciąga nadpisaną wersję), a po
# buildzie przywracamy z gita, żeby drzewo źródeł nie zostało brudne.
# Trap na EXIT — przywrócenie musi nastąpić także gdy pyinstaller padnie.
BUILD_INFO="$ROOT/config/build_info.py"
GIT_REV="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
GIT_SHORT="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo nogit)"
BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BUILD_ID="${GIT_SHORT}-$(date -u +%Y%m%d%H%M)"
if ! git -C "$ROOT" diff --quiet 2>/dev/null || ! git -C "$ROOT" diff --cached --quiet 2>/dev/null; then
  # Freeze z niescommitowanych zmian: build_id MUSI to mówić, inaczej stempel
  # obiecuje odtwarzalność, której nie ma (rev nie opisuje tego, co w binarce).
  BUILD_ID="${BUILD_ID}-dirty"
fi

restore_build_info() {
  if git -C "$ROOT" ls-files --error-unmatch config/build_info.py >/dev/null 2>&1; then
    git -C "$ROOT" checkout -- config/build_info.py 2>/dev/null || true
  fi
}
trap restore_build_info EXIT

echo "→ Stempel builda: $BUILD_ID"
cat > "$BUILD_INFO" <<PYEOF
"""WYGENEROWANE przez scripts/build-backend-sidecar.sh — nie edytuj ręcznie.

Wersja wersjonowana w gicie ma wartości "dev"; ta jest wstrzykiwana wyłącznie
na czas freeze'u PyInstallera i przywracana zaraz po nim.
"""

from __future__ import annotations

BUILD_ID: str = "$BUILD_ID"
BUILT_AT: str = "$BUILT_AT"
GIT_REV: str = "$GIT_REV"
FROZEN_BUILD: bool = True


def build_info() -> dict[str, object]:
    return {
        "build_id": BUILD_ID,
        "built_at": BUILT_AT,
        "git_rev": GIT_REV,
        "frozen_build": FROZEN_BUILD,
    }
PYEOF

echo "→ pyinstaller build ($BIN_NAME)"
rm -rf "$ROOT/build/sidecar-work" "$ROOT/build/sidecar-dist"
pyinstaller \
  --name "$BIN_NAME" \
  --onefile \
  --clean \
  --noconfirm \
  --distpath "$ROOT/build/sidecar-dist" \
  --workpath "$ROOT/build/sidecar-work" \
  --specpath "$ROOT/build" \
  --copy-metadata anthropic \
  --copy-metadata openai \
  --copy-metadata httpx \
  --copy-metadata tqdm \
  --copy-metadata fastapi \
  --copy-metadata starlette \
  --copy-metadata sentry-sdk \
  --copy-metadata uvicorn \
  --hidden-import env_bootstrap \
  --hidden-import config \
  --hidden-import config.sponsor_runtime_loader \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on \
  --collect-submodules agents \
  --collect-submodules api \
  --collect-submodules core \
  --collect-submodules db \
  --collect-submodules config \
  --collect-submodules business_fa2 \
  --add-data "$ROOT/db/schema.sql${PATHSEP:-:}db" \
  --add-data "$ROOT/db/schema_postgres.sql${PATHSEP:-:}db" \
  --add-data "$ROOT/db/migrations${PATHSEP:-:}db/migrations" \
  --add-data "$ROOT/core/fonts${PATHSEP:-:}core/fonts" \
  "$ROOT/boxed_entry.py"

mkdir -p "$OUT_DIR"
EXT=""
[[ "$TARGET_TRIPLE" == *windows* ]] && EXT=".exe"
DEST="$OUT_DIR/$BIN_NAME-$TARGET_TRIPLE$EXT"
cp "$ROOT/build/sidecar-dist/$BIN_NAME$EXT" "$DEST"
chmod +x "$DEST" 2>/dev/null || true

# Stempel obok binarki — czyta go `src/scripts/check-sidecar-fresh.mjs`, żeby
# wypisać build_id przy buildzie paczki. Gitignorowany razem z binarką.
printf '%s\n%s\n%s\n' "$BUILD_ID" "$BUILT_AT" "$GIT_REV" > "$OUT_DIR/BUILD_STAMP"

# Źródła zamrożone — przywróć wersjonowany fallback od razu (trap zrobiłby to
# i tak na wyjściu, ale smoke test poniżej ma już działać na czystym drzewie).
restore_build_info
trap - EXIT

echo "→ Smoke test: uruchamiam binarkę i sprawdzam GET /health"
# PyInstaller --onefile na cold start rozpakowuje się do /tmp — bywa 12–20s.
AW_APP_DATA_DIR="$ROOT/build/sidecar-smoke-data" AW_BACKEND_PORT="$PORT" "$DEST" &
SMOKE_PID=$!
HEALTH_OK=0
HEALTH_BODY=""
for _ in $(seq 1 60); do
  sleep 0.5
  if HEALTH_BODY="$(curl -fsS "http://127.0.0.1:${PORT}/health" 2>/dev/null)"; then
    HEALTH_OK=1
    break
  fi
done
kill "$SMOKE_PID" 2>/dev/null || true
wait "$SMOKE_PID" 2>/dev/null || true
rm -rf "$ROOT/build/sidecar-smoke-data"

if [[ "$HEALTH_OK" -ne 1 ]]; then
  echo "✗ /health nie odpowiedział w 30s — sprawdź logi powyżej (zwykle brakujący --hidden-import/--collect-submodules)." >&2
  exit 1
fi

# Stempel MUSI być widoczny przez /health. Jeśli nie jest, znaczy że PyInstaller
# nie wciągnął nadpisanego config/build_info.py — czyli cały mechanizm detekcji
# rozjazdu wersji jest martwy, mimo że build „przeszedł".
if [[ "$HEALTH_BODY" != *"$BUILD_ID"* ]]; then
  echo "✗ /health nie zwraca build_id=$BUILD_ID — stempel nie wszedł do binarki." >&2
  echo "  Sprawdź, czy 'config' jest w --collect-submodules i czy config/build_info.py istnieje." >&2
  echo "  Odpowiedź /health: $HEALTH_BODY" >&2
  exit 1
fi

echo "✓ /health OK, build_id=$BUILD_ID — sidecar gotowy: $DEST"
echo "→ Dalej: cd src && npm run tauri:build"
