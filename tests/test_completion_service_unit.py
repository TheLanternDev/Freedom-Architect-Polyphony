"""Pure-function testy `api.services.completion_service`:
helpery językowe + porządkowanie statusów stale projects.
"""

from __future__ import annotations

from api.services import completion_service as cs


def test_shadow_followup_prefix_pl():
    out = cs.shadow_followup_prefix("pl")
    assert "Przełamywanie Schematu" in out
    assert "72 godziny" in out


def test_shadow_followup_prefix_en():
    out = cs.shadow_followup_prefix("en")
    assert "Pattern Break" in out
    assert "72 hours" in out


def test_auto_72h_body_pl_warns_about_silence():
    out = cs.auto_72h_schematy_body("pl")
    assert "Tryb agresywny" in out
    assert "wzorzec" in out


def test_auto_72h_body_en():
    out = cs.auto_72h_schematy_body("en")
    assert "Aggressive mode" in out
    assert "silence is the pattern" in out


def test_stale_nudge_at_risk_pl_is_deega():
    out = cs.stale_nudge_text("at_risk", "pl")
    assert "Deegi" in out or "Deega" in out
    assert "checklistę" in out or "funkcjonalność" in out


def test_stale_nudge_stuck_pl_is_szow():
    out = cs.stale_nudge_text("stuck", "pl")
    assert "Szowa" in out or "Szow" in out
    assert "ucieczka" in out


def test_stale_nudge_at_risk_en_is_deega():
    out = cs.stale_nudge_text("at_risk", "en")
    assert "Deega" in out


def test_stale_nudge_stuck_en_is_szow():
    out = cs.stale_nudge_text("stuck", "en")
    assert "Szow" in out


# ── _stale_status_order ──────────────────────────────────────────────────────


def test_stale_status_order_canonical_ranking():
    assert cs._stale_status_order("dreaming") < cs._stale_status_order("in_progress")
    assert cs._stale_status_order("in_progress") < cs._stale_status_order("at_risk")
    assert cs._stale_status_order("at_risk") < cs._stale_status_order("stuck")


def test_stale_status_order_unknown_status_is_negative():
    assert cs._stale_status_order("completed") == -1
    assert cs._stale_status_order("nonsense") == -1
