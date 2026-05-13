"""
Smoke test pełnego pipeline'u SSE /debate/stream.

Bez ANTHROPIC_API_KEY agenci spadają do `contribute()` (synchronicznych
placeholderów), a `adistill_dream()` używa fallbacku deterministycznego.
Test sprawdza WYŁĄCZNIE strumień eventów i ich typy — nie ich treść LLM-ową.

Cel: udowodnić, że cała pętla orkiestracji (A0 + 9 agentów + Syez +
persystencja SQLite) działa offline od początku do końca.
"""

from __future__ import annotations


def _collect_events(resp_text: str) -> list[str]:
    events: list[str] = []
    for line in resp_text.splitlines():
        if line.startswith("event: "):
            events.append(line[len("event: ") :])
    return events


def test_debate_stream_emits_full_event_sequence(client_no_redis):
    payload = {
        "description": (
            "Smoke test debaty w trybie fallback — sprawdzenie pełnego "
            "łańcucha eventów SSE bez wywołań LLM"
        ),
        "category": "marzenie",
        "mode": "marzen",
    }
    with client_no_redis.stream(
        "POST", "/debate/stream", json=payload
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    events = _collect_events(body)

    # AKSJOMAT 1 — faza A0 musi pojawić się PRZED Radą
    assert "dream_architecture" in events
    assert events.index("dream_architecture") < events.index("debate_start")

    # 9 agentów Rady
    assert events.count("agent_start") == 9
    assert events.count("agent_done") == 9

    # Syez
    assert "synthesis_start" in events
    assert "synthesis_done" in events
    # Kolejność: synthesis_start PRZED synthesis_done
    assert events.index("synthesis_start") < events.index("synthesis_done")

    # Zakończenie
    assert events[-1] == "debate_done"


def test_debate_stream_persists_dream_and_debate(client_no_redis, fresh_db_path):
    import sqlite3

    payload = {
        "description": (
            "Drugi smoke test sprawdzający czy marzenie i debata trafiają do "
            "SQLite w trybie fallback offline"
        ),
        "category": "decyzja",
        "mode": "pelna",
    }
    with client_no_redis.stream(
        "POST", "/debate/stream", json=payload
    ) as resp:
        assert resp.status_code == 200
        for _ in resp.iter_text():
            pass

    with sqlite3.connect(str(fresh_db_path)) as conn:
        dreams = conn.execute("SELECT COUNT(*) FROM dreams").fetchone()[0]
        debates = conn.execute("SELECT COUNT(*) FROM debates").fetchone()[0]
        voices = conn.execute("SELECT COUNT(*) FROM agent_voices").fetchone()[0]
    assert dreams == 1
    assert debates == 1
    # 9 agentów Rady → 9 wpisów w agent_voices
    assert voices == 9


def test_debate_stream_creates_project_only_for_category_projekt(
    client_no_redis, fresh_db_path
):
    import sqlite3

    # AKSJOMAT 2: każda debata z marzeniem tworzy projekt (checklist funkcjonalności).
    decision_payload = {
        "description": "Test kategorii decyzja w trybie fallback bez tworzenia projektu",
        "category": "decyzja",
        "mode": "pelna",
    }
    with client_no_redis.stream("POST", "/debate/stream", json=decision_payload) as r:
        for _ in r.iter_text():
            pass

    with sqlite3.connect(str(fresh_db_path)) as conn:
        n_projects_after_decision = conn.execute(
            "SELECT COUNT(*) FROM projects"
        ).fetchone()[0]
    assert n_projects_after_decision == 1

    # 2) druga debata (projekt) → drugi projekt / marzenie
    project_payload = {
        "description": "Test kategorii projekt w trybie fallback z utworzeniem rekordu",
        "category": "projekt",
        "mode": "pelna",
    }
    with client_no_redis.stream("POST", "/debate/stream", json=project_payload) as r:
        for _ in r.iter_text():
            pass

    with sqlite3.connect(str(fresh_db_path)) as conn:
        n_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        n_items = conn.execute(
            "SELECT COUNT(*) FROM functionality_items"
        ).fetchone()[0]
    assert n_projects == 2
    # functionality_checklist z fallbacku ma co najmniej jedną pozycję na projekt
    assert n_items >= 2
