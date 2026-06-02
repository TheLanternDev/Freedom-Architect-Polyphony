"""
Łańcuch wątku debat (parent_debate_id) — list_debate_chain + kontekst kontynuacji.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from db import repo
from db.backend import acquire_http_db
from db.connection import init_db
from db.tenant import reset_current_tenant_id, set_current_tenant_id


async def _insert_chain_debate(
    db_path: Path,
    *,
    brief: str,
    synthesis: str,
    parent_id: int | None = None,
) -> int:
    async with acquire_http_db(db_path) as db:
        debate_id = await repo.insert_debate(
            db,
            category="decyzja",
            mode="codzienny",
            brief_description=brief,
            intention=None,
            extra_context=None,
            dream_id=None,
            parent_debate_id=parent_id,
        )
        await db.execute(
            "UPDATE debates SET synthesis_text = ? WHERE id = ?",
            (synthesis, debate_id),
        )
        await db.commit()
        return debate_id


def test_list_debate_chain_three_turns_chronological(fresh_db_path):
    """t1 ← t2 ← t3: łańcuch od liścia zwraca [t1, t2, t3]."""

    async def inner():
        await init_db(fresh_db_path)
        t1 = await _insert_chain_debate(
            fresh_db_path,
            brief="Pierwsza tura wątku — brief początkowy z pięcioma słowami min.",
            synthesis="Synteza tury pierwszej.",
            parent_id=None,
        )
        t2 = await _insert_chain_debate(
            fresh_db_path,
            brief="Druga tura wątku — kontynuacja po pierwszej debacie.",
            synthesis="Synteza tury drugiej.",
            parent_id=t1,
        )
        t3 = await _insert_chain_debate(
            fresh_db_path,
            brief="Trzecia tura wątku — najnowszy liść łańcucha.",
            synthesis="Synteza tury trzeciej.",
            parent_id=t2,
        )

        async with acquire_http_db(fresh_db_path) as db:
            chain = await repo.list_debate_chain(db, t3)

        assert [c["id"] for c in chain] == [t1, t2, t3]
        assert chain[0]["brief_description"].startswith("Pierwsza")
        assert chain[2]["synthesis_text"] == "Synteza tury trzeciej."

    asyncio.run(inner())


def test_list_debate_chain_single_debate_backward_compat(fresh_db_path):
    """Debatа bez rodzica → łańcuch = [ona]."""

    async def inner():
        await init_db(fresh_db_path)
        solo = await _insert_chain_debate(
            fresh_db_path,
            brief="Samotna debata bez rodzica — pięć słów minimum tutaj.",
            synthesis="Jedyna synteza.",
            parent_id=None,
        )

        async with acquire_http_db(fresh_db_path) as db:
            chain = await repo.list_debate_chain(db, solo)

        assert len(chain) == 1
        assert chain[0]["id"] == solo

    asyncio.run(inner())


def test_list_debate_chain_cycle_safe(fresh_db_path):
    """Cykl parent → potomek nie zapętla się w nieskończoność."""

    async def inner():
        await init_db(fresh_db_path)
        a = await _insert_chain_debate(
            fresh_db_path,
            brief="Debatа A w cyklu testowym — minimum pięć słów w briefie.",
            synthesis="Synth A",
            parent_id=None,
        )
        b = await _insert_chain_debate(
            fresh_db_path,
            brief="Debatа B w cyklu testowym — minimum pięć słów w briefie.",
            synthesis="Synth B",
            parent_id=a,
        )
        async with aiosqlite.connect(str(fresh_db_path)) as db:
            await db.execute(
                "UPDATE debates SET parent_debate_id = ? WHERE id = ?",
                (b, a),
            )
            await db.commit()

        async with acquire_http_db(fresh_db_path) as db:
            chain = await repo.list_debate_chain(db, b, max_turns=10)

        ids = [c["id"] for c in chain]
        assert len(ids) == len(set(ids)), f"powtórzone id w łańcuchu: {ids}"
        assert b in ids

    asyncio.run(inner())


def test_continuation_extra_ctx_respects_2000_char_budget():
    """Przy 4 turach z długimi treściami extra_ctx nie przekracza limitu."""
    from main import _CONTINUATION_EXTRA_CTX_LIMIT, _build_continuation_extra_ctx

    chain = [
        {
            "id": i,
            "brief_description": "B" * 1200,
            "synthesis_text": "S" * 1200,
        }
        for i in range(1, 5)
    ]
    voices = [
        {"agent_name": f"agent_{k}", "voice_text": "V" * 500}
        for k in range(9)
    ]
    ctx = _build_continuation_extra_ctx(chain, voices, leaf_debate_id=4)
    assert len(ctx) <= _CONTINUATION_EXTRA_CTX_LIMIT


def test_resolve_root_debate_ids_for_thread(fresh_db_path):
    """resolve_root_debate_ids: każda tura wątku wskazuje na ten sam root."""

    async def inner():
        await init_db(fresh_db_path)
        t1 = await _insert_chain_debate(
            fresh_db_path,
            brief="Root wątku do testu root_debate_id — minimum pięć słów.",
            synthesis="S1",
            parent_id=None,
        )
        t2 = await _insert_chain_debate(
            fresh_db_path,
            brief="Druga tura — kontynuacja wątku po pierwszej debacie testowej.",
            synthesis="S2",
            parent_id=t1,
        )
        t3 = await _insert_chain_debate(
            fresh_db_path,
            brief="Trzecia tura — najnowszy liść wątku testowego do roota.",
            synthesis="S3",
            parent_id=t2,
        )
        solo = await _insert_chain_debate(
            fresh_db_path,
            brief="Solo bez rodzica — debata samodzielna do testu root_id.",
            synthesis="solo",
            parent_id=None,
        )

        async with acquire_http_db(fresh_db_path) as db:
            roots = await repo.resolve_root_debate_ids(db, [t1, t2, t3, solo])

        assert roots[t1] == t1
        assert roots[t2] == t1
        assert roots[t3] == t1
        assert roots[solo] == solo

    asyncio.run(inner())


def test_history_endpoint_returns_root_debate_id(client_no_redis):
    """/history wzbogaca każdą debatę o root_debate_id (po stronie backendu)."""
    # Posiej dwie tury wątku przez /debate/stream byłoby drogie; używamy bezpośrednio repo.
    import asyncio as _asyncio
    from db.backend import acquire_http_db as _acquire
    from db.connection import DB_PATH as _DB

    async def seed():
        async with _acquire(_DB) as db:
            t1 = await repo.insert_debate(
                db,
                category="decyzja",
                mode="codzienny",
                brief_description="Brief roota wątku — minimum pięć słów w treści.",
                intention=None,
                extra_context=None,
                dream_id=None,
                parent_debate_id=None,
            )
            t2 = await repo.insert_debate(
                db,
                category="decyzja",
                mode="codzienny",
                brief_description="Brief tury drugiej — kontynuacja po pierwszej debacie.",
                intention=None,
                extra_context=None,
                dream_id=None,
                parent_debate_id=t1,
            )
            await db.commit()
            return t1, t2

    t1, t2 = _asyncio.run(seed())
    r = client_no_redis.get("/history?limit=10")
    assert r.status_code == 200
    debates = r.json()["debates"]
    by_id = {int(row["id"]): row for row in debates}
    assert by_id[t1].get("root_debate_id") == t1
    assert by_id[t2].get("root_debate_id") == t1


def test_list_debate_chain_tenant_isolation(fresh_db_path):
    """Wątek tenant-a nie jest widoczny dla tenant-b (list_debate_chain)."""

    async def inner():
        await init_db(fresh_db_path)
        tok_a = set_current_tenant_id("tenant-a")
        try:
            t1 = await _insert_chain_debate(
                fresh_db_path,
                brief="Tenant A tura pierwsza — minimum pięć słów w briefie.",
                synthesis="Synth A1",
                parent_id=None,
            )
            t2 = await _insert_chain_debate(
                fresh_db_path,
                brief="Tenant A tura druga — kontynuacja wątku po pierwszej.",
                synthesis="Synth A2",
                parent_id=t1,
            )
        finally:
            reset_current_tenant_id(tok_a)

        tok_b = set_current_tenant_id("tenant-b")
        try:
            async with acquire_http_db(fresh_db_path) as db:
                chain = await repo.list_debate_chain(db, t2)
            assert chain == [], (
                f"tenant-b nie powinien widzieć debaty {t2} tenant-a, dostał: {chain}"
            )
        finally:
            reset_current_tenant_id(tok_b)

    asyncio.run(inner())
