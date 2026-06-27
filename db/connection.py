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

from db.tenant import current_tenant_id as _tid  # Faza 4 — multi-user

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
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.executescript(schema)
            await _migrate_debates_parent_column(db)
            await _migrate_commitments_phase2(db)
            await _migrate_agent_evolution_table(db)
            await _migrate_users_table(db)
            await _migrate_tenant_id_columns(db)  # Faza 4
            await _migrate_dream_debate_link_tenant(db)
            await _migrate_feedback_onboarding_tables(db)
            await _migrate_debates_fts(db)         # FTS5 full-text search
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


async def _migrate_tenant_id_columns(db: Any) -> None:
    """Faza 4 — multi-user: idempotentne dodanie kolumny tenant_id do tabel z danymi użytkownika.
    Wszystkie wiersze sprzed migracji dostają tenant_id = 'default' (tryb single-user wstecznie OK).
    Indeksy po tenant_id dla najczęściej listowanych tabel.
    """
    tables = (
        "dreams",
        "debates",
        "agent_voices",
        "projects",
        "functionality_items",
        "completion_audits",
        "commitments",
    )
    for tbl in tables:
        cur = await db.execute(f"PRAGMA table_info({tbl})")
        rows = await cur.fetchall()
        col_names = {r[1] for r in rows}
        if "tenant_id" not in col_names:
            await db.execute(
                f"ALTER TABLE {tbl} ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'"
            )
    for tbl in ("dreams", "debates", "projects", "commitments", "agent_voices", "functionality_items"):
        await db.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{tbl}_tenant_id ON {tbl}(tenant_id)"
        )


async def _migrate_dream_debate_link_tenant(db: Any) -> None:
    """Faza 4+: tenant_id na junction dream↔debate (SQLite — bez RLS, defense-in-depth w repo)."""
    cur = await db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dream_debate_link'"
    )
    if not await cur.fetchone():
        return
    cur = await db.execute("PRAGMA table_info(dream_debate_link)")
    col_names = {r[1] for r in await cur.fetchall()}
    if "tenant_id" not in col_names:
        await db.execute(
            "ALTER TABLE dream_debate_link ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'"
        )
    await db.execute(
        """
        UPDATE dream_debate_link
           SET tenant_id = (
               SELECT tenant_id FROM dreams WHERE dreams.id = dream_debate_link.dream_id LIMIT 1
           )
         WHERE tenant_id = 'default'
           AND EXISTS (SELECT 1 FROM dreams WHERE dreams.id = dream_debate_link.dream_id)
        """
    )
    await db.execute(
        """
        UPDATE dream_debate_link
           SET tenant_id = (
               SELECT tenant_id FROM debates WHERE debates.id = dream_debate_link.debate_id LIMIT 1
           )
         WHERE tenant_id = 'default'
           AND EXISTS (SELECT 1 FROM debates WHERE debates.id = dream_debate_link.debate_id)
        """
    )


