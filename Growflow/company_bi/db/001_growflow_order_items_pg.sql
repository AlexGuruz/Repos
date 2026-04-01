-- GrowFlow order items (Postgres). Use when database.dsn is set to a Postgres connection string.
CREATE TABLE IF NOT EXISTS growflow_order_items (
    id              BIGSERIAL PRIMARY KEY,
    object_id       TEXT NOT NULL,
    sold_at         TIMESTAMPTZ NOT NULL,
    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    day             INTEGER NOT NULL,
    date_str        TEXT NOT NULL,
    gross           NUMERIC(12,2) NOT NULL,
    cog             NUMERIC(12,2) NOT NULL,
    sku             TEXT,
    category        TEXT,
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_growflow_order_items_object_id ON growflow_order_items(object_id);
CREATE INDEX IF NOT EXISTS idx_growflow_order_items_sold_at ON growflow_order_items(sold_at);
CREATE INDEX IF NOT EXISTS idx_growflow_order_items_ym ON growflow_order_items(year, month);
CREATE INDEX IF NOT EXISTS idx_growflow_order_items_sku ON growflow_order_items(sku);
