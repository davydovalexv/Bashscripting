"""Тесты препроцессора pg_dump SQL."""

from pathlib import Path

from dv_agent.parser.loader import parse_sql_path
from dv_agent.parser.options import ParseOptions
from dv_agent.parser.sql_parser import parse_create_tables
from dv_agent.parser.sql_preprocess import sanitize_sql, split_sql_statements

DEMO_SQL = Path("/home/weiss/Study/SQL/Small_copy/demo-small.sql")


PG_DUMP_HEADER = """
SET client_encoding = 'UTF8';
DROP DATABASE if exists demo;
CREATE DATABASE demo;
\\connect demo
SET search_path = bookings, pg_catalog;
"""


def test_sanitize_removes_psql_connect():
    cleaned = sanitize_sql(PG_DUMP_HEADER)
    assert "\\connect" not in cleaned
    assert "DROP DATABASE" not in cleaned
    assert "CREATE DATABASE" not in cleaned
    assert "SET client_encoding" in cleaned


def test_split_respects_dollar_quotes():
    sql = "CREATE FUNCTION f() RETURNS void AS $$ BEGIN NULL; END; $$ LANGUAGE plpgsql; SELECT 1;"
    parts = split_sql_statements(sql)
    assert len(parts) == 2
    assert parts[0].startswith("CREATE FUNCTION")
    assert parts[1] == "SELECT 1"


def test_parse_pg_dump_demo_small():
    if not DEMO_SQL.is_file():
        return
    text = DEMO_SQL.read_text(encoding="utf-8")
    tables = parse_create_tables(text, dialect="postgres", default_schema="public")
    names = {t.name for t in tables}
    assert len(tables) == 8
    assert "aircrafts_data" in names
    assert "tickets" in names
    assert all(t.schema_name == "bookings" for t in tables)


def test_parse_sql_path_demo_directory():
    if not DEMO_SQL.parent.is_dir():
        return
    result = parse_sql_path(DEMO_SQL.parent, ParseOptions(dialect="postgres"))
    assert result.table_count == 8
    assert not result.has_errors
