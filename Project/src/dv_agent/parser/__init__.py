from dv_agent.parser.discovery import discover_sql_paths
from dv_agent.parser.loader import parse_sql_path
from dv_agent.parser.options import ParseOptions, ParseResult, SqlDialect
from dv_agent.parser.sql_parser import parse_create_tables

__all__ = [
    "ParseOptions",
    "ParseResult",
    "SqlDialect",
    "discover_sql_paths",
    "parse_create_tables",
    "parse_sql_path",
]

# Обратная совместимость
def parse_sql_files(directory, options: ParseOptions | None = None):
    from pathlib import Path

    return parse_sql_path(Path(directory), options).tables
