-- ==========================================================================
-- Ndungu Electronics Inventory Management System - Database Schema (SQLite)
-- Implements the ERD from Chapter Two: Shop owner (users) -> Product -> Sale
-- Safe to run repeatedly (IF NOT EXISTS).
-- ==========================================================================

PRAGMA foreign_keys = ON;

-- Shop owner / staff accounts (ERD entity: Shop owner, Class: User)
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,                     -- never store plain passwords
    role          TEXT    NOT NULL DEFAULT 'owner'
                          CHECK (role IN ('owner', 'attendant')),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Products held in stock (ERD entity: Product)
CREATE TABLE IF NOT EXISTS products (
    product_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    brand       TEXT    NOT NULL,
    model       TEXT    NOT NULL DEFAULT '',
    category    TEXT    NOT NULL,
    serial_no   TEXT    NOT NULL UNIQUE COLLATE NOCASE, -- duplicate prevention (Objective 5)
    price       REAL    NOT NULL CHECK (price >= 0),
    stock       INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),  -- stock can never go negative
    user_id     INTEGER REFERENCES users(user_id) ON DELETE SET NULL,  -- "Shop owner manages Product"
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Sales transactions (ERD entity: Sale, "Product records Sale")
-- product_name / serial_no / category are snapshots so that the sales history
-- stays complete even if a product is later removed from the inventory.
CREATE TABLE IF NOT EXISTS sales (
    sale_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id   INTEGER REFERENCES products(product_id) ON DELETE SET NULL,
    user_id      INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    product_name TEXT    NOT NULL,
    serial_no    TEXT    NOT NULL,
    category     TEXT    NOT NULL,
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    unit_price   REAL    NOT NULL CHECK (unit_price >= 0),
    total_price  REAL    NOT NULL CHECK (total_price >= 0),
    sale_date    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_sales_date    ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id);
