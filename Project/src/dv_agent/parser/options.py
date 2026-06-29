from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SqlDialect(str, Enum):
    """Поддерживаемые диалекты sqlglot (расширяемый список)."""

    POSTGRES = "postgres"
    MYSQL = "mysql"
    TSQL = "tsql"
    ORACLE = "oracle"
    SQLITE = "sqlite"
    BIGQUERY = "bigquery"
    SNOWFLAKE = "snowflake"
    REDSHIFT = "redshift"
    SPARK = "spark"
    DUCKDB = "duckdb"


@dataclass
class ParseOptions:
    """Параметры разбора произвольных SQL-файлов."""

    dialect: SqlDialect | str = SqlDialect.POSTGRES
    default_schema: str = "public"
    recursive: bool = True
    patterns: tuple[str, ...] = ("*.sql", "*.ddl")
    encodings: tuple[str, ...] = ("utf-8", "utf-8-sig", "cp1251", "latin-1")
    skip_empty: bool = True
    merge_duplicates: bool = True

    @property
    def dialect_name(self) -> str:
        if isinstance(self.dialect, SqlDialect):
            return self.dialect.value
        return str(self.dialect)


@dataclass
class ParseIssue:
    file: str
    level: str  # warning | error
    message: str


@dataclass
class ParseResult:
    tables: list  # list[SourceTable] — без циклического импорта в аннотации
    files_scanned: int = 0
    files_with_ddl: int = 0
    issues: list[ParseIssue] = field(default_factory=list)

    @property
    def table_count(self) -> int:
        return len(self.tables)

    @property
    def has_errors(self) -> bool:
        return any(i.level == "error" for i in self.issues)
