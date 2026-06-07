"""
Wspólne fixture'y dla testów Architekta Wolności v3.2.

Założenia bezpieczeństwa (zero LLM/API calls):
1. ANTHROPIC_API_KEY jest usuwany z env zanim cokolwiek się załaduje.
   Dzięki temu BaseAgent.acontribute() i adistill_dream() spadają do
   deterministycznego fallbacku.
2. Singleton klienta Anthropic w BaseAgent jest resetowany przy każdym
   teście, żeby nie przeciekała instancja z innej sesji.
3. SQLite jest izolowany per test funkcyjny: `ARCHITEKT_DB_PATH` wskazuje
   na `tmp_path`, schema jest ładowana od zera.
4. Redis jest wymuszane na None (jak w v3.0) — testy są deterministyczne
   także przy działającym lokalnie redisie.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Bezpieczeństwo: kasujemy klucze LLM ZANIM zaimportujemy main ───────────
# (env zmienione później nie podziała, bo niektóre klienty są singletonami).
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("XAI_API_KEY", None)
# Nie ładuj `.env` do os.environ pod pytestem — wtedy lokalny `.env` nie
# wstrzykiwałby prawdziwych kluczy w środek testów „bez API”.
os.environ["AW_DISABLE_DOTENV"] = "1"
os.environ["AW_DISABLE_RATE_LIMIT"] = "1"
# Stage 1: guard jest teraz fail-closed gdy brak sekretów.
# Testy integracyjne (nie testujące autentykacji) używają dev-bypass.
# Testy auth (test_auth_*.py) ustawiają własne sekrety przez monkeypatch.
os.environ.setdefault("AW_INSECURE_NO_AUTH", "1")

import pytest
from fastapi.testclient import TestClient

# Pozwala uruchamiać `pytest` z katalogu projektu bez instalacji pakietu.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _disable_anthropic_singleton(monkeypatch):
    """
    Każdy test startuje z czystym BaseAgent._client = None i brakiem
    ANTHROPIC_API_KEY w środowisku.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    try:
        import config.llm_providers as _lp
        monkeypatch.setattr(_lp, "_xai_async_client", None)
    except Exception:
        pass
    try:
        from agents.base_agent import BaseAgent
        monkeypatch.setattr(BaseAgent, "_client", None)
        monkeypatch.setattr(BaseAgent, "_redis", None)
    except Exception:
        pass
    # Cache marzeń w core.dream_architect też resetujemy, żeby fallback był
    # świeży per test (kluczowe dla testów /debate/stream).
    try:
        from core import dream_architect
        dream_architect._DREAM_CACHE.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _isolate_device_seal(tmp_path_factory, monkeypatch):
    """Izoluje pieczęć urządzenia per sesja testowa.

    Bez tego device-gate (api.http_guard → core.device_seal) tworzyłby/odczytywał
    pieczęć w realnym ~/.architekt-wolnosci użytkownika i mógłby zwrócić 423 dla
    testów uruchamianych po zmianie maszyny. Kierujemy pieczęć do tmp — first-run
    zawsze "ok", testy nie dotykają katalogu domowego.
    """
    seal_dir = tmp_path_factory.mktemp("device_seal")
    monkeypatch.setenv("AW_DEVICE_SEAL_DIR", str(seal_dir))


@pytest.fixture
def fresh_db_path(tmp_path, monkeypatch):
    """
    Świeży plik SQLite per test. Podmieniamy `db.connection.DB_PATH` ZANIM
    aplikacja FastAPI zostanie wystartowana (lifespan wywołuje init_db()).
    """
    db_file = tmp_path / "architekt_test.db"
    monkeypatch.setenv("ARCHITEKT_DB_PATH", str(db_file))
    import db.connection as _conn
    monkeypatch.setattr(_conn, "DB_PATH", db_file)
    # main.DB_PATH został zaimportowany przez `from db import DB_PATH`,
    # ale init_db() i get_db() oba czytają `db.connection.DB_PATH`, więc
    # patchowanie tylko tam wystarczy. Główny main.DB_PATH używany jest
    # tylko w /health do logu — bezpiecznie zostawiamy.
    return db_file


@pytest.fixture
def client_no_redis(fresh_db_path) -> TestClient:
    """TestClient z lifespan (świeża DB), z wyłączonym Redisem."""
    import main as main_module
    with TestClient(main_module.app) as c:
        main_module.redis_client = None
        yield c


@pytest.fixture
def client_no_auth_bypass(fresh_db_path, monkeypatch) -> TestClient:
    """TestClient bez AW_INSECURE_NO_AUTH — testuje fail-closed guard.

    Tech-debt fix: zastępuje pattern tworzenia TestClient wewnątrz ciała testu.
    Usuwa AW_INSECURE_NO_AUTH i oba sekrety → guard zwraca 401 dla każdego requestu.
    Testy auth-specific powinny używać tej fixture zamiast ręcznie monkeypatching ENV.
    """
    monkeypatch.delenv("AW_INSECURE_NO_AUTH", raising=False)
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)
    monkeypatch.delenv("ARCHITEKT_JWT_SECRET", raising=False)
    import main as main_module
    with TestClient(main_module.app, raise_server_exceptions=False) as c:
        main_module.redis_client = None
        yield c


@pytest.fixture
def valid_brief_payload() -> dict:
    """Brief który przechodzi walidatory (>= 20 znaków + >= 5 słów)."""
    return {
        "description": (
            "Build a freedom-focused SaaS platform with community features and ethics"
        ),
        "category": "decyzja",
        "mode": "pelna",
        "scale": "startup",
        "budget": "medium",
    }
