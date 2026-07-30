"""Review-fix 2026-07-16 — Etap 2: cennik z datą + stabilny machine-id."""

from __future__ import annotations

from datetime import date


def test_sonnet5_promo_switches_by_date():
    from config.pricing import price_per_m

    assert price_per_m("claude-sonnet-5", at=date(2026, 8, 31)) == (2.0, 10.0)
    assert price_per_m("claude-sonnet-5", at=date(2026, 9, 1)) == (3.0, 15.0)
    # dziś (2026-07): promo
    assert price_per_m("claude-sonnet-5") in ((2.0, 10.0), (3.0, 15.0))
    assert price_per_m("claude-opus-4-8") == (5.0, 25.0)
    assert price_per_m("nieznany-model") is None


def test_base_agent_cost_uses_shared_pricing():
    """base_agent liczy z config/pricing (nie z własnej, zdublowanej tabeli)."""
    import agents.base_agent as ba
    from config.pricing import price_per_m

    pin, pout = price_per_m("claude-opus-4-8")
    expected = (1000 * pin + 500 * pout) / 1_000_000
    assert ba.BaseAgent._calculate_cost("claude-opus-4-8", 1000, 500) == expected
    assert ba.BaseAgent._calculate_cost("nieznany", 10, 10) == 0.0


def test_shared_llm_prices_derived_from_pricing():
    from config.pricing import price_per_m
    from shared.utils import llm as sl

    per_m = price_per_m(sl.MODELS["sonnet"])
    assert sl._prices_per_1k("sonnet") == (per_m[0] / 1000.0, per_m[1] / 1000.0)
    assert sl._prices_per_1k("nieistniejacy-tier") == (0.0, 0.0)


def test_machine_id_memoized_and_has_fallback(monkeypatch):
    import core.device_seal as ds

    # memoizacja: _read_machine_id woła się raz na proces
    monkeypatch.setattr(ds, "_MACHINE_ID_CACHE", None)
    calls = {"n": 0}

    def fake_read():
        calls["n"] += 1
        return "MID-TEST"

    monkeypatch.setattr(ds, "_read_machine_id", fake_read)
    assert ds._stable_machine_id() == "MID-TEST"
    assert ds._stable_machine_id() == "MID-TEST"
    assert calls["n"] == 1

    # fingerprint deterministyczny przy stabilnym ID
    fp1 = ds._machine_fingerprint()
    fp2 = ds._machine_fingerprint()
    assert fp1 == fp2 and len(fp1) == 64


def test_read_machine_id_fallback_is_persistent_not_node(monkeypatch, tmp_path):
    """Awaria ioreg/rejestru/machine-id NIE wywala startu — fallback to TRWAŁY
    losowy machine.id w katalogu pieczęci (stabilny między wywołaniami),
    NIE platform.node() (który przywracał false-locki mDNS/DHCP)."""
    import platform
    import subprocess

    import core.device_seal as ds

    def boom(*a, **kw):
        raise OSError("brak narzędzia")

    monkeypatch.setenv("AW_DEVICE_SEAL_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "_MACHINE_ID_CACHE", None)  # świeży odczyt, memo wróci po teście
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(platform, "node", lambda: "host-fallback")
    if platform.system() == "Linux":
        # wymuś ścieżkę bez /etc/machine-id (Path używany też przez
        # _persisted_random_id — podmieniamy tylko systemowe ścieżki)
        real_read_text = ds.Path.read_text

        def no_system_files(self, **kw):
            if str(self).startswith(("/etc/", "/var/")):
                raise OSError("brak pliku")
            return real_read_text(self, **kw)

        monkeypatch.setattr(ds.Path, "read_text", no_system_files)
    mid1 = ds._read_machine_id()
    mid2 = ds._read_machine_id()
    assert isinstance(mid1, str) and mid1 != ""
    # trwałość: drugi odczyt zwraca TEN SAM ID (z pliku machine.id)
    assert mid1 == mid2
    assert mid1 != "host-fallback"  # nie hostname
    assert (tmp_path / "machine.id").is_file()


def test_seal_migrates_from_legacy_fingerprint(monkeypatch, tmp_path):
    """Pieczęć zapisana STARYM algorytmem (v1: node+getnode) na tej samej
    maszynie → auto re-seal na v2 zamiast fałszywego 'locked' po update.
    created_at zostaje (re-seal to nie nowa instalacja)."""
    import json

    import core.device_seal as ds

    monkeypatch.setenv("AW_DEVICE_SEAL_DIR", str(tmp_path))
    monkeypatch.setenv("AW_DEVICE_BINDING", "1")

    legacy_fp = "a" * 64
    monkeypatch.setattr(ds, "_legacy_fingerprints", lambda: [legacy_fp])
    (tmp_path / "device.seal").write_text(json.dumps({
        "version": 1, "fingerprint": legacy_fp, "created_at": 123.0,
    }), encoding="utf-8")

    try:
        chk = ds.ensure_and_verify(use_cache=False)
        assert chk.status == "ok"
        seal = json.loads((tmp_path / "device.seal").read_text(encoding="utf-8"))
        assert seal["fp_version"] == ds._FP_VERSION
        assert seal["created_at"] == 123.0
        assert seal["fingerprint"] == ds._machine_fingerprint()

        # obcy fingerprint (nie-legacy) nadal blokuje
        seal["fingerprint"] = "f" * 64
        (tmp_path / "device.seal").write_text(json.dumps(seal), encoding="utf-8")
        chk2 = ds.ensure_and_verify(use_cache=False)
        assert chk2.status == "locked"
    finally:
        # ensure_and_verify ZAWSZE zapisuje wynik do _CACHE (5s TTL) — bez
        # bustowania zostawilibyśmy "locked" procesowi i kolejne testy w
        # suicie (http_guard → 423) padałyby przez pollution, nie przez bug.
        ds._bust_cache()


def test_pricing_prefix_and_unknown_warning(caplog):
    """Datowane snapshoty dziedziczą cenę po prefiksie; nieznany model
    loguje warning (raz) zamiast cichego zera."""
    import logging

    from config.pricing import _WARNED_UNKNOWN, price_per_m

    assert price_per_m("claude-sonnet-5-20260601") is not None
    assert price_per_m("claude-opus-4-8-20260315") == (5.0, 25.0)
    _WARNED_UNKNOWN.discard("model-widmo-x")
    with caplog.at_level(logging.WARNING, logger="config.pricing"):
        assert price_per_m("model-widmo-x") is None
    assert any("model-widmo-x" in r.message for r in caplog.records)
