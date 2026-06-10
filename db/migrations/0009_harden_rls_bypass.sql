-- Migration 0009 — hardening RLS: usunięcie escape `current_setting('architekt.tenant_id','')=''`.
--
-- Problem (code review 2026-06-09, HIGH): polityki z 0002–0007 zawierały
-- klauzulę `OR current_setting('architekt.tenant_id', true) = ''`. Pusty GUC
-- (każde połączenie omijające `db.pg_wrap.PgConnection` — raw acquire, błędny
-- kod, przyszła ścieżka) interpretował jako "przepuść wszystko" → cross-tenant
-- read. Izolacja zależała więc od konwencji "ustaw GUC przed query", nie od bazy.
--
-- Fix: bypass dla DDL/seed/migracji jest teraz JAWNY i osobny — tylko gdy
-- `architekt.migration_bypass = 'on'` (ustawiany wyłącznie przez runner migracji
-- `db.backend.init_database`). Runtime (`pg_wrap`) nigdy go nie ustawia, a pusty
-- `architekt.tenant_id` nie dopasuje żadnego wiersza (CHECK `tenant_id <> ''`).
-- → fail-closed.
--
-- Ta migracja re-aplikuje policy `tenant_isolation` z nowym predykatem na
-- WSZYSTKICH istniejących tabelach tenantowanych (świeże deploye dostają nowy
-- predykat już ze źródeł 0002–0007). Idempotentna.

DO $$
DECLARE
    t TEXT;
    tables TEXT[] := ARRAY[
        'dreams', 'debates', 'agent_voices', 'projects',
        'functionality_items', 'completion_audits', 'commitments',
        'agent_evolution', 'feedback', 'onboarding_answers',
        'dream_debate_link', 'user_obraz'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
             WHERE table_schema = current_schema() AND table_name = t
        ) THEN
            CONTINUE;
        END IF;

        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
        EXECUTE format($p$
            CREATE POLICY tenant_isolation ON %I
                USING (
                    tenant_id = current_setting('architekt.tenant_id', true)
                    OR current_setting('architekt.migration_bypass', true) = 'on'
                )
                WITH CHECK (
                    tenant_id = current_setting('architekt.tenant_id', true)
                    OR current_setting('architekt.migration_bypass', true) = 'on'
                )
        $p$, t);
    END LOOP;
END $$;
