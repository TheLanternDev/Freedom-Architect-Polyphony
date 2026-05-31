"""Test `POST /personal/onboarding/save` — zapis odpowiedzi onboardingowych.

Bez DB (`repo` bez `upsert_onboarding_answer`) → fallback JSONL.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.personal import router as personal_router
from personal_v1.rituals.onboarding import PYTANIA as ONBOARDING_PYTANIA


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AW_FEEDBACK_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(personal_router)
    yield TestClient(app), tmp_path


def _patch_repo_without_upsert():
    import db
    return patch.object(db, "repo", object())


def test_get_onboarding_questions_returns_list(client):
    tc, _ = client
    r = tc.get("/personal/onboarding/questions")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == len(ONBOARDING_PYTANIA)


def test_save_writes_jsonl_fallback(client):
    tc, tmp_path = client
    with _patch_repo_without_upsert():
        r = tc.post("/personal/onboarding/save", json={
            "answers": [
                {"question_idx": 0, "answer": "Jestem kimś, kto nie kończy projektów."},
                {"question_idx": 1, "answer": "Dumny z czegoś, co zarchiwizowałem świadomie."},
            ],
        })
    assert r.status_code == 200
    body = r.json()
    assert body["saved"] == 2
    lines = (Path(tmp_path) / "onboarding_answers.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["question_idx"] == 0
    assert "nie kończy projektów" in first["answer"]


def test_save_rejects_out_of_range_question_idx(client):
    tc, _ = client
    out_of_range = len(ONBOARDING_PYTANIA)  # idx == len → out-of-range
    with _patch_repo_without_upsert():
        r = tc.post("/personal/onboarding/save", json={
            "answers": [{"question_idx": out_of_range, "answer": "x"}],
        })
    assert r.status_code == 422


def test_save_rejects_oversized_answer(client):
    tc, _ = client
    huge = "x" * 5000
    with _patch_repo_without_upsert():
        r = tc.post("/personal/onboarding/save", json={
            "answers": [{"question_idx": 0, "answer": huge}],
        })
    assert r.status_code == 422


def test_save_skips_empty_payload(client):
    """Pusta lista answers przechodzi (saved=0) — user może świadomie pominąć."""
    tc, _ = client
    with _patch_repo_without_upsert():
        r = tc.post("/personal/onboarding/save", json={"answers": []})
    assert r.status_code == 200
    assert r.json()["saved"] == 0


def test_get_ritual_daily_returns_questions(client):
    tc, _ = client
    r = tc.get("/personal/ritual/daily")
    assert r.status_code == 200
    body = r.json()
    assert "poranek" in body and "wieczor" in body
    assert isinstance(body["poranek"], list) and len(body["poranek"]) > 0
