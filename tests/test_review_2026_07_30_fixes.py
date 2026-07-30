"""Regresje dla napraw z review 2026-07-30.

Każdy test przypina JEDNĄ konkretną usterkę, żeby nie wróciła:
  • JWT secret: wyścig dwóch first-runów dawał DWA różne sekrety
  • AW_DISABLE_DOTENV czytało dotenv (config.env) mimo flagi
  • nagłówki bezpieczeństwa pomijały tryb boxed
  • revoke w boxed był no-opem (brak Redis → fail-open bez blocklisty)
  • _fernet() mógł rzucić ValueError na pusty/uszkodzony klucz
  • _int_env cicho przycinał wartości poza zakresem
"""

from __future__ import annotations

import importlib
import os

# pytest importowany tylko gdy potrzebny — ten plik używa asyncio.run(),
# zgodnie z konwencją reszty suite (patrz tests/test_account_rodo.py).


# ── JWT secret: atomowość i stabilność ──────────────────────────────────────


def test_jwt_secret_stable_between_calls(tmp_path):
    """Drugie wywołanie MUSI zwrócić ten sam sekret — inaczej restart wylogowuje."""
    import env_bootstrap as eb

    first = eb._ensure_jwt_secret(tmp_path)
    second = eb._ensure_jwt_secret(tmp_path)
    assert first == second
    assert first and len(first) >= 32
    assert (tmp_path / "jwt.secret").is_file()


def test_jwt_secret_file_is_0600_on_posix(tmp_path):
    import env_bootstrap as eb

    eb._ensure_jwt_secret(tmp_path)
    mode = (tmp_path / "jwt.secret").stat().st_mode & 0o777
    if os.name == "posix":
        assert mode == 0o600, f"sekret sesji z uprawnieniami {oct(mode)}"


def test_jwt_secret_race_loser_reads_winner_value(tmp_path, monkeypatch):
    """Symulacja wyścigu dwóch first-runów: przegrany O_EXCL MUSI odczytać
    sekret zwycięzcy, a nie zostać ze swoim.

    Wcześniejszy append do `config.env` nie miał żadnej semantyki wykluczania:
    oba procesy generowały własny sekret i dopisywały OBA, więc tokeny wydane
    przez jeden były odrzucane przez drugi w tym samym czasie."""
    import env_bootstrap as eb

    path = tmp_path / "jwt.secret"
    winner_secret = "w" * 64
    real_open = os.open

    def fake_open(p, flags, mode=0o777):
        # W momencie, w którym „nasz" proces próbuje utworzyć plik z O_EXCL,
        # zwycięzca właśnie go utworzył i zapisał.
        if flags & os.O_EXCL and str(p) == str(path):
            path.write_text(winner_secret, encoding="utf-8")
            raise FileExistsError(17, "File exists")
        return real_open(p, flags, mode)

    monkeypatch.setattr(os, "open", fake_open)
    loser = eb._ensure_jwt_secret(tmp_path)
    assert loser == winner_secret, "przegrany wyścigu został ze swoim sekretem"


# ── AW_DISABLE_DOTENV ───────────────────────────────────────────────────────


