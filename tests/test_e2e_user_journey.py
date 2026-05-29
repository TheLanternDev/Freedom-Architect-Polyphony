"""
E2E: pełny cykl życia użytkownika (TestClient, fallback offline — bez LLM).

Rejestracja → login → debata → kontynuacja wątku → eksport RODO → usunięcie konta
→ login po usunięciu (401).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest

_JWT_SECRET = "jwt-unit-secret-key-min-32chars!"
_CONFIRM_DELETE = "USUŃ MOJE KONTO"
_PASSWORD = "securepass123"


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _last_debate_done_id(sse_body: str) -> int:
    current_event: str | None = None
    debate_id: int | None = None
    for line in sse_body.splitlines():
        if line.startswith("event: "):
            current_event = line[len("event: ") :].strip()
        elif line.startswith("data: ") and current_event == "debate_done":
            payload = json.loads(line[len("data: ") :])
            raw = payload.get("debate_id")
            if raw is not None:
                debate_id = int(raw)
    assert debate_id is not None, "brak debate_id w evencie debate_done"
    return debate_id


def _run_debate_stream(client, headers: dict[str, str], description: str) -> int:
    payload = {
        "description": description,
        "category": "decyzja",
        "mode": "codzienny",
    }
    with client.stream("POST", "/debate/stream", headers=headers, json=payload) as resp:
        assert resp.status_code == 200, resp.text
        body = "".join(resp.iter_text())
    assert "debate_done" in body
    assert "agent_done" in body or "agent_error" in body
    return _last_debate_done_id(body)


@pytest.fixture
def e2e_auth_env(monkeypatch):
    monkeypatch.setenv("ARCHITEKT_JWT_SECRET", _JWT_SECRET)
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _pbkdf2_auth_without_argon2(monkeypatch):
    """Rejestracja/login bez argon2-cffi (środowiska CI bez pełnego venv)."""
    from api.routers import auth as auth_mod

    salt = "e2e_auth_salt"

    def _pbkdf2(password: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100_000
        ).hex()

    monkeypatch.setattr(auth_mod, "_hash_password_argon2", _pbkdf2)
    monkeypatch.setattr(auth_mod, "_is_argon2_hash", lambda _h: False)
    monkeypatch.setattr(auth_mod, "_hash_password_pbkdf2", lambda p, _s: _pbkdf2(p))


@pytest.fixture(autouse=True)
def _no_redis_e2e(monkeypatch):
    import main as main_module

    monkeypatch.setattr(main_module, "redis_client", None)

    def _no_redis():
        return None

    try:
        import api.runtime as rt

        monkeypatch.setattr(rt, "get_redis", _no_redis)
    except Exception:
        pass


def test_full_user_journey_register_to_account_deletion(
    client_no_redis, fresh_db_path, e2e_auth_env
):
    username = f"e2e_{uuid.uuid4().hex[:12]}"
    register_body = {
        "username": username,
        "password": _PASSWORD,
        "display_name": "E2E Podróżnik",
    }

    reg = client_no_redis.post("/auth/register", json=register_body)
    assert reg.status_code == 200, reg.text
    reg_json = reg.json()
    assert reg_json["access_token"]
    assert reg_json["tenant_id"]

    login = client_no_redis.post(
        "/auth/login",
        json={"username": username, "password": _PASSWORD},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = _auth_headers(token)

    debate_1 = _run_debate_stream(
        client_no_redis,
        headers,
        (
            "Pierwsza debata E2E użytkownika — pięć słów minimum "
            "w briefie decyzyjnym bez wywołań LLM"
        ),
    )
    assert debate_1 >= 1

    continue_payload = {
        "previous_debate_id": debate_1,
        "follow_up": (
            "Kontynuacja wątku E2E po pierwszej debacie — pięć słów "
            "w follow-up bez zewnętrznego API"
        ),
    }
    with client_no_redis.stream(
        "POST",
        "/debate/continue/stream",
        headers=headers,
        json=continue_payload,
    ) as resp:
        assert resp.status_code == 200, resp.text
        cont_body = "".join(resp.iter_text())
    assert "debate_done" in cont_body
    debate_2 = _last_debate_done_id(cont_body)
    assert debate_2 >= 1
    assert debate_2 != debate_1

    export = client_no_redis.get("/account/export", headers=headers)
    assert export.status_code == 200, export.text
    export_json = export.json()
    assert export_json["tenant_id"] == login.json()["tenant_id"]
    debate_ids = {int(d["id"]) for d in export_json["debates"]}
    assert debate_1 in debate_ids
    assert debate_2 in debate_ids
    assert len(export_json["users"]) == 1
    assert export_json["users"][0]["username"] == username.lower()

    deleted = client_no_redis.request(
        "DELETE",
        "/account",
        headers=headers,
        json={"confirm": _CONFIRM_DELETE},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["ok"] is True
    assert deleted.json()["deleted"]["debates"] >= 2

    export_after = client_no_redis.get("/account/export", headers=headers)
    assert export_after.status_code == 200
    assert export_after.json()["debates"] == []
    assert export_after.json()["users"] == []

    login_after = client_no_redis.post(
        "/auth/login",
        json={"username": username, "password": _PASSWORD},
    )
    assert login_after.status_code == 401
