"""Konfiguracja Architekta Wolności v3.0."""

# Bootstrap: `.env` / tryb boxed — JEDYNA implementacja (main.py robi
# `import config` i nic więcej; dedup review 2026-07-16).
#
# Ścieżki:
#   1. zwykły `import env_bootstrap` — działa w dev (root repo na sys.path:
#      uvicorn/pytest/skrypty) ORAZ w trybie frozen PyInstaller
#      (`--hidden-import env_bootstrap`, patrz scripts/build-backend-sidecar.sh);
#   2. fallback po ścieżce (spec_from_file_location) — egzotyczne cwd,
#      import spoza korzenia repo.
#
# Porażka bootstrapu NIE jest cicha: w boxed brak env_bootstrap = brak
# JWT secret i ścieżek danych → 500-tki bez śladu w logach. Stąd stderr.
import sys as _sys

_mod = None
try:  # pragma: no cover
    import env_bootstrap as _mod
except ImportError:
    try:
        import importlib.util
        from pathlib import Path

        _root = Path(__file__).resolve().parent.parent
        _spec = importlib.util.spec_from_file_location(
            "aw_env_bootstrap", _root / "env_bootstrap.py"
        )
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
    except Exception as _e:  # pragma: no cover
        print(f"[config] env_bootstrap nieładowalny po ścieżce: {_e}", file=_sys.stderr)

if _mod is None:  # pragma: no cover
    print(
        "[config] UWAGA: env_bootstrap niedostępny — .env/boxed defaults NIE "
        "zostały załadowane (JWT secret, ścieżki danych).",
        file=_sys.stderr,
    )
else:
    try:
        _mod.load_repo_env()
    except Exception as _e:  # pragma: no cover
        print(f"[config] load_repo_env() padło: {_e}", file=_sys.stderr)

from config.agent_models import (
    AGENT_MODEL_CONFIG,
    HYBRID_MODELS_ENABLED,
    get_model_config,
)

__all__ = [
    "AGENT_MODEL_CONFIG",
    "HYBRID_MODELS_ENABLED",
    "get_model_config",
]
