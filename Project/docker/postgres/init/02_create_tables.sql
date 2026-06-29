-- Тестовые таблицы нефтедобычи (схема src)
SET search_path TO src, public;

CREATE TABLE wells (
    well_id       VARCHAR(50) PRIMARY KEY,
    well_name     VARCHAR(200),
    field_name    VARCHAR(200),
    well_type     VARCHAR(50),
    status        VARCHAR(50),
    spud_date     DATE,
    load_date     TIMESTAMP,
    record_source VARCHAR(50)
);

CREATE TABLE production (
    production_id VARCHAR(50) PRIMARY KEY,
    well_id       VARCHAR(50) REFERENCES wells(well_id),
    prod_date     DATE,
    oil_volume    DECIMAL(12, 2),
    water_cut     DECIMAL(5, 2),
    load_date     TIMESTAMP,
    record_source VARCHAR(50)
);

CREATE TABLE deliveries (
    delivery_id   VARCHAR(50) PRIMARY KEY,
    well_id       VARCHAR(50) REFERENCES wells(well_id),
    station_id    VARCHAR(50),
    batch_id      VARCHAR(50),
    delivery_date DATE,
    volume        DECIMAL(12, 2),
    load_date     TIMESTAMP,
    record_source VARCHAR(50)
);

CREATE TABLE oil_stations (
    station_id    VARCHAR(50) PRIMARY KEY,
    station_name  VARCHAR(200),
    location      VARCHAR(200),
    load_date     TIMESTAMP,
    record_source VARCHAR(50)
);

CREATE TABLE batches (
    batch_id      VARCHAR(50) PRIMARY KEY,
    batch_date    DATE,
    quality_grade VARCHAR(50),
    load_date     TIMESTAMP,
    record_source VARCHAR(50)
);

INSERT INTO wells VALUES
    ('W001', 'Скважина-1', 'Северное', 'production', 'active', '2020-01-15', NOW(), 'ERP'),
    ('W002', 'Скважина-2', 'Северное', 'injection', 'active', '2021-03-20', NOW(), 'ERP');

INSERT INTO production VALUES
    ('P001', 'W001', '2026-01-01', 120.50, 15.00, NOW(), 'SCADA'),
    ('P002', 'W001', '2026-01-02', 118.30, 15.50, NOW(), 'SCADA');

INSERT INTO oil_stations VALUES
    ('ST01', 'ЦПС-1', 'Северный район', NOW(), 'ERP');

INSERT INTO batches VALUES
    ('B001', '2026-01-01', 'A', NOW(), 'LIMS');

INSERT INTO deliveries VALUES
    ('D001', 'W001', 'ST01', 'B001', '2026-01-03', 500.00, NOW(), 'LOGISTICS');