def test_disable_dotenv_skips_config_env_in_boxed(tmp_path, monkeypatch):
    """Flaga „nie czytaj dotenv" nie może czytać config.env."""
    import env_bootstrap as eb

    (tmp_path / "config.env").write_text("AW_TEST_SENTINEL=z_pliku\n", encoding="utf-8")
    monkeypatch.setenv("AW_APP_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("AW_TEST_SENTINEL", raising=False)
    monkeypatch.setattr(eb, "is_frozen", lambda: True)

    eb._apply_boxed_defaults(read_dotenv=False)
    assert os.environ.get("AW_TEST_SENTINEL") is None

    eb._apply_boxed_defaults(read_dotenv=True)
    assert os.environ.get("AW_TEST_SENTINEL") == "z_pliku"


def test_boxed_defaults_still_set_paths_without_dotenv(tmp_path, monkeypatch):
    """Nawet bez czytania dotenv paczka MUSI dostać ścieżki danych i sekret."""
    import env_bootstrap as eb

    monkeypatch.setenv("AW_APP_DATA_DIR", str(tmp_path))
    for k in ("ARCHITEKT_DB_PATH", "ARCHITEKT_JWT_SECRET", "COST_LOG_PATH"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(eb, "is_frozen", lambda: True)

    eb._apply_boxed_defaults(read_dotenv=False)
    assert str(tmp_path) in os.environ["ARCHITEKT_DB_PATH"]
    assert os.environ["ARCHITEKT_JWT_SECRET"].strip()


# ── Nagłówki bezpieczeństwa w boxed ─────────────────────────────────────────


def test_security_headers_cover_boxed(monkeypatch):
    """Sprzedawane pudełko MUSI mieć nosniff/X-Frame-Options.

    To jedyny wariant, w którym webview ma IPC do Keychaina (get_llm_key)."""
    from api import settings

    monkeypatch.setenv("AW_ENV", "boxed")
    assert settings.is_boxed() is True
    assert settings.is_production() is False
    assert settings.security_hardened() is True, (
        "boxed musi łapać się pod nagłówki bezpieczeństwa"
    )


def test_boxed_is_not_infrastructural_production(monkeypatch):
    """Boxed zaostrza BEZPIECZEŃSTWO, ale nie udaje produkcji infrastrukturalnie.

    Gdyby `is_production()` zaczęło łapać boxed, paczka wymagałaby Postgresa
    i AW_CORS_ORIGINS — czyli nie wystartowałaby wcale. To rozróżnienie jest
    celowe i łatwe do zepsucia jednym „uproszczeniem"."""
    from api import settings

    monkeypatch.setenv("AW_ENV", "boxed")
    assert settings.production_preflight_errors() == []
    assert settings.security_hardened() is True


# ── Lokalna blocklista JTI (boxed bez Redis) ─────────────────────────────────


def test_local_jti_blocklist_roundtrip(tmp_path, monkeypatch):
    """W boxed bez Redis revoke MUSI być trwały, inaczej 'Wyloguj' kłamie."""
    from api import auth_identity as ai

    monkeypatch.setenv("AW_JTI_BLOCKLIST_PATH", str(tmp_path / "jti.json"))
    assert ai._local_blocklist_has("jti-1") is False
    assert ai._local_blocklist_add("jti-1", 60) is True
    assert ai._local_blocklist_has("jti-1") is True
    assert ai._local_blocklist_has("jti-2") is False


def test_local_jti_blocklist_expires_and_prunes(tmp_path, monkeypatch):
    """Przeterminowany wpis nie blokuje i nie przeżywa kolejnego zapisu —
    inaczej plik rósłby bez limitu przez cały okres życia instalacji."""
    import json
    import time as _t

    from api import auth_identity as ai

    path = tmp_path / "jti.json"
    monkeypatch.setenv("AW_JTI_BLOCKLIST_PATH", str(path))

    # Wpis wygasły 10 s temu — zapisany wprost, bo API wymusza ttl >= 1 s.
    path.write_text(json.dumps({"przedawniony": _t.time() - 10}), encoding="utf-8")
    assert ai._local_blocklist_has("przedawniony") is False

    ai._local_blocklist_add("swiezy", 60)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "swiezy" in data
    assert "przedawniony" not in data, "wygasły wpis nie został usunięty przy zapisie"


def test_boxed_jti_check_uses_local_blocklist(tmp_path, monkeypatch):
    """Boxed bez Redis: revoke MUSI być trwały (wcześniej fail-open = no-op)."""
    import asyncio

    from api import auth_identity as ai

    monkeypatch.setenv("AW_ENV", "boxed")
    monkeypatch.setenv("AW_JTI_BLOCKLIST_PATH", str(tmp_path / "jti.json"))
    monkeypatch.setattr("api.runtime.get_redis", lambda: None, raising=False)

    assert asyncio.run(ai.is_jti_blocked("abc")) is False
    assert asyncio.run(ai.block_jti("abc", 60)) is True
    assert asyncio.run(ai.is_jti_blocked("abc")) is True


def test_non_boxed_dev_stays_fail_open(tmp_path, monkeypatch):
    """Dev bez Redis zostaje fail-open — nie wprowadzamy lokalnej blocklisty
    tam, gdzie Redis jest po prostu opcjonalny."""
    import asyncio

    from api import auth_identity as ai

    monkeypatch.setenv("AW_ENV", "development")
    monkeypatch.setenv("AW_JTI_BLOCKLIST_PATH", str(tmp_path / "jti.json"))
    monkeypatch.setattr("api.runtime.get_redis", lambda: None, raising=False)

    assert asyncio.run(ai.block_jti("x", 60)) is False
    assert asyncio.run(ai.is_jti_blocked("x")) is False


# ── Cache: klucz Fernet nie może wywalić requestu ───────────────────────────


def test_fernet_returns_none_on_corrupt_key(tmp_path, monkeypatch):
    """Pusty/uszkodzony klucz → None (cache off), NIE ValueError w górę.

    Poprzednio `Fernet(b"")` leciał z _save_disk, gdzie łapany był tylko OSError."""
    import shared.utils.cache as c

    key = tmp_path / "cache.key"
    key.write_bytes(b"")  # dokładnie stan z okna wyścigu O_EXCL/write
    monkeypatch.setattr(c, "_KEY_FILE", key)
    monkeypatch.setattr(c, "_HOME", tmp_path)
    assert c._fernet() is None


# ── _int_env: clamp musi być głośny ─────────────────────────────────────────


def test_int_env_warns_on_clamp(monkeypatch, capsys):
    monkeypatch.setenv("AW_TEST_INT", "99999")
    am = importlib.import_module("config.agent_models")
    val = am._int_env("AW_TEST_INT", 2048, lo=1024, hi=16000)
    assert val == 16000
    assert "poza dozwolonym zakresem" in capsys.readouterr().err


def test_int_env_warns_on_garbage(monkeypatch, capsys):
    monkeypatch.setenv("AW_TEST_INT", "dużo")
    am = importlib.import_module("config.agent_models")
    assert am._int_env("AW_TEST_INT", 2048, lo=1024, hi=16000) == 2048
    assert "nie jest liczbą" in capsys.readouterr().err
