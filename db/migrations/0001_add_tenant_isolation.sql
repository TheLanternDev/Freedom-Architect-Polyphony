-- Migration 0001 — Faza 4: izolacja multi-tenant (PostgreSQL)
--
-- Cel: doprowadzić ISTNIEJĄCE bazy Postgres do stanu opisanego w
-- db/schema_postgres.sql. Nowe bazy dostają ten stan od razu przez schema;
-- ta migracja jest dla baz utworzonych PRZED dodaniem tenant_id / users /
-- composite PK na agent_evolution.
--
-- Idempotentna i bezpieczna do uruchomienia na działającej bazie:
-- wszystkie operacje używają IF [NOT] EXISTS. Wiersze sprzed migracji
-- dostają tenant_id = 'default' (tryb single-user pozostaje wstecznie OK).

-- 1) tenant_id na tabelach z danymi użytkownika --------------------------------
ALTER TABLE dreams              ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE debates             ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE agent_voices        ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE projects            ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE functionality_items ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE completion_audits   ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE commitments         ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';

-- Indeksy po tenant_id dla najczęściej listowanych tabel.
CREATE INDEX IF NOT EXISTS idx_dreams_tenant_id              ON dreams(tenant_id);
CREATE INDEX IF NOT EXISTS idx_debates_tenant_id             ON debates(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_voices_tenant_id        ON agent_voices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_projects_tenant_id            ON projects(tenant_id);
CREATE INDEX IF NOT EXISTS idx_functionality_items_tenant_id ON functionality_items(tenant_id);
CREATE INDEX IF NOT EXISTS idx_commitments_tenant_id         ON commitments(tenant_id);

-- 2) tabela users (multi-user auth) -------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    username     TEXT PRIMARY KEY,
    pw_hash      TEXT NOT NULL,
    salt         TEXT NOT NULL,
    tenant_id    TEXT NOT NULL,
    display_name TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3) agent_evolution: tenant_id + composite PK (agent_name, tenant_id) ---------
-- Na starej bazie tabela mogła mieć PK tylko na agent_name. Dodajemy kolumnę,
-- usuwamy stary PK i zakładamy nowy composite — wszystko warunkowo, więc
-- ponowne uruchomienie nie zaszkodzi.
ALTER TABLE agent_evolution ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';

DO $$
DECLARE
    pk_name TEXT;
    pk_cols TEXT;
BEGIN
    SELECT con.conname,
           pg_get_constraintdef(con.oid)
      INTO pk_name, pk_cols
      FROM pg_constraint con
      JOIN pg_class rel ON rel.oid = con.conrelid
     WHERE rel.relname = 'agent_evolution'
       AND con.contype = 'p';

    -- Jeśli istniejący PK to nie dokładnie (agent_name, tenant_id) — przebuduj.
    IF pk_name IS NOT NULL AND pk_cols NOT LIKE '%(agent_name, tenant_id)%' THEN
        EXECUTE format('ALTER TABLE agent_evolution DROP CONSTRAINT %I', pk_name);
        pk_name := NULL;
    END IF;

    IF pk_name IS NULL THEN
        ALTER TABLE agent_evolution
            ADD CONSTRAINT agent_evolution_pkey PRIMARY KEY (agent_name, tenant_id);
    END IF;
END $$;
