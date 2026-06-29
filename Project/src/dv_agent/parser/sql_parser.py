from __future__ import annotations

import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from dv_agent.model.dv_schema import SourceColumn, SourceTable
from dv_agent.parser.sql_preprocess import (
    parse_search_path,
    sanitize_sql,
    split_sql_statements,
)


def _qualified_table_name(table: exp.Table, default_schema: str) -> tuple[str, str, str]:
    catalog = table.catalog or ""
    schema = table.db or default_schema
    name = table.name
    return catalog, schema, name


def _column_type(column: exp.ColumnDef, dialect: str) -> str:
    kind = column.args.get("kind")
    if kind is None:
        return "UNKNOWN"
    return kind.sql(dialect=dialect)


def _constraint_kind(constraint) -> object | None:
    if isinstance(constraint, exp.ColumnConstraint):
        return constraint.args.get("kind")
    return constraint


def _is_not_null(col_def: exp.ColumnDef) -> bool:
    for constraint in col_def.args.get("constraints") or []:
        kind = _constraint_kind(constraint)
        if isinstance(kind, exp.NotNullColumnConstraint):
            return True
    return False


def _table_schema(create: exp.Create) -> tuple[exp.Table, list]:
    target = create.this
    if isinstance(target, exp.Schema):
        table = target.this
        if not isinstance(table, exp.Table):
            raise ValueError(f"Unexpected table node: {type(table)}")
        return table, target.expressions
    if isinstance(target, exp.Table):
        return target, create.expressions
    raise ValueError(f"Unexpected CREATE target: {type(target)}")


def _find_pk_columns(column_defs: list) -> set[str]:
    pks: set[str] = set()
    for item in column_defs:
        if isinstance(item, exp.PrimaryKey):
            for col in item.expressions:
                if isinstance(col, exp.Column):
                    pks.add(col.name)
        if isinstance(item, exp.ColumnDef):
            for constraint in item.args.get("constraints") or []:
                kind = _constraint_kind(constraint)
                if isinstance(kind, exp.PrimaryKeyColumnConstraint):
                    pks.add(item.name)
    return pks


def _ref_table_name(ref_table: exp.Expression) -> str:
    if isinstance(ref_table, exp.Table):
        parts = [p for p in (ref_table.catalog, ref_table.db, ref_table.name) if p]
        return ".".join(parts) if parts else ref_table.name
    if isinstance(ref_table, exp.Schema):
        inner = ref_table.this
        if isinstance(inner, exp.Table):
            return _ref_table_name(inner)
    return str(ref_table).split("(")[0].strip()


def _find_fk_map(column_defs: list) -> dict[str, str]:
    fks: dict[str, str] = {}
    for item in column_defs:
        if isinstance(item, exp.ForeignKey):
            ref = item.args.get("reference")
            if not ref or not ref.this:
                continue
            ref_name = _ref_table_name(ref.this)
            for col in item.expressions:
                if isinstance(col, exp.Column):
                    fks[col.name] = ref_name
        if isinstance(item, exp.ColumnDef):
            for constraint in item.args.get("constraints") or []:
                kind = _constraint_kind(constraint)
                if isinstance(constraint, exp.Reference) or isinstance(kind, exp.Reference):
                    ref = constraint if isinstance(constraint, exp.Reference) else kind
                    ref_name = _ref_table_name(ref.this) if ref and ref.this else "?"
                    fks[item.name] = ref_name
    return fks


_CREATE_TABLE_RE = re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE)


def _is_create_table(stmt: str) -> bool:
    return bool(_CREATE_TABLE_RE.search(stmt))


def _parse_create_table_statement(
    statement: exp.Expression,
    *,
    dialect: str,
    default_schema: str,
    source_file: str | None,
) -> SourceTable | None:
    if not isinstance(statement, exp.Create) or statement.kind != "TABLE":
        return None

    table_expr, column_defs = _table_schema(statement)
    catalog, schema_name, table_name = _qualified_table_name(table_expr, default_schema)
    pk_cols = _find_pk_columns(column_defs)
    fk_map = _find_fk_map(column_defs)
    columns: list[SourceColumn] = []

    for col_def in column_defs:
        if not isinstance(col_def, exp.ColumnDef):
            continue
        columns.append(
            SourceColumn(
                name=col_def.name,
                data_type=_column_type(col_def, dialect),
                nullable=not _is_not_null(col_def),
                is_primary_key=col_def.name in pk_cols,
                references=fk_map.get(col_def.name),
            )
        )

    return SourceTable(
        name=table_name,
        schema_name=schema_name,
        catalog_name=catalog or None,
        columns=columns,
        source_file=source_file,
        dialect=dialect,
    )


def parse_create_tables(
    sql_text: str,
    source_file: str | None = None,
    dialect: str = "postgres",
    default_schema: str = "public",
) -> list[SourceTable]:
    """
    Извлечь CREATE TABLE из SQL-текста.
    Поддерживает pg_dump: SET, функции, \\connect, CREATE VIEW — пропускаются.
    """
    cleaned = sanitize_sql(sql_text)
    statements = split_sql_statements(cleaned)
    tables: list[SourceTable] = []
    active_schema = default_schema

    for stmt in statements:
        path_schema = parse_search_path(stmt)
        if path_schema:
            active_schema = path_schema
            continue

        if not _is_create_table(stmt):
            continue

        try:
            parsed = sqlglot.parse_one(stmt, dialect=dialect)
        except ParseError:
            try:
                parsed = sqlglot.parse_one(stmt, read=dialect)
            except ParseError:
                continue

        table = _parse_create_table_statement(
            parsed,
            dialect=dialect,
            default_schema=active_schema,
            source_file=source_file,
        )
        if table and table.columns:
            tables.append(table)

    return tables
