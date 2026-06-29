CREATE TABLE customers (
    id INT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT REFERENCES customers(id),
    amount DECIMAL(10, 2)
);
