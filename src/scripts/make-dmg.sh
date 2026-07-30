#!/usr/bin/env bash
# make-dmg.sh — deterministyczny DMG przez hdiutil (bez AppleScript/Findera).
# Użycie: ./scripts/make-dmg.sh  (po `tauri build --bundles app`)
set -euo pipefail
cd "$(dirname "$0")/.."

B=src-tauri/target/release/bundle
APP="$B/macos/Freedom Architect.app"
VERSION=$(node -p "require('./src-tauri/tauri.conf.json').version")
OUT="$B/dmg/Freedom Architect_${VERSION}_aarch64.dmg"

[ -d "$APP" ] || { echo "Brak $APP — najpierw: npm run tauri:build"; exit 1; }

S=$(mktemp -d)
cp -R "$APP" "$S/"
ln -s /Applications "$S/Applications"
mkdir -p "$B/dmg"
hdiutil create -volname "Freedom Architect" -srcfolder "$S" -ov -format UDZO "$OUT" -quiet
rm -rf "$S"
echo "DMG: $OUT"
