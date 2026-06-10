-- Migration 0003 — tabela feedback (Tydzień 4 mapy luk: soft launch).
--
-- Cel: zbierać ustrukturyzowany feedback od 3–5 zaproszonych userów soft
-- launchu. Każdy wpis izolowany per tenant (RLS z migracji 0002).
--
-- Pola:
--   id              — serial PK
--   tenant_id       — z ContextVar `architekt.tenant_id` (RLS)
--   user_subject    — JWT `sub` (do korelacji z `users.username`)
--   rating          — 1–5 (CHECK constraint)
--   what_worked     — co realnie pomogło
--   what_broke      — co było mylące / nie działało
--   debate_id       — opcjonalny link do konkretnej debaty (bez FK,
--                     bo debate może być z innego trybu / starszej wersji)
--   created_at      — timestamp UTC
--
-- Idempotentna (CREATE TABLE IF NOT EXISTS) i włączona do RLS policy
-- `tenant_isolation` jak inne tabele tenantowane.

CREATE TABLE IF NOT EXISTS feedback (
    id            SERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    user_subject  TEXT,
    rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    what_worked   TEXT NOT NULL DEFAULT '',
    what_broke    TEXT NOT NULL DEFAULT '',
    debate_id     INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT feedback_tenant_id_nonempty CHECK (tenant_id <> '')
);

CREATE INDEX IF NOT EXISTS idx_feedback_tenant_id ON feedback(tenant_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at);

-- RLS — taka sama policy jak w migracji 0002.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = current_schema() AND table_name = 'feedback'
    ) THEN
        EXECUTE 'ALTER TABLE feedback ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE feedback FORCE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON feedback';
        EXECUTE $p$
            CREATE POLICY tenant_isolation ON feedback
                USING (
                    tenant_id = current_setting('architekt.tenant_id', true)
                    OR current_setting('architekt.migration_bypass', true) = 'on'
                )
                WITH CHECK (
                    tenant_id = current_setting('architekt.tenant_id', true)
                    OR current_setting('architekt.migration_bypass', true) = 'on'
                )
        $p$;
    END IF;
END $$;
