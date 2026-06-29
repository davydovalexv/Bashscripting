-- Эталонная разметка DV 2.0 (схема dv_meta)
SET search_path TO dv_meta, public;

CREATE TABLE dv_column_classification (
    id              SERIAL PRIMARY KEY,
    source_schema   VARCHAR(100) NOT NULL,
    source_table    VARCHAR(200) NOT NULL,
    source_column   VARCHAR(200) NOT NULL,
    dv_type         VARCHAR(20)  NOT NULL CHECK (dv_type IN ('hub', 'satellite', 'link')),
    dv_target_entity VARCHAR(200),
    dv_role         VARCHAR(50),
    notes           TEXT,
    UNIQUE (source_schema, source_table, source_column)
);

INSERT INTO dv_column_classification
    (source_schema, source_table, source_column, dv_type, dv_target_entity, dv_role, notes)
VALUES
    ('src', 'wells', 'well_id', 'hub', 'hub_well', 'business_key', 'BK скважины'),
    ('src', 'wells', 'well_name', 'satellite', 'sat_well', 'attribute', NULL),
    ('src', 'wells', 'field_name', 'satellite', 'sat_well', 'attribute', NULL),
    ('src', 'wells', 'well_type', 'satellite', 'sat_well', 'attribute', NULL),
    ('src', 'wells', 'status', 'satellite', 'sat_well', 'attribute', NULL),
    ('src', 'wells', 'spud_date', 'satellite', 'sat_well', 'attribute', NULL),
    ('src', 'wells', 'load_date', 'satellite', 'sat_well', 'operational_key', NULL),
    ('src', 'wells', 'record_source', 'satellite', 'sat_well', 'operational_key', NULL),

    ('src', 'production', 'production_id', 'hub', 'hub_production', 'business_key', NULL),
    ('src', 'production', 'well_id', 'link', 'link_well_production', 'link_key', 'FK → hub_well'),
    ('src', 'production', 'prod_date', 'satellite', 'sat_production', 'grain_key', NULL),
    ('src', 'production', 'oil_volume', 'satellite', 'sat_production', 'attribute', NULL),
    ('src', 'production', 'water_cut', 'satellite', 'sat_production', 'attribute', NULL),
    ('src', 'production', 'load_date', 'satellite', 'sat_production', 'operational_key', NULL),
    ('src', 'production', 'record_source', 'satellite', 'sat_production', 'operational_key', NULL),

    ('src', 'deliveries', 'delivery_id', 'hub', 'hub_delivery', 'business_key', NULL),
    ('src', 'deliveries', 'well_id', 'link', 'link_well_delivery', 'link_key', NULL),
    ('src', 'deliveries', 'station_id', 'link', 'link_station_delivery', 'link_key', NULL),
    ('src', 'deliveries', 'batch_id', 'link', 'link_batch_delivery', 'link_key', NULL),
    ('src', 'deliveries', 'delivery_date', 'satellite', 'sat_delivery', 'grain_key', NULL),
    ('src', 'deliveries', 'volume', 'satellite', 'sat_delivery', 'attribute', NULL),
    ('src', 'deliveries', 'load_date', 'satellite', 'sat_delivery', 'operational_key', NULL),
    ('src', 'deliveries', 'record_source', 'satellite', 'sat_delivery', 'operational_key', NULL),

    ('src', 'oil_stations', 'station_id', 'hub', 'hub_station', 'business_key', NULL),
    ('src', 'oil_stations', 'station_name', 'satellite', 'sat_station', 'attribute', NULL),
    ('src', 'oil_stations', 'location', 'satellite', 'sat_station', 'attribute', NULL),
    ('src', 'oil_stations', 'load_date', 'satellite', 'sat_station', 'operational_key', NULL),
    ('src', 'oil_stations', 'record_source', 'satellite', 'sat_station', 'operational_key', NULL),

    ('src', 'batches', 'batch_id', 'hub', 'hub_batch', 'business_key', NULL),
    ('src', 'batches', 'batch_date', 'satellite', 'sat_batch', 'attribute', NULL),
    ('src', 'batches', 'quality_grade', 'satellite', 'sat_batch', 'attribute', NULL),
    ('src', 'batches', 'load_date', 'satellite', 'sat_batch', 'operational_key', NULL),
    ('src', 'batches', 'record_source', 'satellite', 'sat_batch', 'operational_key', NULL);

CREATE OR REPLACE VIEW v_column_classification AS
SELECT
    source_schema,
    source_table,
    source_column,
    dv_type,
    dv_target_entity,
    dv_role,
    notes
FROM dv_column_classification
ORDER BY source_table, source_column;

CREATE OR REPLACE VIEW v_classification_summary AS
SELECT
    source_table,
    dv_type,
    COUNT(*) AS column_count
FROM dv_column_classification
GROUP BY source_table, dv_type
ORDER BY source_table, dv_type;
