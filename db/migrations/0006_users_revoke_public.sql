-- Migration 0006 — P1-A2: least privilege na tabeli `users` (poza RLS).
--
-- Login/register wymagają SELECT/INSERT/UPDATE bez ustawionego GUC — stąd brak RLS
-- na `users`. Ograniczamy PUBLIC; rola aplikacji powinna mieć wyłącznie:
--   GRANT SELECT, INSERT, UPDATE ON users TO app_role;
-- (bez DELETE masowego, bez TRUNCATE).
--
-- Idempotentne; bezpieczne przy wielokrotnym uruchomieniu.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = current_schema() AND table_name = 'users'
    ) THEN
        REVOKE ALL ON TABLE users FROM PUBLIC;
    END IF;
END $$;
