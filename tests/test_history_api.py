"""Historia debat, szczegół oraz zobowiązania — endpointy v1.1."""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture
def sample_debate_id(client_no_redis, fresh_db_path) -> int:
    """Wstawia pojedynczą debatę bez marzenia (dream_id NULL).

    Zależy od `client_no_redis`, żeby lifespan FastAPI zdążył wywołać `init_db()`.
    """

    async def _insert() -> int:
        import aiosqlite

        async with aiosqlite.connect(str(fresh_db_path)) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            cur = await db.execute(
                """
                INSERT INTO debates (category, mode, brief_description, synthesis_text, full_synthesis_json)
                VALUES ('decyzja','pelna','Brief testowy ma wystarczajaco slow aby przejsc walidacje API','Synth raw','{"open_questions":["Q1"]}')
                """,
            )
            await db.commit()
            return int(cur.lastrowid)

    return asyncio.run(_insert())


def test_history_empty(client_no_redis):
    r = client_no_redis.get("/history")
    assert r.status_code == 200
    body = r.json()
    assert body["debates"] == []
    assert body.get("query") == ""
    assert body.get("limit") == 40


def test_history_and_detail(client_no_redis, sample_debate_id: int):
    hid = sample_debate_id
    r = client_no_redis.get("/history")
    assert r.status_code == 200
    debates = r.json()["debates"]
    assert len(debates) == 1
    assert debates[0]["id"] == hid

    r2 = client_no_redis.get(f"/debate/{hid}")
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["debate"]["id"] == hid
    assert detail["synthesis_structured"]["open_questions"] == ["Q1"]
    assert detail["voices"] == []


def test_debate_not_found(client_no_redis):
    assert client_no_redis.get("/debate/99999").status_code == 404


def test_debate_export_md(client_no_redis, sample_debate_id: int):
    r = client_no_redis.get(f"/debate/{sample_debate_id}/export.md")
    assert r.status_code == 200
    assert "text/markdown" in (r.headers.get("content-type") or "")
    assert "Architekt Wolności" in r.text
    assert "Brief testowy" in r.text
    assert "Q1" in r.text


def test_debate_export_md_404(client_no_redis):
    assert client_no_redis.get("/debate/99999/export.md").status_code == 404


def test_debate_export_pdf(client_no_redis, sample_debate_id: int):
    r = client_no_redis.get(f"/debate/{sample_debate_id}/export.pdf")
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"
    assert "application/pdf" in (r.headers.get("content-type") or "")


def test_debate_export_pdf_404(client_no_redis):
    assert client_no_redis.get("/debate/99999/export.pdf").status_code == 404


def test_history_search_by_synthesis(client_no_redis, sample_debate_id: int):
    r = client_no_redis.get("/history?q=Synth")
    assert r.status_code == 200
    debates = r.json()["debates"]
    assert len(debates) == 1
    assert debates[0]["id"] == sample_debate_id
    assert r.json().get("query") == "Synth"


def test_history_search_miss(client_no_redis):
    r = client_no_redis.get("/history?q=nieistniejacy_zakres_xyz")
    assert r.status_code == 200
    assert r.json()["debates"] == []


def test_history_limit_clamped(client_no_redis):
    r = client_no_redis.get("/history?limit=99999")
    assert r.status_code == 200
    assert r.json()["limit"] == 200


def test_commitment_create(client_no_redis, sample_debate_id: int):
    payload = {
        "text": "Do piątku: jedna godzina na prototyp bez perfekcjonizmu.",
        "debate_id": sample_debate_id,
        "follow_up_at": "2026-05-14T12:00:00+00:00",
    }
    r = client_no_redis.post("/commitment", json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "open"

    r2 = client_no_redis.get(f"/debate/{sample_debate_id}")
    assert r2.status_code == 200
    cmts = r2.json()["commitments"]
    assert len(cmts) >= 1
    assert cmts[0]["text"] == payload["text"]
