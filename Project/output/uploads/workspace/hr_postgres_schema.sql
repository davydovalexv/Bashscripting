-- HR database schema for PostgreSQL
-- Contains:
-- 1) Monthly average headcount table
-- 2) Personnel movement table with dismissal reasons

DROP DATABASE IF EXISTS hr_db;
CREATE DATABASE hr_db;

\connect hr_db;

-- =========================
-- Reference tables
-- =========================

CREATE TABLE legal_entities (
    id BIGSERIAL PRIMARY KEY,
    enterprise_code VARCHAR(20) NOT NULL UNIQUE,
    enterprise_name TEXT NOT NULL
);

CREATE TABLE employee_categories (
    id SMALLSERIAL PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE employment_statuses (
    id SMALLSERIAL PRIMARY KEY,
    status_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE dismissal_reasons (
    id SMALLSERIAL PRIMARY KEY,
    reason_name TEXT NOT NULL UNIQUE
);

-- =========================
-- Main table #1:
-- Monthly average headcount
-- =========================

CREATE TABLE monthly_average_headcount (
    id BIGSERIAL PRIMARY KEY,
    year SMALLINT NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    month SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    legal_entity_id BIGINT NOT NULL REFERENCES legal_entities(id),
    employee_category_id SMALLINT NOT NULL REFERENCES employee_categories(id),
    employment_status_id SMALLINT NOT NULL REFERENCES employment_statuses(id),
    position_name VARCHAR(200) NOT NULL,
    personnel_number VARCHAR(50) NOT NULL,
    mobilized BOOLEAN NOT NULL DEFAULT FALSE,
    pregnancy BOOLEAN NOT NULL DEFAULT FALSE,
    working_pensioner BOOLEAN NOT NULL DEFAULT FALSE,
    average_headcount NUMERIC(12, 4) NOT NULL CHECK (average_headcount >= 0),
    count_start_period INTEGER NOT NULL CHECK (count_start_period >= 0),
    count_end_period INTEGER NOT NULL CHECK (count_end_period >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (year, month, legal_entity_id, personnel_number, employment_status_id)
);

CREATE INDEX idx_mah_period_entity
    ON monthly_average_headcount (year, month, legal_entity_id);

CREATE INDEX idx_mah_personnel_number
    ON monthly_average_headcount (personnel_number);

-- =========================
-- Main table #2:
-- Personnel movements
-- =========================

CREATE TABLE personnel_movements (
    id BIGSERIAL PRIMARY KEY,
    year SMALLINT NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    month SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    legal_entity_id BIGINT NOT NULL REFERENCES legal_entities(id),
    personnel_number VARCHAR(50) NOT NULL,
    full_name VARCHAR(200),
    position_name VARCHAR(200),
    movement_type VARCHAR(30) NOT NULL CHECK (
        movement_type IN ('hired', 'dismissed', 'transfer', 'other')
    ),
    movement_date DATE,
    dismissal_reason_id SMALLINT REFERENCES dismissal_reasons(id),
    dismissal_reason_comment TEXT,
    document_number VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (movement_type = 'dismissed' AND dismissal_reason_id IS NOT NULL)
        OR
        (movement_type <> 'dismissed')
    )
);

CREATE INDEX idx_pm_period_entity
    ON personnel_movements (year, month, legal_entity_id);

CREATE INDEX idx_pm_dismissals
    ON personnel_movements (year, month, legal_entity_id, dismissal_reason_id)
    WHERE movement_type = 'dismissed';

CREATE INDEX idx_pm_personnel_number
    ON personnel_movements (personnel_number);

-- =========================
-- Seed data
-- =========================

-- Four legal entities (replace names/codes if needed)
INSERT INTO legal_entities (enterprise_code, enterprise_name) VALUES
    ('LE01', 'Юридическое лицо 1'),
    ('LE02', 'Юридическое лицо 2'),
    ('LE03', 'Юридическое лицо 3'),
    ('LE04', 'Юридическое лицо 4');

INSERT INTO employee_categories (category_name) VALUES
    ('Специалист'),
    ('Руководитель'),
    ('Рабочий'),
    ('Административный персонал'),
    ('Прочее');

INSERT INTO employment_statuses (status_name) VALUES
    ('Принят'),
    ('Уволен'),
    ('Занятый'),
    ('Не занятый');

INSERT INTO dismissal_reasons (reason_name) VALUES
    ('По собственному желанию'),
    ('Сокращение штата'),
    ('Окончание срочного договора'),
    ('Нарушение трудовой дисциплины'),
    ('Соглашение сторон'),
    ('Иное');

-- Optional helper trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_monthly_average_headcount_updated_at
BEFORE UPDATE ON monthly_average_headcount
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_personnel_movements_updated_at
BEFORE UPDATE ON personnel_movements
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Sample query:
-- Determine dismissal reasons by year/month/enterprise
-- SELECT pm.year,
--        pm.month,
--        le.enterprise_code,
--        le.enterprise_name,
--        dr.reason_name,
--        COUNT(*) AS dismissals_count
-- FROM personnel_movements pm
-- JOIN legal_entities le ON le.id = pm.legal_entity_id
-- LEFT JOIN dismissal_reasons dr ON dr.id = pm.dismissal_reason_id
-- WHERE pm.movement_type = 'dismissed'
-- GROUP BY pm.year, pm.month, le.enterprise_code, le.enterprise_name, dr.reason_name
-- ORDER BY pm.year, pm.month, le.enterprise_code, dismissals_count DESC;

-- =========================
-- Data marts for dashboard
-- =========================

CREATE SCHEMA IF NOT EXISTS dm;

-- 1) Chart: average headcount fact by year/month/legal entity
CREATE OR REPLACE VIEW dm.v_ssc_fact AS
SELECT
    mah.year,
    mah.month,
    le.enterprise_code,
    le.enterprise_name,
    SUM(mah.average_headcount) AS ssc_fact
FROM monthly_average_headcount mah
JOIN legal_entities le ON le.id = mah.legal_entity_id
GROUP BY mah.year, mah.month, le.enterprise_code, le.enterprise_name;

-- 2) Chart: hired / dismissed by year/month/legal entity
CREATE OR REPLACE VIEW dm.v_hired_dismissed_fact AS
SELECT
    pm.year,
    pm.month,
    le.enterprise_code,
    le.enterprise_name,
    COUNT(*) FILTER (WHERE pm.movement_type = 'hired') AS hired_count,
    COUNT(*) FILTER (WHERE pm.movement_type = 'dismissed') AS dismissed_count
