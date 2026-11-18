-- ============================================================================
-- Ndungu Electronics IMS — Production Database Schema (11 Normalized Tables)
-- Architecture: Integer Cents Currency, Hybrid Tracking, Tamper-Evident Audit
-- ============================================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    applied_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS users (
    user_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username              TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    full_name             TEXT    NOT NULL DEFAULT '',
    password_hash         TEXT    NOT NULL,
    role                  TEXT    NOT NULL DEFAULT 'attendant'
                                  CHECK (role IN ('owner', 'attendant')),
    is_active             INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    must_change_password  INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1)),
    failed_login_attempts INTEGER NOT NULL DEFAULT 0 CHECK (failed_login_attempts >= 0),
    locked_until          TEXT,
    created_at            TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at            TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS invite_tokens (
    token_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash  TEXT    NOT NULL UNIQUE,
    role        TEXT    NOT NULL DEFAULT 'attendant' CHECK (role IN ('owner', 'attendant')),
    created_by  INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    used_by     INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    expires_at  TEXT    NOT NULL,
    used_at     TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS products (
    product_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    sku               TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    sku_normalized    TEXT    NOT NULL UNIQUE,
    name              TEXT    NOT NULL,
    brand             TEXT    NOT NULL,
    model             TEXT    NOT NULL DEFAULT '',
    category_id       INTEGER NOT NULL REFERENCES categories(category_id) ON DELETE RESTRICT,
    tracking_mode     TEXT    NOT NULL DEFAULT 'bulk' CHECK (tracking_mode IN ('bulk', 'serialized')),
    cost_price_cents  INTEGER NOT NULL DEFAULT 0 CHECK (cost_price_cents >= 0),
    price_cents       INTEGER NOT NULL CHECK (price_cents > 0),
    stock             INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    reorder_threshold INTEGER NOT NULL DEFAULT 5 CHECK (reorder_threshold >= 1),
    reorder_qty       INTEGER NOT NULL DEFAULT 10 CHECK (reorder_qty >= 1),
    supplier_name     TEXT    NOT NULL DEFAULT '',
    supplier_phone    TEXT    NOT NULL DEFAULT '',
    is_active         INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_by        INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS promotions (
    promo_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code               TEXT    UNIQUE COLLATE NOCASE,
    name               TEXT    NOT NULL,
    scope              TEXT    NOT NULL CHECK (scope IN ('product', 'category', 'cart')),
    target_product_id  INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    target_category_id INTEGER REFERENCES categories(category_id) ON DELETE CASCADE,
    discount_type      TEXT    NOT NULL CHECK (discount_type IN ('percent', 'fixed_cents')),
    discount_value     INTEGER NOT NULL CHECK (discount_value > 0),
    min_qty            INTEGER NOT NULL DEFAULT 1 CHECK (min_qty >= 1),
    min_subtotal_cents INTEGER NOT NULL DEFAULT 0 CHECK (min_subtotal_cents >= 0),
    stackable          INTEGER NOT NULL DEFAULT 0 CHECK (stackable IN (0, 1)),
    priority           INTEGER NOT NULL DEFAULT 100,
    starts_at          TEXT    NOT NULL,
    ends_at            TEXT    NOT NULL,
    is_active          INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_by         INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    CHECK (
        (scope != 'product' OR target_product_id IS NOT NULL) AND
        (scope != 'category' OR target_category_id IS NOT NULL) AND
        (discount_type != 'percent' OR discount_value <= 90) AND
        (ends_at >= starts_at)
    )
);

CREATE TABLE IF NOT EXISTS sales (
    sale_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_no           TEXT    NOT NULL UNIQUE,
    user_id              INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    cashier_snapshot     TEXT    NOT NULL,
    payment_method       TEXT    NOT NULL DEFAULT 'cash'
                                 CHECK (payment_method IN ('cash', 'mpesa', 'card')),
    payment_reference    TEXT    NOT NULL DEFAULT '',
    subtotal_cents       INTEGER NOT NULL CHECK (subtotal_cents >= 0),
    discount_cents       INTEGER NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
    tax_cents            INTEGER NOT NULL DEFAULT 0 CHECK (tax_cents >= 0),
    total_cents          INTEGER NOT NULL CHECK (total_cents >= 0),
    promo_summary_json   TEXT    NOT NULL DEFAULT '[]',
    status               TEXT    NOT NULL DEFAULT 'completed' CHECK (status IN ('completed', 'voided')),
    void_reason          TEXT    NOT NULL DEFAULT '',
    voided_by            INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    voided_at            TEXT,
    sale_date            TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS sale_items (
    sale_item_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id               INTEGER NOT NULL REFERENCES sales(sale_id) ON DELETE CASCADE,
    product_id            INTEGER REFERENCES products(product_id) ON DELETE SET NULL,
    sku_snapshot          TEXT    NOT NULL,
    product_name_snapshot TEXT    NOT NULL,
    brand_snapshot        TEXT    NOT NULL,
    category_snapshot     TEXT    NOT NULL,
    serial_no_snapshot    TEXT    NOT NULL DEFAULT '',
    quantity              INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents      INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    cost_price_cents      INTEGER NOT NULL DEFAULT 0 CHECK (cost_price_cents >= 0),
    promo_id              INTEGER REFERENCES promotions(promo_id) ON DELETE SET NULL,
    promo_name_snapshot   TEXT    NOT NULL DEFAULT '',
    discount_cents        INTEGER NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
    line_total_cents      INTEGER NOT NULL CHECK (line_total_cents >= 0)
);

CREATE TABLE IF NOT EXISTS product_serials (
    serial_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id           INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    serial_no            TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    serial_normalized    TEXT    NOT NULL UNIQUE,
    status               TEXT    NOT NULL DEFAULT 'in_stock'
                                 CHECK (status IN ('in_stock', 'sold', 'returned', 'damaged')),
    sale_item_id         INTEGER REFERENCES sale_items(sale_item_id) ON DELETE SET NULL,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    sold_at              TEXT
);

CREATE TABLE IF NOT EXISTS stock_movements (
    movement_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id            INTEGER REFERENCES products(product_id) ON DELETE SET NULL,
    sku_snapshot          TEXT    NOT NULL,
    product_name_snapshot TEXT    NOT NULL,
    user_id               INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    username_snapshot     TEXT    NOT NULL,
    movement_type         TEXT    NOT NULL
                                  CHECK (movement_type IN ('initial', 'restock', 'sale', 'void_return', 'adjustment', 'archive')),
    qty_delta             INTEGER NOT NULL,
    stock_before          INTEGER NOT NULL CHECK (stock_before >= 0),
    stock_after           INTEGER NOT NULL CHECK (stock_after >= 0),
    reference_type        TEXT    NOT NULL DEFAULT '',
    reference_id          INTEGER,
    note                  TEXT    NOT NULL DEFAULT '',
    created_at            TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS auth_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    username    TEXT    NOT NULL,
    event_type  TEXT    NOT NULL CHECK (event_type IN ('login_ok', 'login_fail', 'locked', 'logout', 'pw_change', 'invite_register')),
    ip_address  TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Performance and lookup indexes
CREATE INDEX IF NOT EXISTS idx_products_active_name ON products(is_active, name);
CREATE INDEX IF NOT EXISTS idx_products_category    ON products(category_id, is_active);
CREATE INDEX IF NOT EXISTS idx_products_low_stock   ON products(is_active, stock, reorder_threshold);
CREATE INDEX IF NOT EXISTS idx_serials_product      ON product_serials(product_id, status);
CREATE INDEX IF NOT EXISTS idx_promos_active_dates  ON promotions(is_active, starts_at, ends_at);
CREATE INDEX IF NOT EXISTS idx_sales_date_status    ON sales(sale_date, status);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale      ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_movements_product    ON stock_movements(product_id, created_at);
CREATE INDEX IF NOT EXISTS idx_auth_events_user     ON auth_events(username, created_at);
