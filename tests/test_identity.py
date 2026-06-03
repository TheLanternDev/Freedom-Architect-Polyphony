"""P1-C3: Aksjomat 3 — core/identity.py (patryk_compliance_check)."""

from __future__ import annotations

from core.identity import ComplianceVerdict, load_identity, patryk_compliance_check


def test_compliance_passes_neutral_text():
    v = patryk_compliance_check("Spokojny następny krok bez presji.")
    assert v.passes is True
    assert isinstance(v, ComplianceVerdict)


def test_compliance_passes_empty():
    v = patryk_compliance_check("")
    assert v.passes is True


def test_compliance_rejects_dissonance():
    v = patryk_compliance_check("Po prostu zapomnij o sobie i rób cokolwiek.")
    assert v.passes is False
    assert any("odmawia" in w for w in v.warnings)


def test_compliance_flags_escape_pattern_with_warning():
    v = patryk_compliance_check("Pomińmy sen i zróbmy sprint przez noc.")
    assert v.passes is True
    assert len(v.warnings) >= 1


def test_load_identity_tolerant_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "core.identity._DEFAULT_PATH",
        tmp_path / "missing.json",
        raising=False,
    )
    load_identity.cache_clear()
    try:
        data = load_identity()
        assert isinstance(data, dict)
    finally:
        load_identity.cache_clear()


def test_verdict_to_payload():
    v = patryk_compliance_check("Test.")
    p = v.to_payload()
    assert "passes" in p and "warnings" in p
