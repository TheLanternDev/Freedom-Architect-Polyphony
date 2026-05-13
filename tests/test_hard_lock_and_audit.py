"""
Testy hard-locka MAX_ACTIVE_PROJECTS przy POST /debate/stream
oraz pomocniczych funkcji parsujących/budujących payload Syeza.

Wszystkie testy są offline:
  - ANTHROPIC_API_KEY jest usuwany przez conftest,
  - hard-lock działa PRZED uruchomieniem Rady, więc nawet test, który
    pyta o /debate/stream, nie odpala syntezy LLM.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from core import MAX_ACTIVE_PROJECTS
from main import Brief, _build_syez_payload, _extract_json_block, _try_parse_synthesis_json


def _seed_active_project(db_path) -> int:
    dream_id = str(uuid.uuid4())
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO dreams (
              id, raw_brief, core_dream, value_anchor,
              pillars_json, milestones_json, next_move_json,
              completion_criteria_json, functionality_checklist_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                dream_id,
                "brief",
                "core",
                "value",
                '["a","b","c"]',
                "[]",
                '{"action":"a","when":"w"}',
                '["c"]',
                '["f"]',
            ),
        )
        cur = conn.execute(
            "INSERT INTO projects (dream_id, status, started_at) VALUES (?, 'in_progress', ?)",
            (dream_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return int(cur.lastrowid)


# ── Hard-lock MAX_ACTIVE_PROJECTS ───────────────────────────────────────────


def test_hard_lock_blocks_new_project_at_limit(client_no_redis, fresh_db_path):
    """category=projekt + >= MAX aktywnych → 409."""
    for _ in range(MAX_ACTIVE_PROJECTS):
        _seed_active_project(fresh_db_path)
    resp = client_no_redis.post(
        "/debate/stream",
        json={
            "description": (
                "Nowy projekt który powinien zostać zablokowany przez hard-lock "
                "aktywnych projektów"
            ),
            "category": "projekt",
            "mode": "pelna",
        },
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["kind"] == "active_project_limit"
    assert detail["details"]["limit"] == MAX_ACTIVE_PROJECTS
    assert len(detail["details"]["active_projects"]) == MAX_ACTIVE_PROJECTS


def test_hard_lock_does_not_block_when_below_limit(client_no_redis, fresh_db_path):
    """Poniżej limitu — request nie jest blokowany (200 + SSE)."""
    if MAX_ACTIVE_PROJECTS > 0:
        _seed_active_project(fresh_db_path)
    resp = client_no_redis.post(
        "/debate/stream",
        json={
            "description": (
                "Projekt który mieści się jeszcze w limicie aktywnych projektów"
            ),
            "category": "projekt",
            "mode": "pelna",
        },
    )
    # Nie 409 (możemy startować). Stream sam się zakończy w trybie fallback.
    assert resp.status_code != 409


def test_hard_lock_skipped_for_non_projekt_categories(client_no_redis, fresh_db_path):
    """category != projekt: limit nie obowiązuje (decyzja/marzenie/schemat)."""
    for _ in range(MAX_ACTIVE_PROJECTS + 1):
        _seed_active_project(fresh_db_path)
    for category in ("decyzja", "marzenie", "schemat"):
        resp = client_no_redis.post(
            "/debate/stream",
            json={
                "description": f"Test debate w kategorii {category} ponad limitem aktywnych",
                "category": category,
                "mode": "pelna" if category != "marzenie" else "marzen",
            },
        )
        assert resp.status_code != 409, f"Nieoczekiwany 409 dla category={category}"


# ── _extract_json_block / _try_parse_synthesis_json ─────────────────────────


def test_extract_json_block_from_markdown_fences():
    text = "Preamble\n```json\n{\"a\": 1}\n```\nTrailing"
    block = _extract_json_block(text)
    assert block == '{"a": 1}'


def test_extract_json_block_returns_none_for_garbage():
    assert _extract_json_block("nothing structured here") is None


def test_extract_json_block_from_inline_json():
    text = "Some text {\"key\": \"value\"} after"
    block = _extract_json_block(text)
    assert block == '{"key": "value"}'


def test_try_parse_synthesis_json_happy_path():
    text = "```json\n{\"completion_audit\": {\"x\": 1}}\n```"
    data = _try_parse_synthesis_json(text)
    assert data is not None
    assert "completion_audit" in data


def test_try_parse_synthesis_json_returns_none_on_malformed():
    assert _try_parse_synthesis_json("not even json") is None
    assert _try_parse_synthesis_json("```json\n{ malformed\n```") is None


# ── _build_syez_payload ─────────────────────────────────────────────────────


_VALID_DESCRIPTION = (
    "Test brief sprawdzający budowanie payloadu Syeza w trybie offline"
)


def test_build_syez_payload_contains_aksjomat_requirement():
    brief = Brief(
        description=_VALID_DESCRIPTION,
        category="decyzja",
        mode="pelna",
    )
    out = _build_syez_payload("oryginalny brief", "[Kogit]\nbla", None, brief)
    # AKSJOMAT 2 — treść prozaiczna (bez JSON-owego schema promptu)
    assert "functionality_checklist" in out
    assert "ZAKAZ: JSON" in out
    assert "ZWRÓĆ JEDEN POPRAWNY JSON" not in out
    assert "[Głosy Rady przed syntezą]" in out
    assert "Tryb debaty: pelna" in out


def test_build_syez_payload_includes_dream_when_provided():
    from core.dream_architect import distill_dream

    brief = Brief(
        description=_VALID_DESCRIPTION,
        category="marzenie",
        mode="marzen",
    )
    dream = distill_dream("Test marzenia dla syntezy Syeza.")
    out = _build_syez_payload("brief", "voices", dream, brief)
    assert "ARCHITEKTURA MARZENIA" in out
    assert dream.core_dream in out
