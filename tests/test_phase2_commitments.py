"""Faza 2: zobowiązania, follow-up 72h, siła cienia przy DELETE/release."""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture
def debate_schematy_id(client_no_redis, fresh_db_path) -> int:
    async def _insert() -> int:
        import aiosqlite

        async with aiosqlite.connect(str(fresh_db_path)) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            cur = await db.execute(
                """
                INSERT INTO debates (category, mode, brief_description, synthesis_text)
                VALUES ('schemat','schematy','Brief testowy ma wystarczajaco slow aby przejsc walidacje API','Synth')
                """,
            )
            await db.commit()
            return int(cur.lastrowid)

    return asyncio.run(_insert())


def test_commitment_schematy_sets_default_followup(client_no_redis, debate_schematy_id: int):
    r = client_no_redis.post(
        "/commitment",
        json={"text": "Krótki krok: jedna godzina na prototyp.", "debate_id": debate_schematy_id},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["trigger_type"] == "manual"
    assert body.get("follow_up_at")

    d = client_no_redis.get(f"/debate/{debate_schematy_id}").json()
    c = d["commitments"][0]
    assert c["follow_up_at"] == body["follow_up_at"]


def test_commitments_due_lists_open_with_followup(client_no_redis, debate_schematy_id: int):
    past = "2020-01-01T00:00:00+00:00"
    client_no_redis.post(
        "/commitment",
        json={
            "text": "Test due window",
            "debate_id": debate_schematy_id,
            "follow_up_at": past,
        },
    )
    r = client_no_redis.get("/commitments/due?within_hours=48")
    assert r.status_code == 200
    items = r.json()["commitments"]
    assert any("Test due window" in str(x.get("text", "")) for x in items)


def test_delete_commitment_always_shadow_422(client_no_redis, debate_schematy_id: int):
    cid = client_no_redis.post(
        "/commitment",
        json={"text": "Do usunięcia", "debate_id": debate_schematy_id},
    ).json()["id"]
    r = client_no_redis.delete(f"/commitment/{cid}")
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["kind"] == "shadow_no_silent_release"


def test_release_commitment_requires_length(client_no_redis, debate_schematy_id: int):
    cid = client_no_redis.post(
        "/commitment",
        json={"text": "Zwolnienie test", "debate_id": debate_schematy_id},
    ).json()["id"]
    r = client_no_redis.post(
        f"/commitment/{cid}/release",
        json={"reason": "za krótko"},
    )
    assert r.status_code == 422

    long_reason = "x" * 35
    r2 = client_no_redis.post(f"/commitment/{cid}/release", json={"reason": long_reason})
    assert r2.status_code == 200


def test_admin_trigger_followups_ok(client_no_redis):
    r = client_no_redis.post("/admin/trigger-followups")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_patch_commitment_complete_ok(client_no_redis, debate_schematy_id: int):
    cid = client_no_redis.post(
        "/commitment",
        json={"text": "Krok do odhaczenia", "debate_id": debate_schematy_id},
    ).json()["id"]
    r = client_no_redis.patch(
        f"/commitment/{cid}/complete",
        json={"evidence_note": "Zrobione", "evidence_url": "https://example.com/x"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    row = client_no_redis.get(f"/debate/{debate_schematy_id}").json()["commitments"]
    mine = next(x for x in row if x["id"] == cid)
    assert mine["status"] == "completed"
    assert "Zrobione" in mine["text"] and "example.com" in mine["text"]


def test_patch_commitment_complete_idempotent_conflict(client_no_redis, debate_schematy_id: int):
    cid = client_no_redis.post(
        "/commitment",
        json={"text": "Już zamknięte", "debate_id": debate_schematy_id},
    ).json()["id"]
    assert client_no_redis.patch(f"/commitment/{cid}/complete", json={}).status_code == 200
    r2 = client_no_redis.patch(f"/commitment/{cid}/complete", json={})
    assert r2.status_code == 409


def test_patch_commitment_complete_404(client_no_redis):
    assert client_no_redis.patch("/commitment/999999/complete", json={}).status_code == 404
