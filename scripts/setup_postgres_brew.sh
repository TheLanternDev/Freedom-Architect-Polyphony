#!/usr/bin/env bash
# Lokalny Postgres przez Homebrew (bez Dockera) — dla RLS w dev.
# Uruchom z roota repo:   bash scripts/setup_postgres_brew.sh
#
# Idempotentny: bezpieczny do wielokrotnego uruchomienia.
# Hasło/usera/bazę bierze z DATABASE_URL w .env — nic nie wpisujesz ręcznie.
set -euo pipefail
cd "$(dirname "$0")/.."

PG_VERSION="16"
FORMULA="postgresql@${PG_VERSION}"

# ── 0. Wymagania ──────────────────────────────────────────────────────────
if ! command -v brew >/dev/null 2>&1; then
  echo "❌ Homebrew nie znaleziony. Zainstaluj: https://brew.sh  — potem uruchom ten skrypt ponownie."
  exit 1
fi
if [ ! -f .env ]; then
  echo "❌ Brak .env w bieżącym katalogu. Uruchom z roota repo."
  exit 1
fi

# ── 1. Parsuj DATABASE_URL z .env ─────────────────────────────────────────
DB_URL="$(grep -E '^DATABASE_URL=' .env | head -1 | cut -d= -f2-)"
if [ -z "${DB_URL:-}" ]; then
  echo "❌ Brak DATABASE_URL w .env."
  exit 1
fi
# postgresql://USER:PASS@HOST:PORT/DBNAME
proto_stripped="${DB_URL#*://}"
creds="${proto_stripped%%@*}"
hostpart="${proto_stripped#*@}"
DB_USER="${creds%%:*}"
DB_PASS="${creds#*:}"
DB_NAME="${hostpart##*/}"
DB_PORT="$(echo "$hostpart" | sed -E 's#.*:([0-9]+)/.*#\1#')"
echo "Parametry z .env → user=$DB_USER  db=$DB_NAME  port=${DB_PORT:-5432}  host=localhost"

# ── 2. Instalacja Postgresa ───────────────────────────────────────────────
if brew list --versions "$FORMULA" >/dev/null 2>&1; then
  echo "✅ $FORMULA już zainstalowany."
else
  echo "── Instaluję $FORMULA (to potrwa chwilę)..."
  brew install "$FORMULA"
fi

# ścieżka do binarek tej wersji (nie zawsze w PATH)
PG_PREFIX="$(brew --prefix "$FORMULA")"
export PATH="$PG_PREFIX/bin:$PATH"

# ── 3. Start usługi ───────────────────────────────────────────────────────
echo "── Startuję usługę $FORMULA..."
brew services start "$FORMULA" >/dev/null
echo "Czekam aż serwer przyjmie połączenia..."
for i in $(seq 1 30); do
  if pg_isready -q -p "${DB_PORT:-5432}" 2>/dev/null; then echo "✅ Postgres nasłuchuje"; break; fi
  sleep 1
done

# ── 4. Rola + baza + hasło (idempotentnie) ────────────────────────────────
# Łączymy się do domyślnej bazy 'postgres' jako bieżący użytkownik systemowy
# (Homebrew tworzy superusera = nazwa konta macOS).
PSQL="psql -p ${DB_PORT:-5432} -d postgres -v ON_ERROR_STOP=1 -tA"

echo "── Tworzę/aktualizuję rolę '$DB_USER'..."
if [ "$($PSQL -c "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'")" = "1" ]; then
  $PSQL -c "ALTER ROLE \"$DB_USER\" WITH LOGIN PASSWORD '$DB_PASS';" >/dev/null
  echo "   rola istniała — zaktualizowano hasło."
else
  $PSQL -c "CREATE ROLE \"$DB_USER\" WITH LOGIN PASSWORD '$DB_PASS';" >/dev/null
  echo "   rola utworzona."
fi

echo "── Tworzę bazę '$DB_NAME' (owner=$DB_USER)..."
if [ "$($PSQL -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")" = "1" ]; then
  echo "   baza już istnieje — pomijam."
else
  $PSQL -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";" >/dev/null
  echo "   baza utworzona."
fi

# ── 5. Test połączenia tak, jak zrobi to aplikacja ────────────────────────
echo "── Test połączenia jako $DB_USER..."
if PGPASSWORD="$DB_PASS" psql -h localhost -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 'OK' AS conn;" -tA >/dev/null 2>&1; then
  echo "✅ Połączenie działa (localhost:${DB_PORT:-5432} jako $DB_USER)."
else
  echo "❌ Połączenie nie powiodło się — sprawdź hasło w .env i logi: brew services info $FORMULA"
  exit 1
fi

echo
echo "════════════════════════════════════════════════════════════════════"
echo "Gotowe. Teraz uruchom aplikację RAZ, by wykonała schemat + migracje (RLS):"
echo "    uvicorn main:app --reload --port 8000"
echo "W logu szukaj:  'PostgreSQL pool initialized'  (NIE ostrzeżenia o SQLite)."
echo
echo "Potem zweryfikuj izolację RLS:"
echo "    bash scripts/verify_rls_brew.sh"
echo "════════════════════════════════════════════════════════════════════"
