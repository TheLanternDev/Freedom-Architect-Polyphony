"""
Połączenie SQLite + repozytorium dla domeny Architekta.

Używa `aiosqlite` (async). Schemat ładowany z `db/schema.sql`. Single-file DB
w `data/architekt.db` (override env: `ARCHITEKT_DB_PATH`).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover
    import aiosqlite
    _AIOSQLITE_OK = True
except Exception:  # pragma: no cover
    aiosqlite = None  # type: ignore[assignment]
    _AIOSQLITE_OK = False


_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "architekt.db"
DB_PATH: Path = Path(os.getenv("ARCHITEKT_DB_PATH", str(_DEFAULT_DB)))
_SCHEMA_PATH: Path = Path(__file__).resolve().parent / "schema.sql"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db(db_path: Optional[Path] = None) -> None:
    """SQLite (plik + migracje) lub PostgreSQL (`DATABASE_URL`) — patrz `db.backend`."""
    from db.backend import init_database

    async def _sqlite_body() -> None:
        if not _AIOSQLITE_OK:
            logger.warning("aiosqlite niedostępne — pomijam init_db SQLite (tryb degraded).")
            return
        path = db_path or DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        async with aiosqlite.connect(path) as db:  # type: ignore[union-attr]
            await db.executescript(schema)
            await _migrate_debates_parent_column(db)
            await _migrate_commitments_phase2(db)
            await _migrate_agent_evolution_table(db)
            await db.commit()
        logger.info("SQLite initialized at %s", path)

    await init_database(_sqlite_body)


async def _migrate_debates_parent_column(db: Any) -> None:
    """Istniejące bazy bez `parent_debate_id` — jednorazowy ALTER (idempotentny)."""
    cur = await db.execute("PRAGMA table_info(debates)")
    rows = await cur.fetchall()
    col_names = {r[1] for r in rows}
    if "parent_debate_id" not in col_names:
        await db.execute("ALTER TABLE debates ADD COLUMN parent_debate_id INTEGER NULL")


async def _migrate_commitments_phase2(db: Any) -> None:
    """Faza 2: trigger_type, needs_attention, release_reason (idempotentne ALTER)."""
    cur = await db.execute("PRAGMA table_info(commitments)")
    rows = await cur.fetchall()
    col_names = {r[1] for r in rows}
    if "trigger_type" not in col_names:
        await db.execute(
            "ALTER TABLE commitments ADD COLUMN trigger_type TEXT NOT NULL DEFAULT 'manual'"
        )
    if "needs_attention" not in col_names:
        await db.execute(
            "ALTER TABLE commitments ADD COLUMN needs_attention INTEGER NOT NULL DEFAULT 0"
        )
    if "release_reason" not in col_names:
        await db.execute("ALTER TABLE commitments ADD COLUMN release_reason TEXT NULL")


async def _migrate_agent_evolution_table(db: Any) -> None:
    """P5: rolling pamięć ewolucyjna per agent (idempotentne)."""
    cur = await db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_evolution'"
    )
    if await cur.fetchone():
        return
    await db.execute(
        """
        CREATE TABLE agent_evolution (
            agent_name  TEXT PRIMARY KEY,
            note_md     TEXT NOT NULL DEFAULT '',
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


async def get_db() -> AsyncIterator[Any]:
    """Jedno połączenie na żądanie — SQLite lub Postgres (`DATABASE_URL`)."""
    from db.backend import acquire_http_db, use_postgres

    if not use_postgres() and not _AIOSQLITE_OK:
        raise RuntimeError("aiosqlite niedostępne — zainstaluj `aiosqlite` lub ustaw DATABASE_URL.")
    async with acquire_http_db(DB_PATH) as db:
        yield db


# ── Repozytorium domenowe ───────────────────────────────────────────────────


class _Repo:
    """
    Cienka warstwa CRUD nad SQLite. Każda metoda przyjmuje aktywne `db`
    (połączenie aiosqlite), żeby kontrolować transakcje na zewnątrz.
    """

    # ---- dreams ----------------------------------------------------------

    async def insert_dream(self, db: Any, dream: Any) -> str:
        """Zapisuje DreamArchitecture. Zwraca dream_id."""
        await db.execute(
            """
            INSERT INTO dreams (
              id, created_at, raw_brief, core_dream, value_anchor,
              pillars_json, milestones_json, next_move_json,
              completion_criteria_json, functionality_checklist_json,
              status
            ) VALUES (?,?,?,?,?,?,?,?,?,?, 'living')
            """,
            (
                dream.dream_id,
                dream.created_at,
                dream.raw_brief,
                dream.core_dream,
                dream.value_anchor,
                json.dumps(dream.pillars, ensure_ascii=False),
                json.dumps([m.model_dump() for m in dream.milestones], ensure_ascii=False),
                json.dumps(dream.next_move.model_dump(), ensure_ascii=False),
                json.dumps(dream.completion_criteria, ensure_ascii=False),
                json.dumps(dream.functionality_checklist, ensure_ascii=False),
            ),
        )
        return dream.dream_id

    async def get_dream(self, db: Any, dream_id: str) -> Optional[dict[str, Any]]:
        cur = await db.execute("SELECT * FROM dreams WHERE id = ?", (dream_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

    # ---- projects ----------------------------------------------------------

    async def ensure_project_for_dream(
        self, db: Any, dream_id: str, functionality_checklist: list[str]
    ) -> int:
        """
        Zapewnia istnienie projektu dla danego marzenia. Tworzy go z pełną
        functionality_checklist (AKSJOMAT 2 — bez tego projekt nie ma definicji
        skończoności). Zwraca project_id.
        """
        cur = await db.execute("SELECT id FROM projects WHERE dream_id = ?", (dream_id,))
        row = await cur.fetchone()
        if row:
            return int(row["id"])
        cur = await db.execute(
            "INSERT INTO projects (dream_id, status, started_at) VALUES (?, 'dreaming', ?)",
            (dream_id, _utcnow()),
        )
        project_id = int(cur.lastrowid)
        for desc in functionality_checklist:
            await db.execute(
                "INSERT INTO functionality_items (project_id, description) VALUES (?, ?)",
                (project_id, desc),
            )
        return project_id

    async def list_active_projects(self, db: Any) -> list[dict[str, Any]]:
        cur = await db.execute(
            """
            SELECT p.*, d.core_dream
              FROM projects p
              JOIN dreams d ON d.id = p.dream_id
             WHERE p.status IN ('dreaming','in_progress','at_risk','stuck')
             ORDER BY p.started_at DESC
            """
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_project(self, db: Any, project_id: int) -> Optional[dict[str, Any]]:
        cur = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = await cur.fetchone()
        if not row:
            return None
        p = dict(row)
        cur = await db.execute(
            "SELECT * FROM functionality_items WHERE project_id = ? ORDER BY id",
            (project_id,),
        )
        items = [dict(r) for r in await cur.fetchall()]
        p["functionality"] = items
        return p

    async def update_project_status(
        self, db: Any, project_id: int, status: str, **fields: Any
    ) -> None:
        cols = ["status = ?"]
        vals: list[Any] = [status]
        for k, v in fields.items():
            cols.append(f"{k} = ?")
            vals.append(v)
        vals.append(project_id)
        await db.execute(
            f"UPDATE projects SET {', '.join(cols)} WHERE id = ?", tuple(vals)
        )

    async def mark_functionality_done(
        self,
        db: Any,
        item_id: int,
        evidence_url: Optional[str] = None,
    ) -> Optional[int]:
        """Odhacza pozycję i zwraca project_id (lub None gdy nie znaleziono)."""
        cur = await db.execute(
            "SELECT project_id FROM functionality_items WHERE id = ?", (item_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        project_id = int(row["project_id"])
        await db.execute(
            """
            UPDATE functionality_items
               SET is_done = 1, done_at = ?, evidence_url = COALESCE(?, evidence_url)
             WHERE id = ?
            """,
            (_utcnow(), evidence_url, item_id),
        )
        # AKSJOMAT 2: każdy ruch = aktualizacja last_progress_at + przejście do IN_PROGRESS
        await db.execute(
            """
            UPDATE projects
               SET last_progress_at = ?,
                   status = CASE WHEN status = 'dreaming' THEN 'in_progress' ELSE status END
             WHERE id = ?
            """,
            (_utcnow(), project_id),
        )
        return project_id

    # ---- debates / voices / synthesis -------------------------------------

    async def insert_debate(
        self,
        db: Any,
        *,
        category: str,
        mode: str,
        brief_description: str,
        intention: Optional[str],
        extra_context: Optional[str],
        dream_id: Optional[str],
        parent_debate_id: Optional[int] = None,
    ) -> int:
        cur = await db.execute(
            """
            INSERT INTO debates (
              category, mode, brief_description, intention, extra_context,
              dream_id, parent_debate_id
            )
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                category,
                mode,
                brief_description,
                intention,
                extra_context,
                dream_id,
                parent_debate_id,
            ),
        )
        return int(cur.lastrowid)

    async def link_dream_debate(self, db: Any, dream_id: str, debate_id: int) -> None:
        await db.execute(
            "INSERT OR IGNORE INTO dream_debate_link (dream_id, debate_id) VALUES (?, ?)",
            (dream_id, debate_id),
        )

    async def save_voice(
        self,
        db: Any,
        debate_id: int,
        agent_name: str,
        voice_text: str,
    ) -> None:
        await db.execute(
            "INSERT INTO agent_voices (debate_id, agent_name, voice_text) VALUES (?,?,?)",
            (debate_id, agent_name, voice_text),
        )

    async def list_agent_evolution(self, db: Any) -> dict[str, str]:
        cur = await db.execute("SELECT agent_name, note_md FROM agent_evolution")
        rows = await cur.fetchall()
        return {str(r[0]): str(r[1] or "") for r in rows}

    async def merge_agent_evolution_snippet(
        self,
        db: Any,
        agent_name: str,
        voice_text: str,
        *,
        snippet_cap: int = 380,
        total_cap: int = 2600,
    ) -> None:
        raw = " ".join((voice_text or "").split())
        if not raw or raw.startswith("[błąd") or raw.startswith("[error"):
            return
        snippet = raw[:snippet_cap].strip()
        if not snippet:
            return
        cur = await db.execute(
            "SELECT note_md FROM agent_evolution WHERE agent_name = ?",
            (agent_name,),
        )
        row = await cur.fetchone()
        prev = str(row[0] or "") if row else ""
        line = "• " + snippet
        merged = (prev.strip() + "\n" + line).strip() if prev else line
        while len(merged) > total_cap:
            nl = merged.find("\n")
            if nl == -1:
                merged = merged[-total_cap:]
                break
            merged = merged[nl + 1 :].strip()

        await db.execute(
            """
            INSERT INTO agent_evolution (agent_name, note_md, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(agent_name) DO UPDATE SET
                note_md = excluded.note_md,
                updated_at = excluded.updated_at
            """,
            (agent_name, merged),
        )

    async def save_synthesis(
        self,
        db: Any,
        debate_id: int,
        synthesis_text: str,
        synthesis_json: Optional[dict[str, Any]],
    ) -> None:
        await db.execute(
            "UPDATE debates SET synthesis_text = ?, full_synthesis_json = ? WHERE id = ?",
            (
                synthesis_text,
                json.dumps(synthesis_json, ensure_ascii=False) if synthesis_json else None,
                debate_id,
            ),
        )

    async def save_completion_audit(
        self,
        db: Any,
        project_id: int,
        debate_id: Optional[int],
        audit: dict[str, Any],
    ) -> int:
        cur = await db.execute(
            "INSERT INTO completion_audits (project_id, debate_id, remaining_json) VALUES (?,?,?)",
            (project_id, debate_id, json.dumps(audit, ensure_ascii=False)),
        )
        return int(cur.lastrowid)

    async def list_debates_recent(
        self,
        db: Any,
        limit: int = 50,
        *,
        query: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        lim = max(1, min(limit, 200))
        q = (query or "").strip()
        dialect = getattr(db, "dialect", "sqlite")
        order = (
            "ORDER BY datetime(created_at) DESC"
            if dialect == "sqlite"
            else "ORDER BY created_at DESC"
        )
        order_d = (
            "ORDER BY datetime(d.created_at) DESC"
            if dialect == "sqlite"
            else "ORDER BY d.created_at DESC"
        )
        if not q:
            cur = await db.execute(
                f"""
                SELECT id, created_at, category, mode, brief_description, dream_id,
                       substr(brief_description, 1, 140) AS preview
                  FROM debates
                 {order}
                 LIMIT ?
                """,
                (lim,),
            )
        else:
            needle = q.lower()[:500]
            if dialect == "postgres":
                where = """
                 WHERE POSITION($1 IN lower(coalesce(d.brief_description,''))) > 0
                    OR POSITION($2 IN lower(coalesce(d.intention,''))) > 0
                    OR POSITION($3 IN lower(coalesce(d.extra_context,''))) > 0
                    OR POSITION($4 IN lower(coalesce(d.synthesis_text,''))) > 0
                    OR POSITION($5 IN lower(coalesce(v.voice_text,''))) > 0
                """
                sql = f"""
                SELECT DISTINCT d.id, d.created_at, d.category, d.mode, d.brief_description, d.dream_id,
                       substr(d.brief_description::text, 1, 140) AS preview
                  FROM debates d
                  LEFT JOIN agent_voices v ON v.debate_id = d.id
                 {where}
                 {order_d}
                 LIMIT $6
                """
                cur = await db.execute(
                    sql,
                    (needle, needle, needle, needle, needle, lim),
                )
            else:
                cur = await db.execute(
                    f"""
                SELECT DISTINCT d.id, d.created_at, d.category, d.mode, d.brief_description, d.dream_id,
                       substr(d.brief_description, 1, 140) AS preview
                  FROM debates d
                  LEFT JOIN agent_voices v ON v.debate_id = d.id
                 WHERE instr(lower(coalesce(d.brief_description,'')), ?) > 0
                    OR instr(lower(coalesce(d.intention,'')), ?) > 0
                    OR instr(lower(coalesce(d.extra_context,'')), ?) > 0
                    OR instr(lower(coalesce(d.synthesis_text,'')), ?) > 0
                    OR instr(lower(coalesce(v.voice_text,'')), ?) > 0
                 {order_d}
                 LIMIT ?
                """,
                    (needle, needle, needle, needle, needle, lim),
                )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_debate_row(self, db: Any, debate_id: int) -> Optional[dict[str, Any]]:
        cur = await db.execute("SELECT * FROM debates WHERE id = ?", (debate_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def list_voices_for_debate(self, db: Any, debate_id: int) -> list[dict[str, Any]]:
        cur = await db.execute(
            """
            SELECT agent_name, voice_text
              FROM agent_voices
             WHERE debate_id = ?
             ORDER BY id
            """,
            (debate_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_commitment(self, db: Any, commitment_id: int) -> Optional[dict[str, Any]]:
        cur = await db.execute("SELECT * FROM commitments WHERE id = ?", (commitment_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def list_commitments_for_debate(
        self, db: Any, debate_id: int
    ) -> list[dict[str, Any]]:
        cur = await db.execute(
            """
            SELECT id, text, due_at, follow_up_at, status, created_at,
                   trigger_type, needs_attention, release_reason, completed_at
              FROM commitments
             WHERE debate_id = ?
             ORDER BY id DESC
            """,
            (debate_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_debate_row_minimal(
        self, db: Any, debate_id: int
    ) -> Optional[dict[str, Any]]:
        cur = await db.execute(
            "SELECT id, mode, dream_id FROM debates WHERE id = ?", (debate_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def project_id_for_dream(self, db: Any, dream_id: str) -> Optional[int]:
        cur = await db.execute("SELECT id FROM projects WHERE dream_id = ?", (dream_id,))
        row = await cur.fetchone()
        return int(row["id"]) if row else None

    async def insert_commitment(
        self,
        db: Any,
        *,
        text: str,
        debate_id: Optional[int] = None,
        project_id: Optional[int] = None,
        due_at: Optional[str] = None,
        follow_up_at: Optional[str] = None,
        trigger_type: str = "manual",
        needs_attention: int = 0,
    ) -> int:
        if trigger_type not in ("manual", "auto_72h", "stale_project"):
            trigger_type = "manual"
        cur = await db.execute(
            """
            INSERT INTO commitments (
              debate_id, project_id, text, due_at, follow_up_at,
              trigger_type, needs_attention, status
            )
            VALUES (?,?,?,?,?,?,?, 'open')
            """,
            (
                debate_id,
                project_id,
                text,
                due_at,
                follow_up_at,
                trigger_type,
                needs_attention,
            ),
        )
        return int(cur.lastrowid)

    async def touch_project_last_progress(self, db: Any, project_id: int) -> None:
        await db.execute(
            """
            UPDATE projects
               SET last_progress_at = ?,
                   status = CASE WHEN status = 'dreaming' THEN 'in_progress' ELSE status END
             WHERE id = ?
            """,
            (_utcnow(), project_id),
        )

    async def list_open_commitments_with_followup(self, db: Any) -> list[dict[str, Any]]:
        cur = await db.execute(
            """
            SELECT id, text, due_at, follow_up_at, status, created_at,
                   trigger_type, needs_attention, debate_id, project_id
              FROM commitments
             WHERE status = 'open' AND follow_up_at IS NOT NULL
            """
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def set_commitment_needs_attention(self, db: Any, commitment_id: int, text: str) -> None:
        await db.execute(
            """
            UPDATE commitments SET needs_attention = 1, text = ?
             WHERE id = ? AND status = 'open'
            """,
            (text, commitment_id),
        )

    async def list_commitments_due(
        self, db: Any, *, within_hours: int = 24
    ) -> list[dict[str, Any]]:
        """Zobowiązania otwarte z follow_up_at w przeszłości lub w oknie [now, now+within_hours]."""
        now = datetime.now(timezone.utc)
        horizon = now + timedelta(hours=max(1, min(within_hours, 8760)))
        out: list[dict[str, Any]] = []
        for row in await self.list_open_commitments_with_followup(db):
            raw = row.get("follow_up_at")
            if not raw:
                continue
            try:
                fu = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            if fu.tzinfo is None:
                fu = fu.replace(tzinfo=timezone.utc)
            if fu <= horizon:
                out.append(dict(row))
        return out

    async def release_commitment(
        self,
        db: Any,
        commitment_id: int,
        *,
        reason: str,
    ) -> bool:
        cur = await db.execute(
            """
            UPDATE commitments
               SET status = 'released',
                   release_reason = ?,
                   completed_at = ?
             WHERE id = ? AND status = 'open'
            """,
            (reason, _utcnow(), commitment_id),
        )
        return cur.rowcount > 0

    async def complete_commitment(
        self,
        db: Any,
        commitment_id: int,
        *,
        evidence_note: Optional[str] = None,
        evidence_url: Optional[str] = None,
    ) -> bool:
        note = (evidence_note or "").strip()
        url = (evidence_url or "").strip()
        tail = ""
        if note or url:
            tail = f"\n\n[Dowód odhaczenia] {note}" + (f" · {url}" if url else "")
        cur = await db.execute(
            """
            UPDATE commitments
               SET status = 'completed',
                   completed_at = ?,
                   text = text || ?
             WHERE id = ? AND status = 'open'
            """,
            (_utcnow(), tail, commitment_id),
        )
        return cur.rowcount > 0

    async def count_open_commitments_for_project(self, db: Any, project_id: int) -> int:
        cur = await db.execute(
            """
            SELECT COUNT(*) FROM commitments
             WHERE project_id = ? AND status = 'open'
            """,
            (project_id,),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def list_commitments_for_project(
        self, db: Any, project_id: int, limit: int = 50
    ) -> list[dict[str, Any]]:
        lim = max(1, min(limit, 200))
        dialect = getattr(db, "dialect", "sqlite")
        ord_created = (
            "ORDER BY datetime(created_at) DESC"
            if dialect == "sqlite"
            else "ORDER BY created_at DESC"
        )
        cur = await db.execute(
            f"""
            SELECT id, text, due_at, follow_up_at, status, created_at,
                   trigger_type, needs_attention, debate_id, completed_at, release_reason
              FROM commitments
             WHERE project_id = ?
             {ord_created}
             LIMIT ?
            """,
            (project_id, lim),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def has_open_stale_nudge(self, db: Any, project_id: int) -> bool:
        cur = await db.execute(
            """
            SELECT 1 FROM commitments
             WHERE project_id = ?
               AND status = 'open'
               AND trigger_type = 'stale_project'
             LIMIT 1
            """,
            (project_id,),
        )
        return await cur.fetchone() is not None

    async def next_open_followup_iso(self, db: Any, project_id: int) -> Optional[str]:
        cur = await db.execute(
            """
            SELECT follow_up_at FROM commitments
             WHERE project_id = ? AND status = 'open' AND follow_up_at IS NOT NULL
             ORDER BY follow_up_at ASC
             LIMIT 1
            """,
            (project_id,),
        )
        row = await cur.fetchone()
        return str(row[0]) if row and row[0] else None


repo = _Repo()
