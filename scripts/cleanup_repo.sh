#!/usr/bin/env bash
# Porządkowanie repo — bezpieczne, odwracalne (wszystko w gicie).
# Uruchom z roota repo:  bash scripts/cleanup_repo.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "→ Usuwam martwy mockup i nieużywany snapshot coverage…"
# redesign.html: martwy mockup (żywe UI = src/src/App.tsx + src/index.html), niereferencjonowany.
rm -f redesign.html
# coverage_baseline.txt: stary snapshot, nigdzie nie używany. Jest TRACKOWANY → git rm.
git rm --quiet --ignore-unmatch coverage_baseline.txt || rm -f coverage_baseline.txt

echo "→ Usuwam zabłąkane binarium wideo w root…"
# final_extended.mp4 (root): untracked, ~4.5 MB, zero referencji w kodzie.
# Kanoniczna lokalizacja artefaktów wideo: tools/ig-reels/ (gitignored). Root = śmieć.
rm -f final_extended.mp4

echo "→ Czyszczę szum OS/Pythona (gitignored, ale zalega w working tree)…"
find . -name ".DS_Store" -not -path "./venv/*" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null || true
rm -f .coverage .coverage.* 2>/dev/null || true

echo "→ Uzupełniam .gitignore (coverage_baseline + binaria wideo w root)…"
grep -qxF "coverage_baseline.txt" .gitignore || echo "coverage_baseline.txt" >> .gitignore
grep -qxF "/final_extended.mp4" .gitignore || echo "/final_extended.mp4" >> .gitignore

echo "✓ Gotowe. Sprawdź:  git status --short"
echo "  Nietknięte (świadomie):"
echo "    • CZYTAJ_MNIE*.txt — używane przez pack-founders (trackowane)"
echo "    • Fragment.pdf — źródło kosmologii projektu"
echo "    • AUDIT_PRODUCTION_READINESS.md — w root celowo (docs/ linkują ../AUDIT...)"