async def _migrate_feedback_onboarding_tables(db: Any) -> None:
    """Tabele feedback / onboarding_answers (Postgres: migracje 0003/0004)."""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id     TEXT NOT NULL DEFAULT 'default',
            user_subject  TEXT,
            rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            what_worked   TEXT NOT NULL DEFAULT '',
            what_broke    TEXT NOT NULL DEFAULT '',
            debate_id     INTEGER,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (tenant_id <> '')
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_feedback_tenant_id ON feedback(tenant_id)"
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS onboarding_answers (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id     TEXT NOT NULL DEFAULT 'default',
            user_subject  TEXT,
            question_idx  INTEGER NOT NULL CHECK (question_idx >= 0),
            answer        TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (tenant_id <> ''),
            UNIQUE (tenant_id, user_subject, question_idx)
        )
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_onboarding_answers_tenant_user
            ON onboarding_answers(tenant_id, user_subject)
        """
    )


async def _migrate_debates_fts(db: Any) -> None:
    """FTS5 virtual table dla wyszukiwania debat — zastępuje instr() full-table scan.

    Idempotentne: sprawdza czy tabela istnieje przed stworzeniem.
    Trigger keep_debates_fts_* utrzymuje spójność przy INSERT/UPDATE/DELETE.
    """
    cur = await db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='debates_fts'"
    )
    if await cur.fetchone():
        return  # już istnieje

    await db.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS debates_fts USING fts5(
            debate_id UNINDEXED,
            tenant_id UNINDEXED,
            brief_description,
            intention,
            extra_context,
            synthesis_text,
            content='debates',
            content_rowid='id'
        )
        """
    )
    # Populate from existing rows
    await db.execute(
        """
        INSERT INTO debates_fts(rowid, debate_id, tenant_id, brief_description, intention, extra_context, synthesis_text)
        SELECT id, id, tenant_id,
               coalesce(brief_description,''),
               coalesce(intention,''),
               coalesce(extra_context,''),
               coalesce(synthesis_text,'')
        FROM debates
        """
    )
    # Triggers to keep FTS in sync
    await db.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS keep_debates_fts_insert
        AFTER INSERT ON debates BEGIN
            INSERT INTO debates_fts(rowid, debate_id, tenant_id, brief_description, intention, extra_context, synthesis_text)
            VALUES (new.id, new.id, new.tenant_id,
                    coalesce(new.brief_description,''), coalesce(new.intention,''),
                    coalesce(new.extra_context,''), coalesce(new.synthesis_text,''));
        END;

        CREATE TRIGGER IF NOT EXISTS keep_debates_fts_update
        AFTER UPDATE ON debates BEGIN
            INSERT INTO debates_fts(debates_fts, rowid, debate_id, tenant_id, brief_description, intention, extra_context, synthesis_text)
            VALUES ('delete', old.id, old.id, old.tenant_id,
                    coalesce(old.brief_description,''), coalesce(old.intention,''),
                    coalesce(old.extra_context,''), coalesce(old.synthesis_text,''));
            INSERT INTO debates_fts(rowid, debate_id, tenant_id, brief_description, intention, extra_context, synthesis_text)
            VALUES (new.id, new.id, new.tenant_id,
                    coalesce(new.brief_description,''), coalesce(new.intention,''),
                    coalesce(new.extra_context,''), coalesce(new.synthesis_text,''));
        END;

        CREATE TRIGGER IF NOT EXISTS keep_debates_fts_delete
        AFTER DELETE ON debates BEGIN
            INSERT INTO debates_fts(debates_fts, rowid, debate_id, tenant_id, brief_description, intention, extra_context, synthesis_text)
            VALUES ('delete', old.id, old.id, old.tenant_id,
                    coalesce(old.brief_description,''), coalesce(old.intention,''),
                    coalesce(old.extra_context,''), coalesce(old.synthesis_text,''));
        END;
        """
    )


async def _migrate_agent_evolution_table(db: Any) -> None:
    """P5→Faza 4: rolling pamięć ewolucyjna per agent per tenant (idempotentne)."""
    cur = await db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_evolution'"
    )
    if await cur.fetchone():
        # Istniejąca tabela — dodaj tenant_id jeśli brakuje (migracja PK wymaga recreate)
        try:
            cur2 = await db.execute("PRAGMA table_info(agent_evolution)")
            cols = [r[1] for r in await cur2.fetchall()]
            if "tenant_id" not in cols:
                await db.execute("ALTER TABLE agent_evolution RENAME TO _agent_evolution_old")
                await db.execute(
                    """CREATE TABLE agent_evolution (
                        agent_name TEXT NOT NULL,
                        tenant_id  TEXT NOT NULL DEFAULT 'default',
                        note_md    TEXT NOT NULL DEFAULT '',
                        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                        PRIMARY KEY (agent_name, tenant_id)
                    )"""
                )
                await db.execute(
                    "INSERT INTO agent_evolution (agent_name, tenant_id, note_md, updated_at) "
                    "SELECT agent_name, 'default', note_md, updated_at FROM _agent_evolution_old"
                )
                await db.execute("DROP TABLE _agent_evolution_old")
        except Exception:
            pass
        return
    await db.execute(
        """
        CREATE TABLE agent_evolution (
            agent_name  TEXT NOT NULL,
            tenant_id   TEXT NOT NULL DEFAULT 'default',
            note_md     TEXT NOT NULL DEFAULT '',
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (agent_name, tenant_id)
        )
        """
    )


async def _migrate_users_table(db: Any) -> None:
    """Faza 4: tabela użytkowników (idempotentne)."""
    await db.execute(
        """CREATE TABLE IF NOT EXISTS users (
            username     TEXT PRIMARY KEY,
            pw_hash      TEXT NOT NULL,
            salt         TEXT NOT NULL,
            tenant_id    TEXT NOT NULL,
            display_name TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )


