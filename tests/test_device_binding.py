"""Device binding — pieczęć urządzenia (miękkie powiązanie z maszyną).

Testuje:
  • moduł core.device_seal: first-run, same-machine, copied (locked), reset, disabled
  • integrację HTTP: zablokowane urządzenie → 423 na chronionych ścieżkach,
    ale /device/status, /health, /edition dalej działają (allowlist).
"""

from __future__ import annotations

import json

import pytest

import core.device_seal as ds


@pytest.fixture(autouse=True)
def _reset_device_seal_cache():
    """Izolacja: `ensure_and_verify` cache'uje SealCheck per-proces (5s TTL).

    Bez resetu test dziedziczy stale'owy status (np. "ok") z innego testu, który
    używał innego AW_DEVICE_SEAL_DIR → fałszywe FAIL-e zależne od kolejności i
    okna TTL. Bust przed I po każdym teście zamyka cały ten klas flakiness.
    """
    ds._bust_cache()
    yield
    ds._bust_cache()


def test_seal_lifecycle(monkeypatch, tmp_path):
    monkeypatch.setenv("AW_DEVICE_SEAL_DIR", str(tmp_path / "seal"))
    monkeypatch.setenv("AW_DEVICE_BINDING", "1")

    # first-run → tworzy pieczęć → ok
    c1 = ds.ensure_and_verify()
    assert c1.status == "ok"
    assert ds._seal_path().exists()

    # same machine → ok
    assert ds.ensure_and_verify().status == "ok"

    # symulacja kopii na inny komputer: podmiana fingerprintu w pieczęci
    p = ds._seal_path()
    data = json.loads(p.read_text())
    data["fingerprint"] = "deadbeef" * 8
    p.write_text(json.dumps(data))
    # cache busted by reading fresh (tamper jest poza reset_seal/rebind)
    assert ds.ensure_and_verify(use_cache=False).status == "locked"

    # reset → następny run znów ok
    assert ds.reset_seal() is True
    assert ds.ensure_and_verify().status == "ok"


def test_binding_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("AW_DEVICE_SEAL_DIR", str(tmp_path / "seal"))
    monkeypatch.setenv("AW_DEVICE_BINDING", "0")
    assert ds.ensure_and_verify().status == "disabled"


def test_locked_device_returns_423(monkeypatch, client_no_redis, tmp_path):
    """Gdy pieczęć z innej maszyny → chroniona ścieżka zwraca 423,
    ale /device/status i /health pozostają dostępne (allowlist)."""
    seal_dir = tmp_path / "seal_http"
    monkeypatch.setenv("AW_DEVICE_SEAL_DIR", str(seal_dir))
    monkeypatch.setenv("AW_DEVICE_BINDING", "1")

    # utwórz pieczęć z obcym fingerprintem
    ds.ensure_and_verify()
    p = ds._seal_path()
    data = json.loads(p.read_text())
    data["fingerprint"] = "f00dface" * 8
    p.write_text(json.dumps(data))
    ds._bust_cache()  # tamper jest poza reset/rebind — wymuś świeży odczyt

    # chroniona ścieżka → 423 Locked
    r = client_no_redis.get("/history?limit=5")
    assert r.status_code == 423
    assert r.json().get("code") == "device_locked"

    # allowlist nadal działa
    assert client_no_redis.get("/health").status_code == 200
    st = client_no_redis.get("/device/status")
    assert st.status_code == 200
    assert st.json().get("locked") is True


def test_device_status_ok_when_sealed_here(monkeypatch, client_no_redis, tmp_path):
    monkeypatch.setenv("AW_DEVICE_SEAL_DIR", str(tmp_path / "seal_ok"))
    monkeypatch.setenv("AW_DEVICE_BINDING", "1")
    st = client_no_redis.get("/device/status")
    assert st.status_code == 200
    body = st.json()
    assert body.get("locked") is False
    assert body.get("status") in ("ok", "disabled")
