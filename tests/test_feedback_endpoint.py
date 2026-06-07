"""Test endpointu `/feedback` (Tydzień 4 mapy luk).

Bez DB → fallback do JSONL w katalogu `AW_FEEDBACK_DIR`. Test izoluje
folder przez tmp_path + monkeypatch.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.feedback import router as feedback_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI app z izolowanym katalogiem feedbacku."""
    monkeypatch.setenv("AW_FEEDBACK_DIR", str(tmp_path))
    # Wymuszamy fallback JSONL — patch importu db w endpoint.
    import api.routers.feedback as fb
    # Symulujemy brak `db.repo.insert_feedback` (repo bez tej metody w tym repo).
    # Trzeba upewnić się że gałąź fallback się wywoła:
    app = FastAPI()
    app.include_router(feedback_router)
    yield TestClient(app), tmp_path


def _patch_repo_without_insert():
    """Patchuje `db.repo` żeby NIE miał `insert_feedback`, wymuszając fallback JSONL."""
    import db
    return patch.object(db, "repo", object())


def _last_feedback_line(tmp_path) -> str:
    """Ostatnia linia z pliku feedbacku. Po L-2 plik jest per-tenant
    (`feedback_<tenant>.jsonl`), więc bierzemy jedyny pasujący glob."""
    files = sorted(Path(tmp_path).glob("feedback_*.jsonl"))
    assert files, f"Brak pliku feedback_*.jsonl w {tmp_path}"
    return files[-1].read_text().strip().splitlines()[-1]


def test_feedback_endpoint_accepts_minimum_payload(client):
    tc, tmp_path = client
    with _patch_repo_without_insert():
        r = tc.post("/feedback", json={"rating": 4})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "ts" in body

    # Plik JSONL zapisany (per-tenant: feedback_<tenant>.jsonl — L-2).
    line = json.loads(_last_feedback_line(tmp_path))
    assert line["rating"] == 4
    assert line["what_worked"] == ""
    assert line["what_broke"] == ""
    assert line["debate_id"] is None


def test_feedback_endpoint_rejects_out_of_range_rating(client):
    tc, _ = client
    with _patch_repo_without_insert():
        r0 = tc.post("/feedback", json={"rating": 0})
        r6 = tc.post("/feedback", json={"rating": 6})
    assert r0.status_code == 422
    assert r6.status_code == 422


def test_feedback_endpoint_persists_text_and_debate_id(client):
    tc, tmp_path = client
    with _patch_repo_without_insert():
        r = tc.post("/feedback", json={
            "rating": 5,
            "what_worked": "Synteza pokazała ruch ≤60 min, zrobiłem go.",
            "what_broke": "FragmentCompass zniknął po reloadzie raz na 10.",
            "debate_id": 42,
        })
    assert r.status_code == 200
    line = json.loads(_last_feedback_line(tmp_path))
    assert line["rating"] == 5
    assert "Synteza pokazała ruch" in line["what_worked"]
    assert "FragmentCompass" in line["what_broke"]
    assert line["debate_id"] == 42


def test_feedback_endpoint_rejects_oversized_text(client):
    tc, _ = client
    huge = "x" * 3000
    with _patch_repo_without_insert():
        r = tc.post("/feedback", json={
            "rating": 3,
            "what_worked": huge,
        })
    # Pydantic max_length=2000 → 422.
    assert r.status_code == 422


def test_feedback_endpoint_anonymous_when_no_jwt(client):
    """Bez `request.state.architekt_subject` user_subject = "anonymous"."""
    tc, tmp_path = client
    with _patch_repo_without_insert():
        r = tc.post("/feedback", json={"rating": 2})
    assert r.status_code == 200
    line = json.loads(_last_feedback_line(tmp_path))
    assert line["user_subject"] == "anonymous"
