-- Migration 0007 — user_obraz (Obraz Użytkownika, destylat onboardingu).
--
-- Cel: trwały, wysokosygnałowy destylat 24 odpowiedzi onboardingowych, który
-- Rada widzi przez AKSJOMAT 1 (obok Architektury Marzenia). 1 bieżący wiersz
-- na użytkownika (UNIQUE tenant_id+user_subject), wersjonowany licznikiem.
--
-- Izolacja: tenant_id (RLS jak inne tabele) ORAZ filtr user_subject w repo
-- (dwóch userów jednego tenanta nie widzi nawzajem Obrazu). Idempotentna.

CREATE TABLE IF NOT EXISTS user_obraz (
    id            SERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    user_subject  TEXT,
    obraz_json    TEXT NOT NULL,
    wersja        INTEGER NOT NULL DEFAULT 1,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT user_obraz_tenant_id_nonempty CHECK (tenant_id <> ''),
    UNIQUE (tenant_id, user_subject)
);

CREATE INDEX IF NOT EXISTS idx_user_obraz_tenant_user
    ON user_obraz(tenant_id, user_subject);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = current_schema() AND table_name = 'user_obraz'
    ) THEN
        EXECUTE 'ALTER TABLE user_obraz ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE user_obraz FORCE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON user_obraz';
        EXECUTE $p$
            CREATE POLICY tenant_isolation ON user_obraz
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
