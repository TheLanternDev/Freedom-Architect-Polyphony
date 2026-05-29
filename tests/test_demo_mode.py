"""Tryb demo interaktywnego (AW_DEMO_MODE)."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

_JWT_SECRET = "jwt-demo-test-secret-min-32-chars!!"


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _run_debate_stream(client: TestClient, headers: dict[str, str]) -> int:
    body = {
        "description": (
            "Chcę przetestować interaktywne demo Architekta Wolności "
            "z własnym briefem i wystarczającą liczbą słów"
        ),
        "category": "decyzja",
        "mode": "codzienny",
        "language": "pl",
    }
    with client.stream("POST", "/debate/stream", headers=headers, json=body) as resp:
        assert resp.status_code == 200, resp.text
        text = "".join(resp.iter_text())
    assert "debate_done" in text
    debate_id = None
    for line in text.splitlines():
        if line.startswith("data: ") and "debate_done" in text:
            pass
    current_event = None
    for line in text.splitlines():
        if line.startswith("event: "):
            current_event = line[len("event: ") :].strip()
        elif line.startswith("data: ") and current_event == "debate_done":
            payload = json.loads(line[len("data: ") :])
            debate_id = payload.get("debate_id")
    assert isinstance(debate_id, int)
    return debate_id


@pytest.fixture
def client_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("AW_DEMO_MODE", "1")
    monkeypatch.setenv("AW_DEMO_MAX_DEBATES", "2")
    monkeypatch.setenv("AW_DEMO_MAX_BRIEF_CHARS", "500")
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", _JWT_SECRET)
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)
    monkeypatch.setenv("ARCHITEKT_DB_PATH", str(tmp_path / "demo.db"))
    monkeypatch.setenv("AW_DISABLE_DOTENV", "1")
    monkeypatch.setenv("AW_DISABLE_RATE_LIMIT", "1")

    import db.connection as db_conn

    db_conn.DB_PATH = tmp_path / "demo.db"

    import main as main_module

    with TestClient(main_module.app) as c:
        main_module.redis_client = None
        yield c


def test_edition_includes_demo_config(client_demo):
    r = client_demo.get("/edition")
    assert r.status_code == 200
    demo = r.json().get("demo")
    assert demo["enabled"] is True
    assert demo["max_debates"] == 2


def test_auth_demo_issues_jwt(client_demo):
    r = client_demo.post("/auth/demo")
    assert r.status_code == 200
    data = r.json()
    assert data["access_token"]
    assert str(data["tenant_id"]).startswith("demo_")


def test_register_blocked_in_demo(client_demo):
    r = client_demo.post(
        "/auth/register",
        json={"username": f"u_{uuid.uuid4().hex[:8]}", "password": "secret123"},
    )
    assert r.status_code == 403


def test_demo_debate_limit_and_status(client_demo):
    r = client_demo.post("/auth/demo")
    token = r.json()["access_token"]
    headers = _auth_headers(token)

    st0 = client_demo.get("/demo/status", headers=headers)
    assert st0.status_code == 200
    assert st0.json()["demo"] is True
    assert st0.json()["debates_remaining"] == 2

    _run_debate_stream(client_demo, headers)

    st1 = client_demo.get("/demo/status", headers=headers)
    assert st1.json()["debates_used"] == 1
    assert st1.json()["debates_remaining"] == 1

    _run_debate_stream(client_demo, headers)

    st2 = client_demo.get("/demo/status", headers=headers)
    assert st2.json()["debates_remaining"] == 0

    body = {
        "description": (
            "Trzecia debata w sesji demo powinna zostać odrzucona "
            "przez limit i mieć wystarczająco dużo słów"
        ),
        "category": "decyzja",
        "mode": "codzienny",
    }
    r3 = client_demo.post("/debate/stream", headers=headers, json=body)
    assert r3.status_code == 403
    assert r3.json()["detail"]["error"] == "demo_limit_reached"


def test_demo_rejects_pelna_mode(client_demo):
    r = client_demo.post("/auth/demo")
    headers = _auth_headers(r.json()["access_token"])
    body = {
        "description": (
            "Próba pełnej Rady w demo powinna paść na walidacji trybu "
            "z odpowiednią liczbą słów w briefie"
        ),
        "category": "decyzja",
        "mode": "pelna",
    }
    resp = client_demo.post("/debate/stream", headers=headers, json=body)
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "demo_mode_restricted"
