#!/usr/bin/env bash
# Smoke Tydzień 1: pytest bez LLM / sieci (mocki w conftest).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="python3"; fi
exec "$PY" -m pytest tests/ -q
