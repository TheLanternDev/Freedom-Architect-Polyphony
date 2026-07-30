"""Regresja: early-return 401 z http_guard MUSI dostać nagłówki CORS.

Gdy CORSMiddleware jest *wewnątrz* middleware guardu, WebKit/Tauri dostaje
„Failed to fetch" zamiast czytelnego 401 — UI kłamie „backend nie odpowiada".
"""

from __future__ import annotations


def test_guard_401_includes_cors_header(client_no_auth_bypass, monkeypatch):
    """Early-return z guardu (brak sekretów) nadal przechodzi przez CORSMiddleware."""
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)
    monkeypatch.delenv("ARCHITEKT_JWT_SECRET", raising=False)
    monkeypatch.delenv("AW_INSECURE_NO_AUTH", raising=False)

    r = client_no_auth_bypass.get(
        "/history",
        headers={"Origin": "tauri://localhost"},
    )
    assert r.status_code == 401
    acao = r.headers.get("access-control-allow-origin")
    assert acao, "brak Access-Control-Allow-Origin na 401 z guardu — zła kolejność middleware"
    assert acao in ("*", "tauri://localhost")


def test_debate_stream_401_includes_cors_header(client_no_auth_bypass, monkeypatch):
    monkeypatch.delenv("ARCHITEKT_API_KEY", raising=False)
    monkeypatch.delenv("ARCHITEKT_JWT_SECRET", raising=False)
    monkeypatch.delenv("AW_INSECURE_NO_AUTH", raising=False)

    r = client_no_auth_bypass.post(
        "/debate/stream",
        headers={
            "Origin": "http://localhost:1420",
            "Content-Type": "application/json",
            "Authorization": "Bearer invalid-token",
        },
        json={"description": "x", "category": "decyzja", "mode": "codzienny"},
    )
    assert r.status_code == 401
    acao = r.headers.get("access-control-allow-origin")
    assert acao, "brak Access-Control-Allow-Origin na POST /debate/stream 401"
    assert acao in ("*", "http://localhost:1420")
