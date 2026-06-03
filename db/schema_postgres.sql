-- Architekt Wolności — PostgreSQL: CURRENT DESIRED STATE (nie narzędzie migracji).
--
-- Ten plik opisuje docelowy kształt schematu i jest stosowany przez init_db
-- (DATABASE_URL → Postgres) WYŁĄCZNIE przez CREATE TABLE/INDEX IF NOT EXISTS.
-- Oznacza to, że NIE zmodyfikuje istniejących tabel (nie doda kolumn, nie
-- przebuduje PK). Zmiany na DZIAŁAJĄCYCH bazach idą przez wersjonowane
-- migracje w db/migrations/*.sql (śledzone w tabeli schema_migrations),
-- uruchamiane automatycznie po tym schemacie. Patrz README → "Migracje bazy".
--
-- Reguła: każda zmiana strukturalna tutaj MUSI mieć odpowiadającą migrację
-- w db/migrations/, inaczej istniejące bazy Postgres jej nie dostaną.

-- Faza 4 (multi-user): każdy wiersz ma tenant_id. Domyślnie 'default' (tryb single-user wstecznie kompatybilny).
CREATE TABLE IF NOT EXISTS dreams (
    id                          TEXT PRIMARY KEY,
    tenant_id                   TEXT NOT NULL DEFAULT 'default',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_brief                   TEXT NOT NULL,
    core_dream                  TEXT NOT NULL,
    value_anchor                TEXT NOT NULL,
    pillars_json                TEXT NOT NULL,
    milestones_json             TEXT NOT NULL,
    next_move_json              TEXT NOT NULL,
    completion_criteria_json    TEXT NOT NULL,
    functionality_checklist_json TEXT NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'living'
        CHECK (status IN ('living', 'fulfilled', 'released')),
    fulfilled_at                TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS debates (
    id                  SERIAL PRIMARY KEY,
    tenant_id           TEXT NOT NULL DEFAULT 'default',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    category            TEXT NOT NULL CHECK (category IN ('decyzja','projekt','marzenie','schemat')),
    mode                TEXT NOT NULL CHECK (mode IN ('pelna','marzen','schematy','codzienny')),
    brief_description   TEXT NOT NULL,
    intention           TEXT NULL,
    extra_context       TEXT NULL,
    dream_id            TEXT NULL REFERENCES dreams(id) ON DELETE SET NULL,
    parent_debate_id    INTEGER NULL REFERENCES debates(id) ON DELETE SET NULL,
    full_synthesis_json TEXT NULL,
    synthesis_text      TEXT NULL,
    cost_usd            DOUBLE PRECISION DEFAULT 0
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
    id           SERIAL PRIMARY KEY,
    tenant_id    TEXT NOT NULL DEFAULT 'default',
    debate_id    INTEGER NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
    agent_name   TEXT NOT NULL,
    voice_text   TEXT NOT NULL,
    tokens_in    INTEGER DEFAULT 0,
    tokens_out   INTEGER DEFAULT 0,
    cost_usd     DOUBLE PRECISION DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_voices_debate_id ON agent_voices(debate_id);

CREATE TABLE IF NOT EXISTS projects (
    id                SERIAL PRIMARY KEY,
    tenant_id         TEXT NOT NULL DEFAULT 'default',
    dream_id          TEXT NOT NULL REFERENCES dreams(id) ON DELETE CASCADE,
    status            TEXT NOT NULL DEFAULT 'dreaming'
        CHECK (status IN ('dreaming','in_progress','at_risk','stuck','completed','archived_consciously')),
    started_at        TIMESTAMPTZ NULL,
    last_progress_at  TIMESTAMPTZ NULL,
    completed_at      TIMESTAMPTZ NULL,
    archived_reason   TEXT NULL,
    archived_at       TIMESTAMPTZ NULL,
    UNIQUE (dream_id)
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

CREATE TABLE IF NOT EXISTS functionality_items (
    id            SERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    description   TEXT NOT NULL,
    is_done       SMALLINT NOT NULL DEFAULT 0 CHECK (is_done IN (0,1)),
    done_at       TIMESTAMPTZ NULL,
    evidence_url  TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_fitems_project_id ON functionality_items(project_id);

CREATE TABLE IF NOT EXISTS completion_audits (
    id             SERIAL PRIMARY KEY,
    tenant_id      TEXT NOT NULL DEFAULT 'default',
    project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    debate_id      INTEGER NULL REFERENCES debates(id) ON DELETE SET NULL,
    remaining_json TEXT NOT NULL,
    audited_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audits_project_id ON completion_audits(project_id);

CREATE TABLE IF NOT EXISTS commitments (
    id            SERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    debate_id     INTEGER NULL REFERENCES debates(id) ON DELETE SET NULL,
    project_id    INTEGER NULL REFERENCES projects(id) ON DELETE SET NULL,
    text          TEXT NOT NULL,
    due_at        TEXT NULL,
    follow_up_at  TEXT NULL,
    trigger_type  TEXT NOT NULL DEFAULT 'manual'
        CHECK (trigger_type IN ('manual','auto_72h','stale_project')),
    needs_attention SMALLINT NOT NULL DEFAULT 0 CHECK (needs_attention IN (0,1)),
    release_reason TEXT NULL,
    status        TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','completed','rescheduled','released')),
    completed_at  TIMESTAMPTZ NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_commitments_project_id ON commitments(project_id);
CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(status);
CREATE INDEX IF NOT EXISTS idx_commitments_follow_up ON commitments(follow_up_at);

CREATE TABLE IF NOT EXISTS agent_evolution (
    agent_name  TEXT NOT NULL,
    tenant_id   TEXT NOT NULL DEFAULT 'default',
    note_md     TEXT NOT NULL DEFAULT '',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_name, tenant_id)
);

CREATE TABLE IF NOT EXISTS users (
    username     TEXT PRIMARY KEY,
    pw_hash      TEXT NOT NULL,
    salt         TEXT NOT NULL,
    tenant_id    TEXT NOT NULL,
    display_name TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
