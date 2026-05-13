"""
Ładowanie zmiennych z pliku `.env` przed resztą aplikacji (FastAPI / agenci).

Domyślna ścieżka: `ui/.env` (jeden plik z sekretami + `VITE_*` dla Vite/Tauri).
Opcjonalnie drugi plik w korzeniu repozytorium (`.env`), jeśli istnieje —
uzupełnia tylko klucze nadal puste po `ui/.env`.

Nadpisanie jawne: `AW_ENV_FILE=/ścieżka/do/pliku` (tylko ten plik, jeśli istnieje).

`python-dotenv` z `override=False` nie nadpisuje istniejących kluczy — nawet
gdy wartość w środowisku to pusty string po `export ANTHROPIC_API_KEY=`.
Ten moduł wypełnia tylko brakujące lub „puste” (same białe znaki) zmienne.
"""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Katalog główny repozytorium (rodzic `env_bootstrap.py`)."""
    return Path(__file__).resolve().parent


def resolve_dotenv_paths() -> list[Path]:
    """Kolejność ładowania: AW_ENV_FILE → ui/.env → .env (legacy)."""
    explicit = os.getenv("AW_ENV_FILE", "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        return [p] if p.is_file() else []

    root = repo_root()
    paths: list[Path] = []
    ui_env = root / "ui" / ".env"
    if ui_env.is_file():
        paths.append(ui_env)
    legacy = root / ".env"
    if legacy.is_file():
        paths.append(legacy)
    return paths


def load_repo_env() -> None:
    if os.getenv("AW_DISABLE_DOTENV", "").strip().lower() in ("1", "true", "yes"):
        return
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    for env_path in resolve_dotenv_paths():
        try:
            vals = dotenv_values(env_path)
        except OSError:
            continue
        for key, val in vals.items():
            if val is None:
                continue
            cur = os.environ.get(key)
            if cur is None or (isinstance(cur, str) and not cur.strip()):
                os.environ[key] = val
