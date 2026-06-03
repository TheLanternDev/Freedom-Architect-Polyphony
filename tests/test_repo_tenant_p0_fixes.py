"""Repo: insert_feedback, upsert_onboarding_answer, link_dream_debate tenant guard."""

from __future__ import annotations

import asyncio

from db import repo
from db.backend import acquire_http_db
from db.connection import init_db
from db.tenant import reset_current_tenant_id, set_current_tenant_id


def test_insert_feedback_isolated_per_tenant(fresh_db_path):
    async def inner():
        await init_db(fresh_db_path)

        tok_a = set_current_tenant_id("tenant-a")
        try:
            async with acquire_http_db(fresh_db_path) as db:
                await repo.insert_feedback(
                    db,
                    user_subject="user-a",
                    rating=5,
                    what_worked="ok",
                    what_broke="",
                    debate_id=None,
                    created_at="2026-01-01T00:00:00+00:00",
                )
                await db.commit()
        finally:
            reset_current_tenant_id(tok_a)

        tok_b = set_current_tenant_id("tenant-b")
        try:
            async with acquire_http_db(fresh_db_path) as db:
                cur = await db.execute(
                    "SELECT COUNT(*) FROM feedback WHERE tenant_id = ?", ("tenant-b",)
                )
                assert (await cur.fetchone())[0] == 0
                cur = await db.execute(
                    "SELECT rating FROM feedback WHERE tenant_id = ?", ("tenant-a",)
                )
                row = await cur.fetchone()
                assert row is not None
                assert int(row[0]) == 5
        finally:
            reset_current_tenant_id(tok_b)

    asyncio.run(inner())


def test_upsert_onboarding_answer_per_tenant(fresh_db_path):
    async def inner():
        await init_db(fresh_db_path)
        ts = "2026-01-01T00:00:00+00:00"

        tok_a = set_current_tenant_id("tenant-a")
        try:
            async with acquire_http_db(fresh_db_path) as db:
                await repo.upsert_onboarding_answer(
                    db,
                    user_subject="alice",
                    question_idx=0,
                    answer="odpowiedź A",
                    updated_at=ts,
                )
                await db.commit()
        finally:
            reset_current_tenant_id(tok_a)

        tok_b = set_current_tenant_id("tenant-b")
        try:
            async with acquire_http_db(fresh_db_path) as db:
                await repo.upsert_onboarding_answer(
                    db,
                    user_subject="alice",
                    question_idx=0,
                    answer="odpowiedź B",
                    updated_at=ts,
                )
                await db.commit()
        finally:
            reset_current_tenant_id(tok_b)

        tok_a = set_current_tenant_id("tenant-a")
        try:
            async with acquire_http_db(fresh_db_path) as db:
                cur = await db.execute(
                    "SELECT answer FROM onboarding_answers WHERE tenant_id = ? AND question_idx = 0",
                    ("tenant-a",),
                )
                assert (await cur.fetchone())[0] == "odpowiedź A"
        finally:
            reset_current_tenant_id(tok_a)

    asyncio.run(inner())


def test_link_dream_debate_rejects_cross_tenant(fresh_db_path):
    async def inner():
        await init_db(fresh_db_path)

        tok_a = set_current_tenant_id("tenant-a")
        dream_id = "dream-a"
        debate_id = 0
        try:
            async with acquire_http_db(fresh_db_path) as db:
                await db.execute(
                    """
                    INSERT INTO dreams (
                        id, tenant_id, raw_brief, core_dream, value_anchor,
                        pillars_json, milestones_json, next_move_json,
                        completion_criteria_json, functionality_checklist_json
                    ) VALUES (?, ?, 'b', 'c', 'v', '[]', '[]', '{}', '[]', '[]')
                    """,
                    (dream_id, "tenant-a"),
                )
                cur = await db.execute(
                    """
                    INSERT INTO debates (
                        tenant_id, category, mode, brief_description
                    ) VALUES (?, 'decyzja', 'codzienny', 'brief')
                    """,
                    ("tenant-a",),
                )
                debate_id = int(cur.lastrowid)
                await db.commit()
        finally:
            reset_current_tenant_id(tok_a)

        tok_b = set_current_tenant_id("tenant-b")
        try:
            async with acquire_http_db(fresh_db_path) as db:
                with __import__("pytest").raises(ValueError, match="nie należą"):
                    await repo.link_dream_debate(db, dream_id, debate_id)
        finally:
            reset_current_tenant_id(tok_b)

        tok_a = set_current_tenant_id("tenant-a")
        try:
            async with acquire_http_db(fresh_db_path) as db:
                await repo.link_dream_debate(db, dream_id, debate_id)
                cur = await db.execute(
                    "SELECT tenant_id FROM dream_debate_link WHERE dream_id = ?",
                    (dream_id,),
                )
                assert (await cur.fetchone())[0] == "tenant-a"
        finally:
            reset_current_tenant_id(tok_a)

    asyncio.run(inner())
