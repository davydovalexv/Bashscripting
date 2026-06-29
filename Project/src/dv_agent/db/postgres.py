from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from dv_agent.config import AppConfig, load_config
from dv_agent.model.dv_schema import ColumnClassification, DvEntitySummary


def _connect(config: AppConfig | None = None) -> psycopg.Connection:
    cfg = config or load_config()
    return psycopg.connect(cfg.database.dsn, row_factory=dict_row)


def fetch_column_map(
    table_name: str | None = None,
    config: AppConfig | None = None,
) -> list[ColumnClassification]:
    cfg = config or load_config()
    meta = cfg.database.meta_schema
    query = f"""
        SELECT
            table_schema,
            table_name,
            column_name,
            ordinal_position,
            data_type,
            is_nullable,
            dv_type,
            dv_target_entity,
            dv_role,
            is_business_key,
            description
        FROM {meta}.v_source_columns
    """
    params: list[str] = []
    if table_name:
        query += " WHERE table_name = %s"
        params.append(table_name)
    query += " ORDER BY table_name, ordinal_position"

    with _connect(cfg) as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return [ColumnClassification.model_validate(row) for row in cur.fetchall()]


def fetch_entity_summary(config: AppConfig | None = None) -> list[DvEntitySummary]:
    cfg = config or load_config()
    meta = cfg.database.meta_schema
    query = f"""
        SELECT dv_target_entity, dv_type, column_count, source_columns
        FROM {meta}.v_dv_entities_summary
        ORDER BY dv_type, dv_target_entity
    """
    with _connect(cfg) as conn, conn.cursor() as cur:
        cur.execute(query)
        return [DvEntitySummary.model_validate(row) for row in cur.fetchall()]


def ping(config: AppConfig | None = None) -> bool:
    try:
        with _connect(config or load_config()) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() is not None
    except psycopg.Error:
        return False
