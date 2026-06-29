-- Представления для CLI (export-meta, summary, inspect-db)
SET search_path TO dv_meta, public;

CREATE OR REPLACE VIEW v_source_columns AS
SELECT
    c.table_schema,
    c.table_name,
    c.column_name,
    c.ordinal_position,
    c.data_type,
    c.is_nullable,
    cl.dv_type::varchar AS dv_type,
    cl.dv_target_entity,
    cl.dv_role,
    (cl.dv_role = 'business_key') AS is_business_key,
    cl.notes AS description
FROM information_schema.columns c
JOIN dv_column_classification cl
    ON cl.source_schema = c.table_schema
   AND cl.source_table = c.table_name
   AND cl.source_column = c.column_name
WHERE c.table_schema = 'src';

CREATE OR REPLACE VIEW v_dv_entities_summary AS
SELECT
    dv_target_entity,
    dv_type::varchar AS dv_type,
    COUNT(*)::int AS column_count,
    string_agg(
        source_table || '.' || source_column,
        ', ' ORDER BY source_table, source_column
    ) AS source_columns
FROM dv_column_classification
GROUP BY dv_target_entity, dv_type;
