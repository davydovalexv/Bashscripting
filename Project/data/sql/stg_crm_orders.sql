-- Эталонный пример: плоская CRM staging-таблица (клиент + заказ)
CREATE TABLE stg_crm_orders (
    customer_id   VARCHAR(50),
    first_name    VARCHAR(100),
    last_name     VARCHAR(100),
    email         VARCHAR(150),
    order_num     VARCHAR(50),
    order_date    DATE,
    total_amount  DECIMAL(10, 2),
    status        VARCHAR(50),
    load_date     TIMESTAMP,
    record_source VARCHAR(50)
);

INSERT INTO stg_crm_orders
VALUES (
    'C100', 'Иван', 'Иванов', 'ivan@email.com',
    'O-999', '2026-06-25', 5000.00, 'New',
    '2026-06-25 12:00:00', 'CRM_SYS'
);
