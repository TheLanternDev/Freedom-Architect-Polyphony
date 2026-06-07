#!/usr/bin/env bash
# Weryfikacja RLS na natywnym Postgresie (Homebrew, bez Dockera).
# Wymaga: uruchomionej usługi postgres + raz odpalonej aplikacji (migracje).
# Uruchom z roota repo:   bash scripts/verify_rls_brew.sh
set -euo pipefail
cd "$(dirname "$0")/.."

DB_URL="$(grep -E '^DATABASE_URL=' .env | head -1 | cut -d= -f2-)"
proto_stripped="${DB_URL#*://}"; creds="${proto_stripped%%@*}"; hostpart="${proto_stripped#*@}"
DB_USER="${creds%%:*}"; DB_PASS="${creds#*:}"; DB_NAME="${hostpart##*/}"
DB_PORT="$(echo "$hostpart" | sed -E 's#.*:([0-9]+)/.*#\1#')"; DB_PORT="${DB_PORT:-5432}"

# dorzuć binarki postgresql@16 do PATH jeśli trzeba
if ! command -v psql >/dev/null 2>&1; then
  PG_PREFIX="$(brew --prefix postgresql@16 2>/dev/null || true)"
  [ -n "$PG_PREFIX" ] && export PATH="$PG_PREFIX/bin:$PATH"
fi

PSQL="env PGPASSWORD=$DB_PASS psql -h localhost -p $DB_PORT -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1"

echo "── 1/3: czy migracje (RLS) są zastosowane? ───────────────────────────"
$PSQL -c "SELECT version FROM schema_migrations ORDER BY version;" || {
  echo "⚠️  Brak schema_migrations — odpal aplikację raz: uvicorn main:app --port 8000"
  exit 1
}

echo
echo "── 2/3: policy tenant_isolation na chronionych tabelach ──────────────"
$PSQL -c "SELECT tablename, policyname FROM pg_policies WHERE policyname='tenant_isolation' ORDER BY tablename;"
echo "RLS forced na 'debates' (oczekiwane: t | t):"
$PSQL -tA -c "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='debates';"

echo
echo "── 3/3: żywy test izolacji — tenant A nie widzi wierszy tenanta B ─────"
$PSQL <<'SQL'
BEGIN;
-- wstaw wiersz jako tenant A
SELECT set_config('architekt.tenant_id', 'verifyA', true);
INSERT INTO debates (tenant_id, category, mode, brief_description)
  VALUES ('verifyA','decyzja','codzienny','RLSVERIFY::A');
-- wstaw wiersz jako tenant B
SELECT set_config('architekt.tenant_id', 'verifyB', true);
INSERT INTO debates (tenant_id, category, mode, brief_description)
  VALUES ('verifyB','decyzja','codzienny','RLSVERIFY::B');
-- jako tenant A: RAW SELECT bez WHERE — RLS musi pokazać TYLKO verifyA
SELECT set_config('architekt.tenant_id', 'verifyA', true);
\echo '>>> Widoczne tenanty dla verifyA (oczekiwane: tylko verifyA):'
SELECT DISTINCT tenant_id FROM debates WHERE brief_description LIKE 'RLSVERIFY::%';
ROLLBACK;
SQL

echo
echo "Jeśli wyżej widać TYLKO 'verifyA' — RLS izoluje tenantów na poziomie bazy. ✅"
echo "(Wiersze testowe wycofane przez ROLLBACK — nic nie zostaje w bazie.)"
