"""
Testy endpointów projektów (AKSJOMAT 2 — Doprowadzanie Do Końca).

Pokrywa:
  GET    /projects
  GET    /projects/{id}
  PATCH  /projects/{id}/functionality/{item_id}
  POST   /projects/{id}/complete
  POST   /projects/{id}/archive

Seed bazy odbywa się przez sqlite3 (sync, stdlib) — szybciej i prościej
niż async repo, i nie wymaga LLM ani pętli asyncio.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_dream_and_project(
    db_path,
    *,
    items_done: list[bool],
    status: str = "in_progress",
) -> tuple[str, int, list[int]]:
    """Wstawia 1 dream + 1 projekt z N functionality_items. Zwraca ids."""
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
                "raw brief",
                "rdzenne marzenie testowe",
                "kotwica testowa",
                '["a","b","c"]',
                "[]",
                '{"action":"a","when":"w"}',
                '["kryterium"]',
                '["wymóg"]',
            ),
        )
        cur = conn.execute(
            "INSERT INTO projects (dream_id, status, started_at) VALUES (?,?,?)",
            (dream_id, status, _utcnow_iso()),
        )
        project_id = int(cur.lastrowid)
        item_ids: list[int] = []
        for i, done in enumerate(items_done):
            c = conn.execute(
                """
                INSERT INTO functionality_items (project_id, description, is_done)
                VALUES (?,?,?)
                """,
                (project_id, f"item {i}", 1 if done else 0),
            )
            item_ids.append(int(c.lastrowid))
        conn.commit()
    return dream_id, project_id, item_ids


# ── GET /projects ───────────────────────────────────────────────────────────


def test_list_projects_empty(client_no_redis):
    r = client_no_redis.get("/projects")
    assert r.status_code == 200
    body = r.json()
    assert body["projects"] == []
    assert "limit" in body


def test_list_projects_returns_seeded(client_no_redis, fresh_db_path):
    _seed_dream_and_project(fresh_db_path, items_done=[True, False, False])
    r = client_no_redis.get("/projects")
    assert r.status_code == 200
    projects = r.json()["projects"]
    assert len(projects) == 1
    p = projects[0]
    assert p["status"] == "in_progress"
    assert p["total_items"] == 3
    assert p["completion_ratio"] == pytest.approx(1 / 3, abs=0.01)
    assert "item 1" in p["remaining"]


def test_list_projects_skips_terminal(client_no_redis, fresh_db_path):
    """COMPLETED/ARCHIVED_CONSCIOUSLY nie pojawiają się na liście aktywnych."""
    _seed_dream_and_project(fresh_db_path, items_done=[True], status="completed")
    _seed_dream_and_project(
        fresh_db_path, items_done=[False], status="archived_consciously"
    )
    _seed_dream_and_project(fresh_db_path, items_done=[False], status="in_progress")
    r = client_no_redis.get("/projects")
    projects = r.json()["projects"]
    assert len(projects) == 1
    assert projects[0]["status"] == "in_progress"


# ── GET /projects/{id} ──────────────────────────────────────────────────────


def test_get_project_detail(client_no_redis, fresh_db_path):
    _, pid, _ = _seed_dream_and_project(fresh_db_path, items_done=[False, True])
    r = client_no_redis.get(f"/projects/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == pid
    assert len(body["functionality"]) == 2


def test_get_project_404(client_no_redis):
    r = client_no_redis.get("/projects/99999")
    assert r.status_code == 404


# ── PATCH /projects/{id}/functionality/{item_id} ────────────────────────────


def test_check_functionality_item_marks_done(client_no_redis, fresh_db_path):
    _, pid, items = _seed_dream_and_project(fresh_db_path, items_done=[False, False])
    r = client_no_redis.patch(
        f"/projects/{pid}/functionality/{items[0]}",
        json={"evidence_url": "https://example.com/proof"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    done_flag = body["project"]["functionality"][0]["is_done"]
    assert done_flag in (1, True)


def test_check_functionality_404_on_missing_item(client_no_redis, fresh_db_path):
    _, pid, _ = _seed_dream_and_project(fresh_db_path, items_done=[False])
    r = client_no_redis.patch(
        f"/projects/{pid}/functionality/99999",
        json={"evidence_url": None},
    )
    assert r.status_code == 404


def test_check_functionality_400_when_wrong_project(client_no_redis, fresh_db_path):
    """Pozycja z innego projektu nie może być oznaczona pod fałszywym project_id."""
    _, pid_a, items_a = _seed_dream_and_project(fresh_db_path, items_done=[False])
    _, pid_b, _ = _seed_dream_and_project(fresh_db_path, items_done=[False])
    r = client_no_redis.patch(
        f"/projects/{pid_b}/functionality/{items_a[0]}",
        json={"evidence_url": None},
    )
    assert r.status_code == 400


# ── POST /projects/{id}/complete ────────────────────────────────────────────


def test_complete_blocked_when_incomplete(client_no_redis, fresh_db_path):
    _, pid, _ = _seed_dream_and_project(fresh_db_path, items_done=[True, False])
    r = client_no_redis.post(f"/projects/{pid}/complete")
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["kind"] == "incomplete_functionality"
    assert "item 1" in str(detail["details"]["remaining"])


def test_complete_passes_when_all_done(client_no_redis, fresh_db_path):
    _, pid, _ = _seed_dream_and_project(fresh_db_path, items_done=[True, True])
    r = client_no_redis.post(f"/projects/{pid}/complete")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    # ponownie GET — projekt już nie aktywny → lista pusta
    listing = client_no_redis.get("/projects").json()["projects"]
    assert listing == []


def test_complete_blocked_when_empty_checklist(client_no_redis, fresh_db_path):
    _, pid, _ = _seed_dream_and_project(fresh_db_path, items_done=[])
    r = client_no_redis.post(f"/projects/{pid}/complete")
    assert r.status_code == 422
    assert r.json()["detail"]["kind"] == "empty_functionality_checklist"


def test_complete_404_when_missing(client_no_redis):
    r = client_no_redis.post("/projects/99999/complete")
    assert r.status_code == 404


# ── POST /projects/{id}/archive ─────────────────────────────────────────────


def test_archive_rejects_short_reason(client_no_redis, fresh_db_path):
    _, pid, _ = _seed_dream_and_project(fresh_db_path, items_done=[False])
    r = client_no_redis.post(
        f"/projects/{pid}/archive",
        json={"reason": "za krótko"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["kind"] == "archive_reason_too_short"


def test_archive_passes_with_long_reason(client_no_redis, fresh_db_path):
    _, pid, _ = _seed_dream_and_project(fresh_db_path, items_done=[False])
    reason = (
        "Świadomie odpuszczam ten projekt, bo zmieniły się priorytety życiowe "
        "i nie chcę go ciągnąć z poczucia obowiązku."
    )
    r = client_no_redis.post(f"/projects/{pid}/archive", json={"reason": reason})
    assert r.status_code == 200
    assert r.json()["status"] == "archived_consciously"


def test_archive_missing_reason_422(client_no_redis, fresh_db_path):
    _, pid, _ = _seed_dream_and_project(fresh_db_path, items_done=[False])
    r = client_no_redis.post(f"/projects/{pid}/archive", json={})
    assert r.status_code == 422  # Pydantic — brak wymaganego pola


def test_list_project_commitments_empty(client_no_redis, fresh_db_path):
    _, pid, _ = _seed_dream_and_project(fresh_db_path, items_done=[False])
    r = client_no_redis.get(f"/projects/{pid}/commitments")
    assert r.status_code == 200
    assert r.json()["commitments"] == []
