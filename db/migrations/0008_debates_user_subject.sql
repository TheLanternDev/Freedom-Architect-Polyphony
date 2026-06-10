-- Migration 0008 — debates.user_subject (Faza A: izolacja historii per user).
--
-- Historia debat była tylko tenant-scoped. W trybach współdzielonego tenanta
-- (legacy API key / BFF z wieloma userami) groziło to cross-user leak. Dodajemy
-- `user_subject` i filtrujemy odczyty w repo (jak onboarding/user_obraz).
--
-- Wstecznie zgodne: stare wiersze pozostają `user_subject = NULL` i są widoczne
-- dla całego tenanta (filtr w repo: `user_subject = :uid OR user_subject IS NULL`).
-- Nowe debaty stemplowane `current_user_id()`. RLS pozostaje tenantowy — izolacja
-- per-user jest egzekwowana w warstwie repo, nie przez politykę RLS.

ALTER TABLE debates ADD COLUMN IF NOT EXISTS user_subject TEXT;

CREATE INDEX IF NOT EXISTS idx_debates_tenant_user
    ON debates(tenant_id, user_subject);
