"""Faza A — izolacja historii debat per user W TYM SAMYM tenancie.

Scenariusz współdzielonego tenanta (legacy API key / BFF): userzy A i B mają
ten sam `tenant_id`, ale różne `user_subject`. Nowe debaty są rozdzielone;
stare wiersze (`user_subject = NULL`, sprzed migracji) pozostają widoczne dla
całego tenanta (decyzja: wstecznie zgodne).
"""

from __future__ import annotations

import asyncio


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_debate_history_isolated_per_user_same_tenant(fresh_db_path):
    from db import init_db, repo
    from db.backend import acquire_http_db
    from db.connection import DB_PATH
    from db.tenant import set_current_tenant_id, set_current_user_id

    async def scenario():
        await init_db()
        T = "wspolny-tenant"

        async with acquire_http_db(DB_PATH) as db:
            set_current_tenant_id(T)

            set_current_user_id("userA")
            id_a = await repo.insert_debate(
                db, category="decyzja", mode="codzienny",
                brief_description="Debata usera A", intention=None,
                extra_context=None, dream_id=None,
            )

            set_current_user_id("userB")
            id_b = await repo.insert_debate(
                db, category="decyzja", mode="codzienny",
                brief_description="Debata usera B", intention=None,
                extra_context=None, dream_id=None,
            )

            # Legacy: wiersz sprzed migracji (user_subject = NULL).
            await db.execute(
                "INSERT INTO debates (tenant_id, user_subject, category, mode, "
                "brief_description) VALUES (?, ?, ?, ?, ?)",
                (T, None, "decyzja", "codzienny", "Debata legacy NULL"),
            )
            await db.commit()
            cur = await db.execute(
                "SELECT id FROM debates WHERE brief_description = 'Debata legacy NULL'"
            )
            id_legacy = int((await cur.fetchone())["id"])

            # ── jako A ───────────────────────────────────────────────────────
            set_current_user_id("userA")
            ids_a = {int(r["id"]) for r in await repo.list_debates_recent(db, limit=50)}
            assert id_a in ids_a
            assert id_legacy in ids_a            # NULL widoczny dla całego tenanta
            assert id_b not in ids_a             # cudza debata — NIEwidoczna
            assert await repo.get_debate_row(db, id_a) is not None
            assert await repo.get_debate_row(db, id_b) is None
            assert await repo.get_debate_row(db, id_legacy) is not None
            # kontynuacja cudzej debaty: łańcuch pusty → handler zwróci 404
            assert await repo.list_debate_chain(db, id_b) == []

            # ── jako B ───────────────────────────────────────────────────────
            set_current_user_id("userB")
            ids_b = {int(r["id"]) for r in await repo.list_debates_recent(db, limit=50)}
            assert id_b in ids_b
            assert id_legacy in ids_b
            assert id_a not in ids_b
            assert await repo.get_debate_row(db, id_a) is None
            assert await repo.get_debate_row(db, id_legacy) is not None
            # legacy NULL można kontynuować (własność tenanta)
            assert len(await repo.list_debate_chain(db, id_legacy)) == 1

    _run(scenario())
