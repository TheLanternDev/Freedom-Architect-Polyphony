-- Migration 0004 — onboarding_answers (Tydzień 4 mapy luk, #14 tech-debt).
--
-- Cel: zapisywać odpowiedzi z 20 pytań onboardingowych w bazie, nie tylko
-- w localStorage UI. Bez tego AKSJOMAT 1 (Architektura Marzenia) traci
-- najbogatszy kontekst — `distill_dream` mogłoby czytać te odpowiedzi
-- jako podstawowy materiał.
--
-- Idempotentna, RLS jak inne tabele tenantowane.

CREATE TABLE IF NOT EXISTS onboarding_answers (
    id            SERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    user_subject  TEXT,
    question_idx  INTEGER NOT NULL CHECK (question_idx >= 0),
    answer        TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT onboarding_answers_tenant_id_nonempty CHECK (tenant_id <> ''),
    UNIQUE (tenant_id, user_subject, question_idx)
);

CREATE INDEX IF NOT EXISTS idx_onboarding_answers_tenant_user
    ON onboarding_answers(tenant_id, user_subject);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = current_schema() AND table_name = 'onboarding_answers'
    ) THEN
        EXECUTE 'ALTER TABLE onboarding_answers ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE onboarding_answers FORCE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON onboarding_answers';
        EXECUTE $p$
            CREATE POLICY tenant_isolation ON onboarding_answers
                USING (
                    tenant_id = current_setting('architekt.tenant_id', true)
                    OR current_setting('architekt.tenant_id', true) = ''
                )
                WITH CHECK (
                    tenant_id = current_setting('architekt.tenant_id', true)
                    OR current_setting('architekt.tenant_id', true) = ''
                )
        $p$;
    END IF;
END $$;
