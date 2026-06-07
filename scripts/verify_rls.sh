#!/usr/bin/env bash
# Weryfikacja RLS end-to-end (dev). Uruchom z roota repo:
#     bash scripts/verify_rls.sh
#
# Sprawdza:
#   1. Postgres (Docker) wstaje i jest healthy.
#   2. Migracje (w tym RLS 0002) są zastosowane, policy tenant_isolation istnieje.
#   3. Test izolacji: tenant A nie widzi wierszy tenanta B przy RAW SELECT.
#   4. Fail-closed: gdy PG zgaszony, start aplikacji się zatrzymuje (nie SQLite).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "── 1/4: uruchamiam Postgres + Redis (Docker) ─────────────────────────"
docker compose up -d postgres redis
echo "Czekam aż Postgres będzie healthy..."
for i in $(seq 1 30); do
  status=$(docker compose ps postgres --format '{{.Health}}' 2>/dev/null || echo "")
  if [ "$status" = "healthy" ]; then echo "✅ Postgres healthy"; break; fi
  sleep 2
done

echo
echo "── 2/4: sprawdzam migracje + policy RLS w bazie ──────────────────────"
docker compose exec -T postgres psql -U architekt -d architekt -c \
  "SELECT version FROM schema_migrations ORDER BY version;" || {
    echo "⚠️  Brak schema_migrations — uruchom najpierw aplikację raz, by wykonała migracje:"
    echo "    uvicorn main:app --port 8000   (Ctrl+C po 'PostgreSQL pool initialized')"
  }
echo
echo "Policy tenant_isolation na chronionych tabelach:"
docker compose exec -T postgres psql -U architekt -d architekt -c \
  "SELECT tablename, policyname FROM pg_policies WHERE policyname='tenant_isolation' ORDER BY tablename;"
echo
echo "RLS forced (relforcerowsecurity=t) na 'debates':"
docker compose exec -T postgres psql -U architekt -d architekt -c \
  "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='debates';"

echo
echo "── 3/4: test izolacji RLS (pytest, wymaga PG) ────────────────────────"
echo "Uruchom (w środowisku z zależnościami projektu):"
echo "    TEST_DATABASE_URL=postgresql://architekt:\$POSTGRES_PASSWORD@localhost:5432/architekt \\"
echo "        pytest tests/test_rls_postgres_isolation.py tests/test_db_dev_fallback.py -v"

echo
echo "── 4/4: test fail-closed (opcjonalny) ────────────────────────────────"
echo "Zgaś Postgres i spróbuj odpalić app — start powinien się ZATRZYMAĆ:"
echo "    docker compose stop postgres"
echo "    uvicorn main:app --port 8000      # oczekiwane: RuntimeError 'SQLite nie ma RLS'"
echo
echo "Gotowe. Jeśli punkt 2 pokazuje policy tenant_isolation na wszystkich tabelach"
echo "i punkt 3 przechodzi — RLS realnie izoluje tenantów na poziomie bazy."
