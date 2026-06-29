"""Тесты парсера SQL."""

from pathlib import Path

import pytest

from dv_agent.parser.loader import parse_sql_path
from dv_agent.parser.options import ParseOptions
from dv_agent.parser.sql_parser import parse_create_tables

FIXTURES = Path(__file__).parent / "fixtures"
TEST_SQL_DIR = Path(__file__).resolve().parents[2] / "Files" / "Файлы к ML"


def test_parse_postgres_ddl_with_dml():
    sql = """
    CREATE TABLE orders (
        order_id INT PRIMARY KEY,
        customer_id INT NOT NULL REFERENCES customers(id)
    );
    INSERT INTO orders VALUES (1, 10);
  """
    tables = parse_create_tables(sql, dialect="postgres")
    assert len(tables) == 1
    assert tables[0].name == "orders"
    assert tables[0].columns[0].is_primary_key
    assert tables[0].columns[1].references == "customers"


def test_parse_schema_qualified_table():
    sql = "CREATE TABLE sales.customers (id INT PRIMARY KEY, name TEXT);"
    tables = parse_create_tables(sql, dialect="postgres", default_schema="public")
    assert tables[0].schema_name == "sales"
    assert tables[0].qualified_name == "sales.customers"


def test_parse_mysql_dialect():
    sql = """
    CREATE TABLE `users` (
        `id` INT PRIMARY KEY,
        `email` VARCHAR(255) NOT NULL
    );
    """
    tables = parse_create_tables(sql, dialect="mysql")
    assert tables[0].name == "users"
    assert any(c.name == "email" and not c.nullable for c in tables[0].columns)


def test_dml_only_file_warning():
    sql = "INSERT INTO foo VALUES (1); SELECT 1;"
    result = parse_sql_path_from_text(sql, "dml_only.sql")
    assert result.table_count == 0
    assert any("CREATE TABLE не найден" in i.message for i in result.issues)


def test_parse_test_data_directory():
    if not TEST_SQL_DIR.is_dir():
        pytest.skip("Тестовые SQL недоступны")
    result = parse_sql_path(TEST_SQL_DIR, ParseOptions(dialect="postgres", default_schema="public"))
    assert result.table_count == 11
    assert result.files_with_ddl >= 5
    assert result.files_scanned == 9


def test_single_file_path():
    ddl_file = FIXTURES / "sample.ddl"
    result = parse_sql_path(ddl_file, ParseOptions())
    assert result.table_count == 2
    names = {t.name for t in result.tables}
    assert names == {"customers", "orders"}


def test_recursive_subdirectory():
    root = FIXTURES / "nested"
    result = parse_sql_path(root, ParseOptions(recursive=True))
    assert result.table_count == 1
    assert result.tables[0].name == "products"


def parse_sql_path_from_text(sql: str, filename: str):
    import tempfile

    from dv_agent.parser.loader import parse_sql_path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / filename
        path.write_text(sql, encoding="utf-8")
        return parse_sql_path(path, ParseOptions())
