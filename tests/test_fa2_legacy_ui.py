"""FA2 tryb (`AW_COUNCIL_MODE=fa2`) — legacy ścieżki UI bez kluczy LLM (mock FA2)."""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_fa2(tmp_path, monkeypatch):
    monkeypatch.setenv("AW_COUNCIL_MODE", "fa2")
    # FA2 współdzieli DB z trybem personal — jedyna realna baza to ARCHITEKT_DB_PATH
    # (+ patch db.connection.DB_PATH niżej). Brak osobnej bazy FA2.
    monkeypatch.setenv("ARCHITEKT_DB_PATH", str(tmp_path / "fa2_main.db"))
    monkeypatch.delenv("FA2_ANTHROPIC_API_KEY", raising=False)
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("XAI_API_KEY", None)
    monkeypatch.setenv("AW_DISABLE_DOTENV", "1")
    monkeypatch.setenv("AW_DISABLE_RATE_LIMIT", "1")

    import db.connection as db_conn
    db_conn.DB_PATH = tmp_path / "fa2_main.db"

    import main as main_module

    with TestClient(main_module.app) as c:
        main_module.redis_client = None
        yield c


def test_fa2_history_200(client_fa2):
    r = client_fa2.get("/history")
    assert r.status_code == 200
    assert r.json()["debates"] == []


def test_fa2_debate_stream_sse_debate_done(client_fa2):
    body = {
        "description": (
            "Build a freedom-focused SaaS platform with community features and ethics "
            "and enough words to pass validation here"
        ),
        "category": "decyzja",
        "mode": "pelna",
        "language": "pl",
    }
    with client_fa2.stream("POST", "/debate/stream", json=body) as r:
        assert r.status_code == 200
        buf = ""
        debate_id = None
        for chunk in r.iter_text():
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                if "event: debate_done" not in block:
                    continue
                line = [ln for ln in block.split("\n") if ln.startswith("data: ")][0]
                payload = json.loads(line[6:])
                debate_id = payload.get("debate_id")
        assert isinstance(debate_id, int)
        assert debate_id >= 1
