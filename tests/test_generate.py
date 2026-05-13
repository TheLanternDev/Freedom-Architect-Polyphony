"""
Testy endpointu /generate — legacy stub w v3.2.

W v3.2 `/generate` jest celowo legacy: zwraca strukturę informującą,
że główny flow przeszedł na SSE `/debate/stream`. Testy sprawdzają:
1. Stub zwraca poprawny ArchitectureResponse z `status="legacy"`.
2. Walidatory pola `description` działają (min_length=20 + min 5 słów).
3. Walidatory typów kategorii/trybu/scale/budget działają.
"""

from __future__ import annotations


def test_generate_returns_legacy_stub(client_no_redis, valid_brief_payload):
    resp = client_no_redis.post("/generate", json=valid_brief_payload)
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["status"] == "legacy"
    assert data["idea"] == valid_brief_payload["description"]
    assert data["cache_hit"] is False
    assert data["cached_at"] is None
    assert "generated_at" in data and data["generated_at"]
    # Wskazówka, że nowy flow to /debate/stream
    assert "/debate/stream" in data["architecture"]["description"]


def test_generate_lists_v32_folders(client_no_redis, valid_brief_payload):
    data = client_no_redis.post("/generate", json=valid_brief_payload).json()
    folders = data["code_structure"]["folders"]
    assert "agents/" in folders
    assert "core/" in folders
    assert "db/" in folders


def test_generate_insights_mention_aksjomaty(client_no_redis, valid_brief_payload):
    data = client_no_redis.post("/generate", json=valid_brief_payload).json()
    insights_blob = " ".join(data["agent_insights"])
    assert "AKSJOMAT" in insights_blob
    assert "/debate/stream" in insights_blob


def test_generate_validation_too_short_description(client_no_redis):
    payload = {"description": "Za krótko"}  # < 20 znaków → 422
    resp = client_no_redis.post("/generate", json=payload)
    assert resp.status_code == 422


def test_generate_validation_few_words(client_no_redis):
    payload = {
        # długie, ale tylko 3 „słowa" po splitcie → custom validator
        "description": "aaaaaaaaaa bbbbbbbbbb cccccccccc",
    }
    resp = client_no_redis.post("/generate", json=payload)
    assert resp.status_code == 422
    assert "Marzenia" in resp.text


def test_generate_few_words_exact_error_message(client_no_redis):
    payload = {
        "description": "aaaaaaaaaa bbbbbbbbbb cccccccccc dddddddddd",
    }
    resp = client_no_redis.post("/generate", json=payload)
    assert resp.status_code == 422
    assert "Marzenia nie rodzą się z 3 słów." in resp.text


def test_generate_validation_bad_scale(client_no_redis, valid_brief_payload):
    bad = {**valid_brief_payload, "scale": "mega"}
    resp = client_no_redis.post("/generate", json=bad)
    assert resp.status_code == 422


def test_generate_validation_bad_budget(client_no_redis, valid_brief_payload):
    bad = {**valid_brief_payload, "budget": "unlimited"}
    resp = client_no_redis.post("/generate", json=bad)
    assert resp.status_code == 422


def test_generate_validation_bad_category(client_no_redis, valid_brief_payload):
    bad = {**valid_brief_payload, "category": "śmieci"}
    resp = client_no_redis.post("/generate", json=bad)
    assert resp.status_code == 422


def test_generate_validation_bad_mode(client_no_redis, valid_brief_payload):
    bad = {**valid_brief_payload, "mode": "turbo"}
    resp = client_no_redis.post("/generate", json=bad)
    assert resp.status_code == 422
