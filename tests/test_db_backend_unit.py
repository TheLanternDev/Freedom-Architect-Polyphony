"""Pure-function testy `db.backend`: detekcja PG vs SQLite + parsowanie SQL.

`_split_pg_schema` jest centralnym kawałkiem inicjalizacji bazy — bug tu wycieka
do każdej nowej instalacji PG.
"""

from __future__ import annotations

from db import backend as bk


def test_use_postgres_false_when_url_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert bk.use_postgres() is False
    assert bk.database_url() == ""


def test_use_postgres_true_for_postgresql_scheme(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert bk.use_postgres() is True


def test_use_postgres_true_for_postgres_scheme(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "POSTGRES://u@h/db")  # case-insensitive
    assert bk.use_postgres() is True


def test_use_postgres_false_for_sqlite_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data.db")
    assert bk.use_postgres() is False


def test_use_postgres_false_for_whitespace(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "   ")
    assert bk.use_postgres() is False


def test_split_pg_schema_basic_statements():
    sql = """
    -- header
    CREATE TABLE a (id INT);

    CREATE TABLE b (id INT);
    """
    stmts = bk._split_pg_schema(sql)
    assert len(stmts) == 2
    assert "CREATE TABLE a" in stmts[0]
    assert "CREATE TABLE b" in stmts[1]


def test_split_pg_schema_strips_pure_top_level_comment_lines():
    """Linia pełnokomentarzowa BEZPOŚREDNIO przed statement jest pomijana
    (algorytm: `if not cur and ls.startswith('--'): continue`)."""
    sql = "-- header\nCREATE TABLE x (id INT);"
    stmts = bk._split_pg_schema(sql)
    assert len(stmts) == 1
    assert stmts[0] == "CREATE TABLE x (id INT);"


def test_split_pg_schema_keeps_multiline_block():
    """Blok wieloliniowy zakończony średnikiem na ostatniej linii."""
    sql = """
    CREATE TABLE multi (
        id INT,
        name TEXT
    );
    """
    stmts = bk._split_pg_schema(sql)
    assert len(stmts) == 1
    assert "multi" in stmts[0] and "name TEXT" in stmts[0]


def test_split_pg_schema_handles_empty_input():
    assert bk._split_pg_schema("") == []
    assert bk._split_pg_schema("\n\n   \n") == []


def test_split_pg_schema_skips_statement_without_semicolon():
    """Statement bez średnika na końcu — NIE jest emitowane (broken SQL)."""
    sql = "CREATE TABLE x (id INT)"  # brak średnika
    stmts = bk._split_pg_schema(sql)
    assert stmts == []
