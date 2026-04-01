-- GrowFlow order items (sales/inventory data) ingested from API for easier queries and analytics.
-- Run once per environment. SQLite: use company_bi/db/growflow.db. Postgres: set database.dsn in config (see 001_growflow_order_items_pg.sql).

-- SQLite (default)
CREATE TABLE IF NOT EXISTS growflow_order_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id       TEXT NOT NULL,
    sold_at         TEXT NOT NULL,
    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    day             INTEGER NOT NULL,
    date_str        TEXT NOT NULL,
    gross           REAL NOT NULL,
    cog             REAL NOT NULL,
    sku             TEXT,
    category        TEXT,
    ingested_at     TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_growflow_order_items_object_id ON growflow_order_items(object_id);
CREATE INDEX IF NOT EXISTS idx_growflow_order_items_sold_at ON growflow_order_items(sold_at);
CREATE INDEX IF NOT EXISTS idx_growflow_order_items_ym ON growflow_order_items(year, month);
CREATE INDEX IF NOT EXISTS idx_growflow_order_items_sku ON growflow_order_items(sku);
