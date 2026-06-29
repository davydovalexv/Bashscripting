from __future__ import annotations

from pathlib import Path

from dv_agent.model.dv_schema import SourceTable
from dv_agent.parser.discovery import discover_sql_paths
from dv_agent.parser.options import ParseIssue, ParseOptions, ParseResult
from dv_agent.parser.sql_parser import parse_create_tables


def _read_sql_file(path: Path, encodings: tuple[str, ...]) -> tuple[str, str]:
    raw = path.read_bytes()
    if not raw.strip():
        return "", encodings[0]

    last_error: Exception | None = None
    for encoding in encodings:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeDecodeError(
        last_error.encoding if isinstance(last_error, UnicodeDecodeError) else encodings[0],
        last_error.object if isinstance(last_error, UnicodeDecodeError) else b"",
        last_error.start if isinstance(last_error, UnicodeDecodeError) else 0,
        last_error.end if isinstance(last_error, UnicodeDecodeError) else 1,
        f"Не удалось прочитать {path} ни в одной из кодировок: {encodings}",
    )


def parse_sql_path(path: Path, options: ParseOptions | None = None) -> ParseResult:
    """
    Разобрать SQL из файла, каталога или glob.
    DML-only файлы (INSERT/SELECT) пропускаются без ошибки.
    """
    opts = options or ParseOptions()
    result = ParseResult(tables=[])
    table_index: dict[str, SourceTable] = {}

    try:
        files = discover_sql_paths(path, opts)
    except (FileNotFoundError, ValueError) as exc:
        result.issues.append(ParseIssue(file=str(path), level="error", message=str(exc)))
        return result

    if not files:
        result.issues.append(
            ParseIssue(file=str(path), level="warning", message="SQL-файлы не найдены")
        )
        return result

    for file_path in files:
        result.files_scanned += 1
        rel = str(file_path)

        try:
            text, encoding = _read_sql_file(file_path, opts.encodings)
        except UnicodeDecodeError as exc:
            result.issues.append(ParseIssue(file=rel, level="error", message=str(exc)))
            continue

        if opts.skip_empty and not text.strip():
            result.issues.append(ParseIssue(file=rel, level="warning", message="Пустой файл"))
            continue

        try:
            tables = parse_create_tables(
                text,
                source_file=str(file_path),
                dialect=opts.dialect_name,
                default_schema=opts.default_schema,
            )
        except Exception as exc:  # noqa: BLE001 — фиксируем и продолжаем остальные файлы
            result.issues.append(
                ParseIssue(file=rel, level="error", message=f"Ошибка разбора: {exc}")
            )
            continue

        if tables:
            result.files_with_ddl += 1
        else:
            result.issues.append(
                ParseIssue(
                    file=rel,
                    level="warning",
                    message="CREATE TABLE не найден (возможно, только DML)",
                )
            )

        for table in tables:
            key = table.qualified_name
            if key in table_index and opts.merge_duplicates:
                prev = table_index[key]
                result.issues.append(
                    ParseIssue(
                        file=rel,
                        level="warning",
                        message=(
                            f"Таблица {key} переопределена "
                            f"(ранее в {prev.source_file})"
                        ),
                    )
                )
            table_index[key] = table

    result.tables = list(table_index.values())
    return result
