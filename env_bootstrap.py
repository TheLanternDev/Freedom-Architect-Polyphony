"""
Ładowanie zmiennych z pliku `.env` przed resztą aplikacji (FastAPI / agenci).

JEDYNE źródło prawdy sekretów/kluczy API: `.env` w korzeniu repozytorium.
`src/.env` służy WYŁĄCZNIE frontendowi (Vite/Tauri) i powinien zawierać tylko
zmienne `VITE_*`; uzupełnia jedynie klucze nadal puste po korzeniowym `.env`.

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
    """Kolejność ładowania: AW_ENV_FILE → .env (źródło prawdy) → src/.env (tylko VITE_*)."""
    explicit = os.getenv("AW_ENV_FILE", "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        return [p] if p.is_file() else []

    root = repo_root()
    paths: list[Path] = []
    primary = root / ".env"  # JEDYNE źródło prawdy sekretów/kluczy API (override=False → wygrywa)
    if primary.is_file():
        paths.append(primary)
    src_env = root / "src" / ".env"  # tylko VITE_* dla Vite/Tauri; uzupełnia brakujące
    if src_env.is_file():
        paths.append(src_env)
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

    try:
        from config.sponsor_runtime_loader import apply_sponsor_secrets_if_marked

        apply_sponsor_secrets_if_marked(repo_root())
    except ImportError:
        pass
