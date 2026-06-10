-- Migration 0002 — Row Level Security (PostgreSQL only).
--
-- Cel: defense-in-depth dla multi-tenancy. Do tej pory izolacja zależała
-- WYŁĄCZNIE od poprawności warstwy repo (`db/connection.py` stempluje każdy
-- INSERT/SELECT tenant_id z ContextVar). Jeden bug, jeden raw SQL bez WHERE
-- tenant_id i wycieka cross-tenant. RLS przesuwa tę gwarancję do bazy.
--
-- Sposób działania:
--   • aplikacja przed każdym query ustawia GUC `architekt.tenant_id`
--     (`db.pg_wrap.PgConnection.execute` woła `set_config(...)`).
--   • policy USING/CHECK porównuje wiersz z tym GUC.
--   • bypass dla DDL/seed/migracji jest JAWNY: tylko gdy GUC
--     `architekt.migration_bypass` == 'on' (ustawia go runner migracji,
--     `db.backend.init_database`). Pusty/nieustawiony `architekt.tenant_id`
--     NIE otwiera już policy — fail-closed (poprzednio `... = ''` dawało
--     cross-tenant read na każdym połączeniu omijającym pg_wrap). CHECK
--     `tenant_id <> ''` gwarantuje, że pusty GUC nie dopasuje żadnego wiersza.
--   • `FORCE ROW LEVEL SECURITY` enforce'uje policy NAWET dla ownera tabeli
--     (czyli roli aplikacji), inaczej RLS jest dla niego no-op.
--
-- Idempotentna: DROP POLICY IF EXISTS przed CREATE; ENABLE/FORCE jest no-op
-- jeśli już włączone. Bezpieczna do uruchomienia wielokrotnie.
--
-- ŚWIADOME ograniczenie: tabela `users` POZA RLS. Login musi działać bez
-- ustawionego GUC (user jest jeszcze nieznany). Zabezpieczenie tej tabeli to
-- silne hashowanie haseł (argon2) + brak innych danych poza username/tenant
-- w wierszu. Patrz `db/tenant.py` dla decyzji "tenant_id == user_id".

-- Helper: jeden DO-block per tabela żeby zachować spójność stylu i dać
-- czytelne komunikaty błędów przy ręcznym debugu.

DO $$
DECLARE
    t TEXT;
    tables TEXT[] := ARRAY[
        'dreams', 'debates', 'agent_voices', 'projects',
        'functionality_items', 'completion_audits', 'commitments',
        'agent_evolution'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        -- Niektóre instalacje mogą jeszcze nie mieć tabeli (świeży deploy
        -- po sequence init_db → migration). Skip cicho.
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

-- Sanity: każda tabela z tenant_id MUSI mieć tenant_id <> '' żeby pusta wartość
-- GUC (init/migrations) nie była omyłkowo interpretowana jako "wiersz dla
-- usera bez tenant_id". Default 'default' z migracji 0001 to gwarantuje, ale
-- dorzucamy CHECK bo wartość jest fundamentalna dla izolacji.
DO $$
DECLARE
    t TEXT;
    tables TEXT[] := ARRAY[
        'dreams', 'debates', 'agent_voices', 'projects',
        'functionality_items', 'completion_audits', 'commitments',
        'agent_evolution'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
             WHERE table_schema = current_schema() AND table_name = t
        ) THEN
            CONTINUE;
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
             WHERE table_schema = current_schema()
               AND table_name = t
               AND constraint_name = t || '_tenant_id_nonempty'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I ADD CONSTRAINT %I CHECK (tenant_id <> '''')',
                t, t || '_tenant_id_nonempty'
            );
        END IF;
    END LOOP;
END $$;
