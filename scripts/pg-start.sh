#!/usr/bin/env bash
# Podnosi lokalnego Postgresa (Homebrew) po reboocie — z ominięciem brew services.
#
# Dlaczego nie `brew services`: na tej maszynie launchd wywala się przy bootstrapie
# (Bootstrap failed: 5: Input/output error). Startujemy bezpośrednio przez pg_ctl.
#
# Idempotentny i bezpieczny:
#   • jeśli serwer już działa → nic nie robi.
#   • jeśli został osierocony postmaster.pid (po crashu) a procesu nie ma → sprząta i startuje.
#   • nigdy nie usuwa pid gdy realny proces żyje.
#
# Użycie:  bash scripts/pg-start.sh        (albo dodaj alias — patrz na końcu)
set -euo pipefail

PG_FORMULA="postgresql@16"
PG_PREFIX="$(brew --prefix "$PG_FORMULA" 2>/dev/null || echo /usr/local/opt/$PG_FORMULA)"
PG_BIN="$PG_PREFIX/bin"
# Katalog danych: var w prefiksie Homebrew (Intel: /usr/local/var, ARM: /opt/homebrew/var).
BREW_VAR="$(brew --prefix 2>/dev/null)/var"
PGDATA="$BREW_VAR/$PG_FORMULA"
PGLOG="$BREW_VAR/log/$PG_FORMULA.log"
PORT="5432"

if [ ! -x "$PG_BIN/pg_ctl" ]; then
  echo "❌ Nie znaleziono pg_ctl w $PG_BIN — czy $PG_FORMULA jest zainstalowany? (brew install $PG_FORMULA)"
  exit 1
fi
if [ ! -d "$PGDATA" ]; then
  echo "❌ Brak katalogu danych $PGDATA. Zainicjalizuj: $PG_BIN/initdb -D $PGDATA"
  exit 1
fi

# 1. Już działa?
if "$PG_BIN/pg_isready" -q -p "$PORT" 2>/dev/null; then
  echo "✅ Postgres już działa (port $PORT)."
  exit 0
fi

# 2. Osierocony postmaster.pid? (plik jest, ale serwer nie odpowiada)
PIDFILE="$PGDATA/postmaster.pid"
if [ -f "$PIDFILE" ]; then
  pg_pid="$(head -1 "$PIDFILE" 2>/dev/null || echo "")"
  # Czy ten PID to faktycznie żywy proces postgres?
  if [ -n "$pg_pid" ] && ps -p "$pg_pid" -o comm= 2>/dev/null | grep -qi postgres; then
    echo "ℹ️  Proces postgres (PID $pg_pid) żyje, ale nie odpowiada na $PORT — czekam chwilę..."
    sleep 2
    "$PG_BIN/pg_isready" -q -p "$PORT" && { echo "✅ Już odpowiada."; exit 0; }
    echo "⚠️  Nadal nie odpowiada — sprawdź log: tail -20 $PGLOG"
    exit 1
  fi
  echo "🧹 Osierocony postmaster.pid (PID $pg_pid nie jest procesem postgres) — usuwam."
  rm -f "$PIDFILE"
fi

# 3. Start.
echo "── Startuję Postgres ($PGDATA)..."
"$PG_BIN/pg_ctl" -D "$PGDATA" -l "$PGLOG" start
sleep 1
if "$PG_BIN/pg_isready" -q -p "$PORT"; then
  echo "✅ Postgres wystartował i nasłuchuje na porcie $PORT."
else
  echo "⚠️  Start zgłoszony, ale brak odpowiedzi — sprawdź log: tail -20 $PGLOG"
  exit 1
fi

# Podpowiedź jednorazowa: alias dla wygody.
echo
echo "Tip: dodaj alias do ~/.zshrc, by podnosić bazę jedną komendą:"
echo "    echo 'alias pg-start=\"bash ~/Projects/architekt-wolnosci/scripts/pg-start.sh\"' >> ~/.zshrc"
echo "    source ~/.zshrc    # potem wystarczy:  pg-start"
