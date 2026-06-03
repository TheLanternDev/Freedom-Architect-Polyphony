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


def _first_event_data(resp_text: str) -> dict:
    import json

    block = resp_text.split("\n\n")[0]
    data_line = next(
        (ln for ln in block.splitlines() if ln.startswith("data: ")), None
    )
    assert data_line is not None, "brak data: w pierwszym bloku SSE"
    return json.loads(data_line.removeprefix("data: "))


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

    # Pierwszy event — wczesny sygnał (kontrakt SSE § debate_pending)
    assert events[0] == "debate_pending"
    pending = _first_event_data(body)
    assert pending["status"] == "initializing"
    assert pending["council_mode"] in ("personal", "fa2")
    assert isinstance(pending["msg"], str) and len(pending["msg"]) > 0

    # AKSJOMAT 1 — faza A0 musi pojawić się PRZED Radą (po debate_pending)
    assert "dream_architecture" in events
    assert events.index("debate_pending") < events.index("dream_architecture")
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


def test_persist_dream_defers_debate_until_post_council(fresh_db_path):
    """P1-B1: marzenie/projekt wcześnie, wiersz debates dopiero po Radzie."""
    import asyncio
    from types import SimpleNamespace

    from core.dream_architect import _fallback_dream
    from db.backend import acquire_http_db
    from db.connection import init_db

    from api.services.dream_service import insert_debate_for_stream, persist_dream_and_project

    async def inner() -> None:
        await init_db(fresh_db_path)
        dream = _fallback_dream("Unit test persist dream without debate row", language="pl")
        brief = SimpleNamespace(
            category="decyzja",
            mode="pelna",
            description="Unit test persist dream without debate row",
            intention=None,
            extra_context=None,
        )
        async with acquire_http_db(fresh_db_path) as db:
            debate_id, project_id = await persist_dream_and_project(db, dream, brief)
            assert debate_id is None
            assert project_id is not None
            row = await db.execute("SELECT COUNT(*) FROM debates")
            assert (await row.fetchone())[0] == 0

            debate_id = await insert_debate_for_stream(
                db, brief, dream_id=dream.dream_id
            )
            assert debate_id is not None
            row = await db.execute("SELECT COUNT(*) FROM debates")
            assert (await row.fetchone())[0] == 1

    asyncio.run(inner())


def test_debate_stream_creates_project_only_for_category_projekt(
    client_no_redis, fresh_db_path
):
    """
    v3.3: persist_dream_and_project tworzy projekt przy każdej debacie z marzeniem
    (także category=decyzja). category=projekt przy MAX_ACTIVE_PROJECTS=1 → 409,
    dopóki poprzedni projekt nie jest świadomie zarchiwizowany.
    """
    import sqlite3

    from core import MAX_ACTIVE_PROJECTS

    decision_payload = {
        "description": "Test kategorii decyzja w trybie fallback — marzenie i projekt",
        "category": "decyzja",
        "mode": "pelna",
    }
    with client_no_redis.stream("POST", "/debate/stream", json=decision_payload) as r:
        assert r.status_code == 200
        for _ in r.iter_text():
            pass

    with sqlite3.connect(str(fresh_db_path)) as conn:
        n_projects_after_decision = conn.execute(
            "SELECT COUNT(*) FROM projects"
        ).fetchone()[0]
        n_active_after_decision = conn.execute(
            """
            SELECT COUNT(*) FROM projects
             WHERE status IN ('dreaming','in_progress','at_risk','stuck')
            """
        ).fetchone()[0]
    assert n_projects_after_decision == 1
    assert n_active_after_decision == 1

    # Drugi POST (projekt) przy pełnym limicie aktywnych → hard-lock 409, bez nowego projektu.
    project_payload = {
        "description": "Test kategorii projekt w trybie fallback z utworzeniem rekordu",
        "category": "projekt",
        "mode": "pelna",
    }
    blocked = client_no_redis.post("/debate/stream", json=project_payload)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["kind"] == "active_project_limit"

    with sqlite3.connect(str(fresh_db_path)) as conn:
        n_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        n_active = conn.execute(
            """
            SELECT COUNT(*) FROM projects
             WHERE status IN ('dreaming','in_progress','at_risk','stuck')
            """
        ).fetchone()[0]
    assert n_projects == 1
    assert n_active == MAX_ACTIVE_PROJECTS

    # Po świadomej archiwizacji — kolejna debata projekt może założyć drugi rekord.
    with sqlite3.connect(str(fresh_db_path)) as conn:
        first_pid = conn.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()[0]
    archive_reason = (
        "Świadomie archiwizuję projekt po teście smoke, aby zwolnić slot na nowy "
        "projekt zgodnie z AKSJOMATEM 2 i limitem aktywnych projektów."
    )
    ar = client_no_redis.post(
        f"/projects/{first_pid}/archive", json={"reason": archive_reason}
    )
    assert ar.status_code == 200

    with client_no_redis.stream("POST", "/debate/stream", json=project_payload) as r:
        assert r.status_code == 200
        for _ in r.iter_text():
            pass

    with sqlite3.connect(str(fresh_db_path)) as conn:
        n_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        n_items = conn.execute(
            "SELECT COUNT(*) FROM functionality_items"
        ).fetchone()[0]
        n_active = conn.execute(
            """
            SELECT COUNT(*) FROM projects
             WHERE status IN ('dreaming','in_progress','at_risk','stuck')
            """
        ).fetchone()[0]
    assert n_projects == 2
    assert n_active == 1
    assert n_items >= 2