FROM personnel_movements pm
JOIN legal_entities le ON le.id = pm.legal_entity_id
GROUP BY pm.year, pm.month, le.enterprise_code, le.enterprise_name;

-- 3) Chart: dismissal reasons by year/month/legal entity
CREATE OR REPLACE VIEW dm.v_dismissal_reasons_fact AS
SELECT
    pm.year,
    pm.month,
    le.enterprise_code,
    le.enterprise_name,
    COALESCE(dr.reason_name, 'Не указана') AS dismissal_reason,
    COUNT(*) AS dismissed_count
FROM personnel_movements pm
JOIN legal_entities le ON le.id = pm.legal_entity_id
LEFT JOIN dismissal_reasons dr ON dr.id = pm.dismissal_reason_id
WHERE pm.movement_type = 'dismissed'
GROUP BY
    pm.year,
    pm.month,
    le.enterprise_code,
    le.enterprise_name,
    COALESCE(dr.reason_name, 'Не указана');

-- Alternative: one unified long-form mart for all charts
CREATE OR REPLACE VIEW dm.v_hr_dashboard_unified AS
SELECT
    'ssc_fact'::TEXT AS metric_name,
    s.year,
    s.month,
    s.enterprise_code,
    s.enterprise_name,
    NULL::TEXT AS metric_subtype,
    s.ssc_fact::NUMERIC AS metric_value
FROM dm.v_ssc_fact s

UNION ALL

SELECT
    'hired_dismissed'::TEXT AS metric_name,
    h.year,
    h.month,
    h.enterprise_code,
    h.enterprise_name,
    'hired'::TEXT AS metric_subtype,
    h.hired_count::NUMERIC AS metric_value
FROM dm.v_hired_dismissed_fact h

UNION ALL

SELECT
    'hired_dismissed'::TEXT AS metric_name,
    h.year,
    h.month,
    h.enterprise_code,
    h.enterprise_name,
    'dismissed'::TEXT AS metric_subtype,
    h.dismissed_count::NUMERIC AS metric_value
FROM dm.v_hired_dismissed_fact h

UNION ALL

SELECT
    'dismissal_reason'::TEXT AS metric_name,
    d.year,
    d.month,
    d.enterprise_code,
    d.enterprise_name,
    d.dismissal_reason::TEXT AS metric_subtype,
    d.dismissed_count::NUMERIC AS metric_value
FROM dm.v_dismissal_reasons_fact d;

-- If dashboard becomes slow on large volumes, use materialized views:
-- CREATE MATERIALIZED VIEW dm.mv_ssc_fact AS
-- SELECT * FROM dm.v_ssc_fact;
--
-- CREATE MATERIALIZED VIEW dm.mv_hired_dismissed_fact AS
-- SELECT * FROM dm.v_hired_dismissed_fact;
--
-- CREATE MATERIALIZED VIEW dm.mv_dismissal_reasons_fact AS
-- SELECT * FROM dm.v_dismissal_reasons_fact;
--
-- Refresh schedule example:
-- REFRESH MATERIALIZED VIEW dm.mv_ssc_fact;
-- REFRESH MATERIALIZED VIEW dm.mv_hired_dismissed_fact;
-- REFRESH MATERIALIZED VIEW dm.mv_dismissal_reasons_fact;


enriched = (
    orders.withColumn("revenue", F.col("qty") * F.col("price"))
    .join(users, on="user_id", how="inner")
    .join(products, on="product_id", how="inner")
)

agg = (
    enriched.groupBy("city", "product_id", "product_name")
    .agg(
        F.count("order_id").alias("orders_cnt"),
        F.sum("qty").alias("qty_sum"),
        F.sum("revenue").alias("revenue_sum"),
    )
)

w = Window.partitionBy("city").orderBy(F.col("revenue_sum").desc())
mart_city_top_products = (
    agg.withColumn("rn", F.row_number().over(w))
    .where(F.col("rn") <= 2)
    .drop("rn")
)


output_path = "s3a://hadoop/mart_city_top_products/"
(
    mart_city_top_products.write.mode("overwrite")
    .format("parquet")
    .save(output_path)
)

read_back = spark.read.parquet(output_path)
read_back.orderBy("city", F.col("revenue_sum").desc()).show(truncate=False)