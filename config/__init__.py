"""Konfiguracja Architekta Wolności v3.0."""

# Bootstrap: `ui/.env` (lub legacy `.env` w root) — wypełnia też „puste” zmienne z shella.
try:  # pragma: no cover
    import importlib.util
    from pathlib import Path

    _root = Path(__file__).resolve().parent.parent
    _spec = importlib.util.spec_from_file_location(
        "aw_env_bootstrap", _root / "env_bootstrap.py"
    )
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _mod.load_repo_env()
except Exception:
    pass

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
