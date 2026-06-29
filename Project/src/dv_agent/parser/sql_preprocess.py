from __future__ import annotations

import re


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_PSQL_META_RE = re.compile(r"^\\[a-zA-Z].*")
_SEARCH_PATH_RE = re.compile(
    r"SET\s+search_path\s*=\s*([^;]+)",
    re.IGNORECASE,
)


def strip_ansi_codes(text: str) -> str:
    return _ANSI_RE.sub("", text)


def remove_psql_meta_commands(text: str) -> str:
    """Убрать команды psql: \\connect, \\copy, \\restrict и т.д."""
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if _PSQL_META_RE.match(stripped):
            continue
        lines.append(line)
    return "\n".join(lines)


def remove_database_admin_statements(text: str) -> str:
    """Убрать DROP/CREATE DATABASE — не нужны для разбора таблиц."""
    lines: list[str] = []
    for line in text.splitlines():
        upper = line.strip().upper()
        if upper.startswith("DROP DATABASE") or upper.startswith("CREATE DATABASE"):
            continue
        if upper.startswith("ALTER DATABASE"):
            continue
        lines.append(line)
    return "\n".join(lines)


def sanitize_sql(text: str) -> str:
    """Подготовить SQL-дамп (pg_dump + psql) к разбору sqlglot."""
    text = strip_ansi_codes(text)
    text = remove_psql_meta_commands(text)
    text = remove_database_admin_statements(text)
    return text


def parse_search_path(statement: str) -> str | None:
    match = _SEARCH_PATH_RE.search(statement)
    if not match:
        return None
    first = match.group(1).split(",")[0].strip().strip('"').strip("'")
    return first or None


def split_sql_statements(sql: str) -> list[str]:
    """
    Разбить SQL на отдельные выражения по ';'.
    Учитывает dollar-quoting ($$ ... $$) в функциях pg_dump.
    """
    statements: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    dollar_tag: str | None = None
    i = 0
    length = len(sql)

    while i < length:
        ch = sql[i]

        if dollar_tag is None and not in_single and not in_double:
            if ch == "$":
                m = re.match(r"\$([A-Za-z0-9_]*)\$", sql[i:])
                if m:
                    tag = m.group(0)
                    if dollar_tag is None:
                        dollar_tag = tag
                        buf.append(tag)
                        i += len(tag)
                        continue
            if ch == "'" and not in_double:
                in_single = True
                buf.append(ch)
                i += 1
                continue
            if ch == '"' and not in_single:
                in_double = True
                buf.append(ch)
                i += 1
                continue
            if ch == ";" and dollar_tag is None:
                stmt = "".join(buf).strip()
                if stmt:
                    statements.append(stmt)
                buf = []
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'" and i + 1 < length and sql[i + 1] == "'":
                buf.append(sql[i + 1])
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            buf.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        if dollar_tag:
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(ch)
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements
