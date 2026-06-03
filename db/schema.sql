-- ┌──────────────────────────────────────────────────────────────────────┐
-- │  Architekt Wolności — schemat SQLite v1                              │
-- │  Wbija w bazę dwa AKSJOMATY: Architekturę Marzenia + Doprowadzanie   │
-- │  Projektów Do Końca (w pełni funkcjonalnym stanie).                  │
-- └──────────────────────────────────────────────────────────────────────┘

PRAGMA foreign_keys = ON;

-- AKSJOMAT 1: marzenia żyją przez wiele debat.
-- Faza 4 (multi-user): każdy wiersz ma tenant_id. Domyślnie 'default' (tryb single-user wstecznie kompatybilny).
CREATE TABLE IF NOT EXISTS dreams (
    id                          TEXT PRIMARY KEY,          -- UUID v4
    tenant_id                   TEXT NOT NULL DEFAULT 'default',
    created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    raw_brief                   TEXT NOT NULL,
    core_dream                  TEXT NOT NULL,
    value_anchor                TEXT NOT NULL,
    pillars_json                TEXT NOT NULL,             -- JSON array
    milestones_json             TEXT NOT NULL,             -- JSON array of {title,due,why_it_matters}
    next_move_json              TEXT NOT NULL,             -- JSON {action,when,smallest_form}
    completion_criteria_json    TEXT NOT NULL,             -- JSON array
    functionality_checklist_json TEXT NOT NULL,            -- JSON array (źródło prawdy dla AKSJOMATU 2)
    status                      TEXT NOT NULL DEFAULT 'living'
        CHECK (status IN ('living', 'fulfilled', 'released')),
    fulfilled_at                TEXT NULL
);

-- Debata = jeden cykl Rady (9 głosów + Syez).
CREATE TABLE IF NOT EXISTS debates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id           TEXT NOT NULL DEFAULT 'default',
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    category            TEXT NOT NULL CHECK (category IN ('decyzja','projekt','marzenie','schemat')),
    mode                TEXT NOT NULL CHECK (mode IN ('pelna','marzen','schematy','codzienny')),
    brief_description   TEXT NOT NULL,
    intention           TEXT NULL,
    extra_context       TEXT NULL,
    dream_id            TEXT NULL REFERENCES dreams(id) ON DELETE SET NULL,
    parent_debate_id    INTEGER NULL REFERENCES debates(id) ON DELETE SET NULL,
    full_synthesis_json TEXT NULL,                         -- strukturyzowany output Syeza
    synthesis_text      TEXT NULL,                         -- backup plain text
    cost_usd            REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_debates_dream_id ON debates(dream_id);
CREATE INDEX IF NOT EXISTS idx_debates_created_at ON debates(created_at);

CREATE TABLE IF NOT EXISTS dream_debate_link (
    tenant_id TEXT NOT NULL DEFAULT 'default',
    dream_id  TEXT NOT NULL REFERENCES dreams(id) ON DELETE CASCADE,
    debate_id INTEGER NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
    PRIMARY KEY (tenant_id, dream_id, debate_id)
);

CREATE TABLE IF NOT EXISTS agent_voices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id    TEXT NOT NULL DEFAULT 'default',
    debate_id    INTEGER NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
    agent_name   TEXT NOT NULL,
    voice_text   TEXT NOT NULL,
    tokens_in    INTEGER DEFAULT 0,
    tokens_out   INTEGER DEFAULT 0,
    cost_usd     REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_voices_debate_id ON agent_voices(debate_id);

-- AKSJOMAT 2: projekt = realizacja marzenia. Brak stanu ABANDONED — wyłącznie
-- ARCHIVED_CONSCIOUSLY (z `archived_reason` ≥ MIN_ARCHIVE_REASON_LEN znaków).
CREATE TABLE IF NOT EXISTS projects (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id         TEXT NOT NULL DEFAULT 'default',
    dream_id          TEXT NOT NULL REFERENCES dreams(id) ON DELETE CASCADE,
    status            TEXT NOT NULL DEFAULT 'dreaming'
        CHECK (status IN ('dreaming','in_progress','at_risk','stuck','completed','archived_consciously')),
    started_at        TEXT NULL,
    last_progress_at  TEXT NULL,
    completed_at      TEXT NULL,
    archived_reason   TEXT NULL,
    archived_at       TEXT NULL,
    UNIQUE (dream_id)        -- 1 projekt per marzenie (MVP; w przyszłości można zluzować)
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

CREATE TABLE IF NOT EXISTS functionality_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    description   TEXT NOT NULL,
    is_done       INTEGER NOT NULL DEFAULT 0 CHECK (is_done IN (0,1)),
    done_at       TEXT NULL,
    evidence_url  TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_fitems_project_id ON functionality_items(project_id);

CREATE TABLE IF NOT EXISTS completion_audits (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id      TEXT NOT NULL DEFAULT 'default',
    project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    debate_id      INTEGER NULL REFERENCES debates(id) ON DELETE SET NULL,
    remaining_json TEXT NOT NULL,
    audited_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audits_project_id ON completion_audits(project_id);

CREATE TABLE IF NOT EXISTS commitments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    debate_id     INTEGER NULL REFERENCES debates(id) ON DELETE SET NULL,
    project_id    INTEGER NULL REFERENCES projects(id) ON DELETE SET NULL,
    text          TEXT NOT NULL,
    due_at        TEXT NULL,
    follow_up_at  TEXT NULL,
    -- Faza 2: przełamywanie schematów — źródło zobowiązania (AKSJOMAT 2: brak cichego porzucania).
    trigger_type  TEXT NOT NULL DEFAULT 'manual'
        CHECK (trigger_type IN ('manual','auto_72h','stale_project')),
    needs_attention INTEGER NOT NULL DEFAULT 0 CHECK (needs_attention IN (0,1)),
    release_reason TEXT NULL,
    status        TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','completed','rescheduled','released')),
    completed_at  TEXT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_commitments_project_id ON commitments(project_id);
CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(status);
CREATE INDEX IF NOT EXISTS idx_commitments_follow_up ON commitments(follow_up_at);

-- P5 / Faza 3 (MVP): rolling notatka per agent z ostatnich debat → kolejne prompty.
CREATE TABLE IF NOT EXISTS agent_evolution (
    agent_name  TEXT NOT NULL,
    tenant_id   TEXT NOT NULL DEFAULT 'default',
    note_md     TEXT NOT NULL DEFAULT '',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (agent_name, tenant_id)
);

-- Faza 4: użytkownicy (multi-user auth).
CREATE TABLE IF NOT EXISTS users (
    username     TEXT PRIMARY KEY,
    pw_hash      TEXT NOT NULL,
    salt         TEXT NOT NULL,
    tenant_id    TEXT NOT NULL,
    display_name TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
