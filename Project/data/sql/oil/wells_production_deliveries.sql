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
    well_id       VARCHAR(50),
    prod_date     DATE,
    oil_volume    DECIMAL(12, 2),
    water_cut     DECIMAL(5, 2),
    load_date     TIMESTAMP,
    record_source VARCHAR(50)
);

CREATE TABLE deliveries (
    delivery_id   VARCHAR(50) PRIMARY KEY,
    well_id       VARCHAR(50),
    station_id    VARCHAR(50),
    batch_id      VARCHAR(50),
    delivery_date DATE,
    volume        DECIMAL(12, 2),
    load_date     TIMESTAMP,
    record_source VARCHAR(50)
);