async def get_db() -> AsyncIterator[Any]:
    """Jedno połączenie na żądanie — SQLite lub Postgres (`DATABASE_URL`)."""
    from db.backend import acquire_http_db, runtime_use_postgres

    if not runtime_use_postgres() and not _AIOSQLITE_OK:
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
        """Zapisuje DreamArchitecture. Zwraca dream_id. Stempel tenant_id z ContextVar (Faza 4)."""
        await db.execute(
            """
            INSERT INTO dreams (
              id, tenant_id, created_at, raw_brief, core_dream, value_anchor,
              pillars_json, milestones_json, next_move_json,
              completion_criteria_json, functionality_checklist_json,
              status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?, 'living')
            """,
            (
                dream.dream_id,
                _tid(),
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
        cur = await db.execute(
            "SELECT * FROM dreams WHERE id = ? AND tenant_id = ?", (dream_id, _tid())
        )
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
        tid = _tid()
        cur = await db.execute(
            "SELECT id FROM projects WHERE dream_id = ? AND tenant_id = ?",
            (dream_id, tid),
        )
        row = await cur.fetchone()
        if row:
            return int(row["id"])
        cur = await db.execute(
            "INSERT INTO projects (dream_id, tenant_id, status, started_at) "
            "VALUES (?, ?, 'dreaming', ?)",
            (dream_id, tid, _utcnow()),
        )
        project_id = int(cur.lastrowid)
        for desc in functionality_checklist:
            await db.execute(
                "INSERT INTO functionality_items (project_id, tenant_id, description) "
                "VALUES (?, ?, ?)",
                (project_id, tid, desc),
            )
        return project_id

    async def list_active_projects(self, db: Any) -> list[dict[str, Any]]:
        cur = await db.execute(
            """
            SELECT p.*, d.core_dream
              FROM projects p
              JOIN dreams d ON d.id = p.dream_id
             WHERE p.status IN ('dreaming','in_progress','at_risk','stuck')
               AND p.tenant_id = ?
             ORDER BY p.started_at DESC
            """,
            (_tid(),),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_project(self, db: Any, project_id: int) -> Optional[dict[str, Any]]:
        cur = await db.execute(
            "SELECT * FROM projects WHERE id = ? AND tenant_id = ?",
            (project_id, _tid()),
        )
        row = await cur.fetchone()
        if not row:
            return None
        p = dict(row)
        cur = await db.execute(
            "SELECT * FROM functionality_items WHERE project_id = ? AND tenant_id = ? ORDER BY id",
            (project_id, _tid()),
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
        vals.extend([project_id, _tid()])
        await db.execute(
            f"UPDATE projects SET {', '.join(cols)} WHERE id = ? AND tenant_id = ?",
            tuple(vals),
        )

    async def mark_functionality_done(
        self,
        db: Any,
        item_id: int,
        evidence_url: Optional[str] = None,
    ) -> Optional[int]:
        """Odhacza pozycję i zwraca project_id (lub None gdy nie znaleziono / inny tenant)."""
        cur = await db.execute(
            "SELECT project_id FROM functionality_items WHERE id = ? AND tenant_id = ?",
            (item_id, _tid()),
        )
        row = await cur.fetchone()
        if not row:
            return None
        project_id = int(row["project_id"])
        await db.execute(
            """
            UPDATE functionality_items
               SET is_done = 1, done_at = ?, evidence_url = COALESCE(?, evidence_url)
             WHERE id = ? AND tenant_id = ?
            """,
            (_utcnow(), evidence_url, item_id, _tid()),
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
              tenant_id, category, mode, brief_description, intention, extra_context,
              dream_id, parent_debate_id
            )
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                _tid(),
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

    async def count_debates_for_tenant(self, db: Any, tenant_id: str) -> int:
        """Zlicza debaty dla konkretnego tenanta (np. limity demo)."""
        cur = await db.execute(
            "SELECT COUNT(*) AS n FROM debates WHERE tenant_id = ?",
            (tenant_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return 0
        return int(row[0] if not hasattr(row, "keys") else row["n"])

    async def link_dream_debate(self, db: Any, dream_id: str, debate_id: int) -> None:
        tid = _tid()
        cur = await db.execute(
            """
            SELECT 1 FROM dreams d
            INNER JOIN debates b ON b.id = ? AND b.tenant_id = d.tenant_id
            WHERE d.id = ? AND d.tenant_id = ?
            """,
            (debate_id, dream_id, tid),
        )
        if not await cur.fetchone():
            raise ValueError(
                f"link_dream_debate: dream={dream_id!r} debate={debate_id} "
                f"nie należą do tenanta {tid!r}"
            )
        await db.execute(
            "INSERT OR IGNORE INTO dream_debate_link (tenant_id, dream_id, debate_id) "
            "VALUES (?, ?, ?)",
            (tid, dream_id, debate_id),
        )

    async def save_voice(
        self,
        db: Any,
        debate_id: int,
        agent_name: str,
        voice_text: str,
    ) -> None:
        await db.execute(
            "INSERT INTO agent_voices (tenant_id, debate_id, agent_name, voice_text) VALUES (?,?,?,?)",
            (_tid(), debate_id, agent_name, voice_text),
        )

    async def list_agent_evolution(self, db: Any, council_mode: str = "personal") -> dict[str, str]:
        # Izolacja ewolucji per tryb: fa2 używa wirtualnego tenanta (sufiks),
        # by notatki biznesowe nie mieszały się z osobistymi. Zero migracji PK.
        tid = f"{_tid()}:fa2" if council_mode == "fa2" else _tid()
        cur = await db.execute(
            "SELECT agent_name, note_md FROM agent_evolution WHERE tenant_id = ?",
            (tid,),
        )
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
        council_mode: str = "personal",
    ) -> None:
        raw = " ".join((voice_text or "").split())
        if not raw or raw.startswith("[błąd") or raw.startswith("[error"):
            return
        snippet = raw[:snippet_cap].strip()
        if not snippet:
            return
        # Izolacja per tryb — patrz list_agent_evolution.
        tid = f"{_tid()}:fa2" if council_mode == "fa2" else _tid()
        cur = await db.execute(
            "SELECT note_md FROM agent_evolution WHERE agent_name = ? AND tenant_id = ?",
            (agent_name, tid),
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
            INSERT INTO agent_evolution (agent_name, tenant_id, note_md, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(agent_name, tenant_id) DO UPDATE SET
                note_md = excluded.note_md,
                updated_at = excluded.updated_at
            """,
            (agent_name, tid, merged),
        )

    async def list_recent_voices_for_agent(
        self,
        db: Any,
        agent_name: str,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Faza 3: ostatnie głosy agenta (do przebudowy ewolucji)."""
        cur = await db.execute(
            "SELECT voice_text, debate_id FROM agent_voices "
            "WHERE agent_name = ? AND tenant_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (agent_name, _tid(), max(1, min(limit, 100))),
        )
        rows = await cur.fetchall()
        return [{"voice_text": str(r[0] or ""), "debate_id": r[1]} for r in rows]

    async def save_synthesis(
        self,
        db: Any,
        debate_id: int,
        synthesis_text: str,
        synthesis_json: Optional[dict[str, Any]],
    ) -> None:
        await db.execute(
            "UPDATE debates SET synthesis_text = ?, full_synthesis_json = ? "
            "WHERE id = ? AND tenant_id = ?",
            (
                synthesis_text,
                json.dumps(synthesis_json, ensure_ascii=False) if synthesis_json else None,
                debate_id,
                _tid(),
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
            "INSERT INTO completion_audits (tenant_id, project_id, debate_id, remaining_json) "
            "VALUES (?,?,?,?)",
            (_tid(), project_id, debate_id, json.dumps(audit, ensure_ascii=False)),
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
        tid = _tid()
        if not q:
            cur = await db.execute(
                f"""
                SELECT id, created_at, category, mode, brief_description, dream_id,
                       parent_debate_id,
                       substr(brief_description, 1, 140) AS preview
                  FROM debates
                 WHERE tenant_id = ?
                 {order}
                 LIMIT ?
                """,
                (tid, lim),
            )
        else:
            needle = q.lower()[:500]
            if dialect == "postgres":
                where = """
                 WHERE d.tenant_id = $1
                   AND (POSITION($2 IN lower(coalesce(d.brief_description,''))) > 0
                    OR POSITION($3 IN lower(coalesce(d.intention,''))) > 0
                    OR POSITION($4 IN lower(coalesce(d.extra_context,''))) > 0
                    OR POSITION($5 IN lower(coalesce(d.synthesis_text,''))) > 0
                    OR POSITION($6 IN lower(coalesce(v.voice_text,''))) > 0)
                """
                sql = f"""
                SELECT DISTINCT d.id, d.created_at, d.category, d.mode, d.brief_description, d.dream_id,
                       d.parent_debate_id,
                       substr(d.brief_description::text, 1, 140) AS preview
                  FROM debates d
                  LEFT JOIN agent_voices v ON v.debate_id = d.id
                 {where}
                 {order_d}
                 LIMIT $7
                """
                cur = await db.execute(
                    sql,
                    (tid, needle, needle, needle, needle, needle, lim),
                )
            else:
                # FTS5 path — sub-millisecond at any scale; fallback to instr() if table absent
                fts_check = await db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='debates_fts'"
                )
                use_fts = await fts_check.fetchone() is not None
                if use_fts:
                    cur = await db.execute(
                        f"""
                        SELECT DISTINCT d.id, d.created_at, d.category, d.mode,
                               d.brief_description, d.dream_id,
                               d.parent_debate_id,
                               substr(d.brief_description, 1, 140) AS preview
                          FROM debates_fts f
                          JOIN debates d ON d.id = f.rowid
                         WHERE f.debates_fts MATCH ?
                           AND d.tenant_id = ?
                         {order_d}
                         LIMIT ?
                        """,
                        (needle, tid, lim),
                    )
                else:
                    # Legacy fallback (pre-migration)
                    cur = await db.execute(
                        f"""
                        SELECT DISTINCT d.id, d.created_at, d.category, d.mode,
                               d.brief_description, d.dream_id,
                               d.parent_debate_id,
                               substr(d.brief_description, 1, 140) AS preview
                          FROM debates d
                          LEFT JOIN agent_voices v ON v.debate_id = d.id
                         WHERE d.tenant_id = ?
                           AND (instr(lower(coalesce(d.brief_description,'')), ?) > 0
                            OR instr(lower(coalesce(d.intention,'')), ?) > 0
                            OR instr(lower(coalesce(d.extra_context,'')), ?) > 0
                            OR instr(lower(coalesce(d.synthesis_text,'')), ?) > 0
                            OR instr(lower(coalesce(v.voice_text,'')), ?) > 0)
                         {order_d}
                         LIMIT ?
                        """,
                        (tid, needle, needle, needle, needle, needle, lim),
                    )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_debate_row(self, db: Any, debate_id: int) -> Optional[dict[str, Any]]:
        cur = await db.execute(
            "SELECT * FROM debates WHERE id = ? AND tenant_id = ?",
            (debate_id, _tid()),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def list_voices_for_debate(self, db: Any, debate_id: int) -> list[dict[str, Any]]:
        cur = await db.execute(
            """
            SELECT agent_name, voice_text
              FROM agent_voices
             WHERE debate_id = ? AND tenant_id = ?
             ORDER BY id
            """,
            (debate_id, _tid()),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def resolve_root_debate_ids(
        self, db: Any, debate_ids: list[int], *, max_depth: int = 32
    ) -> dict[int, int]:
        """Dla każdej debaty z listy zwraca id roota jej wątku (debata bez parenta).

        Liczone po stronie serwera (a nie na froncie po `groupIntoThreads`), żeby
        sidebar history grupował poprawnie nawet gdy część rodziców wypadła poza
        widoczny limit (np. /history?limit=30 a wątek ma 35 tur). Cache w pamięci
        per-wywołanie eliminuje redundantne zapytania w obrębie tej samej listy.
        """
        if not debate_ids:
            return {}
        tid = _tid()
        parent_cache: dict[int, Optional[int]] = {}

        async def fetch_parent(d_id: int) -> Optional[int]:
            if d_id in parent_cache:
                return parent_cache[d_id]
            cur = await db.execute(
                "SELECT parent_debate_id FROM debates WHERE id = ? AND tenant_id = ?",
                (d_id, tid),
            )
            row = await cur.fetchone()
            parent = None if row is None else row["parent_debate_id"]
            parent_cache[d_id] = int(parent) if parent is not None else None
            return parent_cache[d_id]

        roots: dict[int, int] = {}
        for d_id in debate_ids:
            current = int(d_id)
            visited: set[int] = set()
            for _ in range(max_depth):
                if current in visited:
                    break
                visited.add(current)
                parent = await fetch_parent(current)
                if parent is None:
                    break
                current = parent
            roots[int(d_id)] = current
        return roots

    async def list_debate_chain(
        self,
        db: Any,
        leaf_debate_id: int,
        *,
        max_turns: int = 4,
    ) -> list[dict[str, Any]]:
        """Ostatnie max_turns tur wątku (najstarsza → najnowsza), po parent_debate_id."""
        visited: set[int] = set()
        newest_first: list[dict[str, Any]] = []
        current_id: Optional[int] = leaf_debate_id

        while current_id is not None and len(newest_first) < max_turns:
            if current_id in visited:
                break
            visited.add(current_id)

            cur = await db.execute(
                """
                SELECT id, brief_description, synthesis_text, parent_debate_id
                  FROM debates
                 WHERE id = ? AND tenant_id = ?
                """,
                (current_id, _tid()),
            )
            row = await cur.fetchone()
            if not row:
                break

            row_d = dict(row)
            newest_first.append(
                {
                    "id": int(row_d["id"]),
                    "brief_description": row_d["brief_description"],
                    "synthesis_text": row_d.get("synthesis_text"),
                }
            )
            parent = row_d.get("parent_debate_id")
            current_id = int(parent) if parent is not None else None

        newest_first.reverse()
        return newest_first

    async def get_commitment(self, db: Any, commitment_id: int) -> Optional[dict[str, Any]]:
        cur = await db.execute(
            "SELECT * FROM commitments WHERE id = ? AND tenant_id = ?",
            (commitment_id, _tid()),
        )
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
             WHERE debate_id = ? AND tenant_id = ?
             ORDER BY id DESC
            """,
            (debate_id, _tid()),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_debate_row_minimal(
        self, db: Any, debate_id: int
    ) -> Optional[dict[str, Any]]:
        cur = await db.execute(
            "SELECT id, mode, dream_id FROM debates WHERE id = ? AND tenant_id = ?",
            (debate_id, _tid()),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def project_id_for_dream(self, db: Any, dream_id: str) -> Optional[int]:
        cur = await db.execute(
            "SELECT id FROM projects WHERE dream_id = ? AND tenant_id = ?",
            (dream_id, _tid()),
        )
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
              tenant_id, debate_id, project_id, text, due_at, follow_up_at,
              trigger_type, needs_attention, status
            )
            VALUES (?,?,?,?,?,?,?,?, 'open')
            """,
            (
                _tid(),
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
             WHERE id = ? AND tenant_id = ?
            """,
            (_utcnow(), project_id, _tid()),
        )

    async def list_open_commitments_with_followup(self, db: Any) -> list[dict[str, Any]]:
        cur = await db.execute(
            """
            SELECT id, text, due_at, follow_up_at, status, created_at,
                   trigger_type, needs_attention, debate_id, project_id
              FROM commitments
             WHERE status = 'open' AND follow_up_at IS NOT NULL
               AND tenant_id = ?
            """,
            (_tid(),),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def set_commitment_needs_attention(self, db: Any, commitment_id: int, text: str) -> None:
        await db.execute(
            """
            UPDATE commitments SET needs_attention = 1, text = ?
             WHERE id = ? AND status = 'open' AND tenant_id = ?
            """,
            (text, commitment_id, _tid()),
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
             WHERE id = ? AND status = 'open' AND tenant_id = ?
            """,
            (reason, _utcnow(), commitment_id, _tid()),
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
             WHERE id = ? AND status = 'open' AND tenant_id = ?
            """,
            (_utcnow(), tail, commitment_id, _tid()),
        )
        return cur.rowcount > 0

    async def count_open_commitments_for_project(self, db: Any, project_id: int) -> int:
        cur = await db.execute(
            """
            SELECT COUNT(*) FROM commitments
             WHERE project_id = ? AND status = 'open' AND tenant_id = ?
            """,
            (project_id, _tid()),
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
             WHERE project_id = ? AND tenant_id = ?
             {ord_created}
             LIMIT ?
            """,
            (project_id, _tid(), lim),
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
               AND tenant_id = ?
             LIMIT 1
            """,
            (project_id, _tid()),
        )
        return await cur.fetchone() is not None

    async def next_open_followup_iso(self, db: Any, project_id: int) -> Optional[str]:
        cur = await db.execute(
            """
            SELECT follow_up_at FROM commitments
             WHERE project_id = ? AND status = 'open'
               AND follow_up_at IS NOT NULL
               AND tenant_id = ?
             ORDER BY follow_up_at ASC
             LIMIT 1
            """,
            (project_id, _tid()),
        )
        row = await cur.fetchone()
        return str(row[0]) if row and row[0] else None

    async def _table_exists(self, db: Any, name: str) -> bool:
        cur = await db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        )
        if await cur.fetchone():
            return True
        # Postgres / inne backendy
        try:
            cur = await db.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
                (name,),
            )
            return await cur.fetchone() is not None
        except Exception:
            return False

    async def _rows_to_dicts(self, db: Any, sql: str, params: tuple) -> list[dict[str, Any]]:
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def insert_feedback(
        self,
        db: Any,
        *,
        user_subject: str,
        rating: int,
        what_worked: str,
        what_broke: str,
        debate_id: Optional[int],
        created_at: str,
    ) -> None:
        await db.execute(
            """
            INSERT INTO feedback (
                tenant_id, user_subject, rating, what_worked, what_broke, debate_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (_tid(), user_subject, rating, what_worked, what_broke, debate_id, created_at),
        )

    async def upsert_onboarding_answer(
        self,
        db: Any,
        *,
        user_subject: str,
        question_idx: int,
        answer: str,
        updated_at: str,
    ) -> None:
        await db.execute(
            """
            INSERT INTO onboarding_answers (
                tenant_id, user_subject, question_idx, answer, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, user_subject, question_idx) DO UPDATE SET
                answer = excluded.answer,
                updated_at = excluded.updated_at
            """,
            (_tid(), user_subject, question_idx, answer, updated_at, updated_at),
        )

    async def export_tenant_data(self, db: Any, *, tenant_id: str) -> dict[str, Any]:
        """Eksport wszystkich danych tenanta (RODO — prawo dostępu)."""
        tid = tenant_id
        dream_debate_link = await self._rows_to_dicts(
            db,
            """
            SELECT tenant_id, dream_id, debate_id
              FROM dream_debate_link
             WHERE tenant_id = ?
            """,
            (tid,),
        )
        out: dict[str, Any] = {
            "tenant_id": tid,
            "dreams": await self._rows_to_dicts(
                db, "SELECT * FROM dreams WHERE tenant_id = ?", (tid,)
            ),
            "debates": await self._rows_to_dicts(
                db, "SELECT * FROM debates WHERE tenant_id = ?", (tid,)
            ),
            "dream_debate_link": dream_debate_link,
            "agent_voices": await self._rows_to_dicts(
                db, "SELECT * FROM agent_voices WHERE tenant_id = ?", (tid,)
            ),
            "projects": await self._rows_to_dicts(
                db, "SELECT * FROM projects WHERE tenant_id = ?", (tid,)
            ),
            "functionality_items": await self._rows_to_dicts(
                db, "SELECT * FROM functionality_items WHERE tenant_id = ?", (tid,)
            ),
            "completion_audits": await self._rows_to_dicts(
                db, "SELECT * FROM completion_audits WHERE tenant_id = ?", (tid,)
            ),
            "commitments": await self._rows_to_dicts(
                db, "SELECT * FROM commitments WHERE tenant_id = ?", (tid,)
            ),
            "agent_evolution": await self._rows_to_dicts(
                db, "SELECT * FROM agent_evolution WHERE tenant_id = ?", (tid,)
            ),
            "users": await self._rows_to_dicts(
                db, "SELECT username, tenant_id, display_name, created_at FROM users WHERE tenant_id = ?",
                (tid,),
            ),
        }
        try:
            if await self._table_exists(db, "feedback"):
                out["feedback"] = await self._rows_to_dicts(
                    db, "SELECT * FROM feedback WHERE tenant_id = ?", (tid,)
                )
        except Exception:
            pass
        if await self._table_exists(db, "onboarding_answers"):
            try:
                out["onboarding_answers"] = await self._rows_to_dicts(
                    db, "SELECT * FROM onboarding_answers WHERE tenant_id = ?", (tid,)
                )
            except Exception:
                pass
        return out

    async def _delete_where_tenant(
        self, db: Any, table: str, tenant_id: str
    ) -> int:
        cur = await db.execute(
            f"DELETE FROM {table} WHERE tenant_id = ?",
            (tenant_id,),
        )
        return int(cur.rowcount or 0)

    async def _purge_debates_for_tenant(self, db: Any, tenant_id: str) -> int:
        """Usuwa debaty tenanta; FTS5 synchronizuje triggery AFTER DELETE na debates."""
        try:
            cur = await db.execute(
                "DELETE FROM debates WHERE tenant_id = ?",
                (tenant_id,),
            )
            return int(cur.rowcount or 0)
        except Exception:
            cur = await db.execute(
                "SELECT id FROM debates WHERE tenant_id = ?",
                (tenant_id,),
            )
            debate_ids = [int(r[0]) for r in await cur.fetchall()]
            for debate_id in debate_ids:
                await db.execute(
                    "DELETE FROM debates WHERE id = ? AND tenant_id = ?",
                    (debate_id, tenant_id),
                )
            return len(debate_ids)

    async def purge_tenant_data(self, db: Any, *, tenant_id: str) -> dict[str, int]:
        """Trwałe usunięcie wszystkich danych tenanta (RODO). Zwraca liczniki per tabela."""
        tid = tenant_id
        deleted: dict[str, int] = {}

        cur = await db.execute(
            "DELETE FROM dream_debate_link WHERE tenant_id = ?",
            (tid,),
        )
        deleted["dream_debate_link"] = int(cur.rowcount or 0)

        for table in (
            "agent_voices",
            "completion_audits",
            "commitments",
            "functionality_items",
            "projects",
        ):
            deleted[table] = await self._delete_where_tenant(db, table, tid)

        for table in ("feedback", "onboarding_answers"):
            if await self._table_exists(db, table):
                deleted[table] = await self._delete_where_tenant(db, table, tid)

        deleted["debates"] = await self._purge_debates_for_tenant(db, tid)
        deleted["dreams"] = await self._delete_where_tenant(db, "dreams", tid)
        deleted["agent_evolution"] = await self._delete_where_tenant(
            db, "agent_evolution", tid
        )
        deleted["users"] = await self._delete_where_tenant(db, "users", tid)
        return deleted


repo = _Repo()
