-- Migration 0005 — dream_debate_link: tenant_id + RLS (defense-in-depth).
--
-- Junction bez tenant_id pozwalał na cross-tenant linki przy błędzie repo.
-- Idempotentna; bezpieczna do wielokrotnego uruchomienia.

ALTER TABLE dream_debate_link ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';

-- Backfill z marzeń (preferowane).
UPDATE dream_debate_link l
   SET tenant_id = d.tenant_id
  FROM dreams d
 WHERE l.dream_id = d.id
   AND l.tenant_id = 'default';

-- Uzupełnij z debat, gdy brak dopasowania w dreams.
UPDATE dream_debate_link l
   SET tenant_id = b.tenant_id
  FROM debates b
 WHERE l.debate_id = b.id
   AND l.tenant_id = 'default';

DO $$
DECLARE
    pk_name TEXT;
    pk_cols TEXT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = current_schema() AND table_name = 'dream_debate_link'
    ) THEN
        RETURN;
    END IF;

    SELECT con.conname, pg_get_constraintdef(con.oid)
      INTO pk_name, pk_cols
      FROM pg_constraint con
      JOIN pg_class rel ON rel.oid = con.conrelid
     WHERE rel.relname = 'dream_debate_link'
       AND con.contype = 'p';

    IF pk_name IS NOT NULL AND pk_cols NOT LIKE '%tenant_id%' THEN
        EXECUTE format('ALTER TABLE dream_debate_link DROP CONSTRAINT %I', pk_name);
        ALTER TABLE dream_debate_link
            ADD CONSTRAINT dream_debate_link_pkey PRIMARY KEY (tenant_id, dream_id, debate_id);
    ELSIF pk_name IS NULL THEN
        ALTER TABLE dream_debate_link
            ADD CONSTRAINT dream_debate_link_pkey PRIMARY KEY (tenant_id, dream_id, debate_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
         WHERE table_schema = current_schema()
           AND table_name = 'dream_debate_link'
           AND constraint_name = 'dream_debate_link_tenant_id_nonempty'
    ) THEN
        ALTER TABLE dream_debate_link
            ADD CONSTRAINT dream_debate_link_tenant_id_nonempty CHECK (tenant_id <> '');
    END IF;

    EXECUTE 'ALTER TABLE dream_debate_link ENABLE ROW LEVEL SECURITY';
    EXECUTE 'ALTER TABLE dream_debate_link FORCE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON dream_debate_link';
    EXECUTE $p$
        CREATE POLICY tenant_isolation ON dream_debate_link
            USING (
                tenant_id = current_setting('architekt.tenant_id', true)
                OR current_setting('architekt.migration_bypass', true) = 'on'
            )
            WITH CHECK (
                tenant_id = current_setting('architekt.tenant_id', true)
                OR current_setting('architekt.migration_bypass', true) = 'on'
            )
    $p$;
END $$;
