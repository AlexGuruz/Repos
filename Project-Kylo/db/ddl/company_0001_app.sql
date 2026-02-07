-- db/ddl/company_0001_app.sql
-- Postgres 16
-- Per-company database: app schema with transactions, rules snapshot, sort queue.

BEGIN;

CREATE SCHEMA IF NOT EXISTS app;

-- =========================
-- Active company transactions (fed by mover)
-- =========================
CREATE TABLE IF NOT EXISTS app.transactions (
  txn_uid UUID PRIMARY KEY,                 -- deterministic ID from Global
  company_id TEXT NOT NULL,
  posted_date DATE NOT NULL,                -- UTC canonical date
  amount_cents INTEGER NOT NULL,            -- signed cents; debits negative
  currency_code TEXT NOT NULL DEFAULT 'USD',

  description TEXT,
  counterparty_name TEXT,
  memo TEXT,
  category TEXT,

  source_stream_id TEXT NOT NULL,
  source_file_fingerprint CHAR(64) NOT NULL,
  row_index_0based INTEGER NOT NULL CHECK (row_index_0based >= 0),

  hash_norm CHAR(64) NOT NULL,              -- for change detection

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (source_stream_id, source_file_fingerprint, row_index_0based)
);

CREATE INDEX IF NOT EXISTS idx_app_txn_posted_date ON app.transactions(posted_date);
CREATE INDEX IF NOT EXISTS idx_app_txn_hash       ON app.transactions(hash_norm);

CREATE OR REPLACE FUNCTION app.touch_updated_at() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_touch_app_txn ON app.transactions;
CREATE TRIGGER trg_touch_app_txn
BEFORE UPDATE ON app.transactions
FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();

-- =========================
-- Active rules snapshot (no versioning; single live snapshot)
-- Shape-neutral via JSONB; snapshot built in Global then copied here.
-- =========================
CREATE TABLE IF NOT EXISTS app.rules_active (
  rule_id UUID PRIMARY KEY,
  rule_json JSONB NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  rule_hash CHAR(64)
);

-- Optional content hash for deduplication/idempotency of rule content
CREATE UNIQUE INDEX IF NOT EXISTS ux_rules_active_rule_hash ON app.rules_active(rule_hash);

-- =========================
-- Sort queue (downstream worklist). Enqueue txn_uids when feed or rules change.
-- =========================
CREATE TABLE IF NOT EXISTS app.sort_queue (
  queue_id BIGSERIAL PRIMARY KEY,
  txn_uid UUID NOT NULL REFERENCES app.transactions(txn_uid) ON DELETE CASCADE,
  reason  TEXT NOT NULL CHECK (reason IN ('feed.updated','rules.updated')),
  enqueued_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Allow idempotent "do nothing" on duplicates.
CREATE UNIQUE INDEX IF NOT EXISTS ux_sort_queue_txn_reason
  ON app.sort_queue (txn_uid, reason);

CREATE INDEX IF NOT EXISTS idx_sort_queue_reason_time
  ON app.sort_queue (reason, enqueued_at DESC);

-- =========================
-- Outputs (example)
-- =========================
CREATE TABLE IF NOT EXISTS app.outputs_projection (
  txn_uid        UUID PRIMARY KEY,
  target_sheet   TEXT NOT NULL,
  target_header  TEXT NOT NULL,
  decided_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================
-- Outbox for local events (optional)
-- =========================
CREATE TABLE IF NOT EXISTS app.outbox_events (
  id           BIGSERIAL PRIMARY KEY,
  topic        TEXT NOT NULL,
  payload      JSONB NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_app_outbox_topic_created ON app.outbox_events(topic, created_at);

COMMIT;


