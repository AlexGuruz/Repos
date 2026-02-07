-- Alias file for Global Two-Phase DDL (Postgres 16)
-- Content mirrors 0002_global_two_phase.sql

CREATE SCHEMA IF NOT EXISTS intake;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS control;

-- Global batches (strictly monotonic across all sources)
CREATE TABLE IF NOT EXISTS control.ingest_batches (
  batch_id   BIGSERIAL PRIMARY KEY,
  source     TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at   TIMESTAMPTZ
);

-- Per-company watermark maintained by mover
CREATE TABLE IF NOT EXISTS control.company_feeds (
  company_id       TEXT PRIMARY KEY,
  last_batch_id    BIGINT NOT NULL DEFAULT 0,
  last_updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Global outbox with idempotent key
CREATE TABLE IF NOT EXISTS control.outbox_events (
  id           BIGSERIAL PRIMARY KEY,
  topic        TEXT NOT NULL,
  payload      JSONB NOT NULL,
  event_key    TEXT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_outbox_topic_created ON control.outbox_events(topic, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS ux_outbox_event_key ON control.outbox_events(event_key) WHERE event_key IS NOT NULL;

-- Raw intake (immutable), fingerprint dedupe, tied to global batch
CREATE TABLE IF NOT EXISTS intake.raw_transactions (
  ingest_id               UUID PRIMARY KEY,
  ingest_batch_id         BIGINT NOT NULL REFERENCES control.ingest_batches(batch_id),
  received_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_stream_id        TEXT NOT NULL,
  company_id              TEXT NOT NULL,
  payload_json            JSONB NOT NULL,
  fingerprint             TEXT NOT NULL,
  source_file_fingerprint CHAR(64) NOT NULL,
  row_index_0based        INTEGER NOT NULL CHECK (row_index_0based >= 0),
  source_txn_id           TEXT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_fingerprint ON intake.raw_transactions(fingerprint);
CREATE INDEX IF NOT EXISTS ix_raw_company_batch ON intake.raw_transactions(company_id, ingest_batch_id);

-- Normalized, deduped core with global batch id, stable identity + canonical hash
CREATE TABLE IF NOT EXISTS core.transactions_unified (
  txn_uid                 UUID PRIMARY KEY,
  company_id              TEXT NOT NULL,
  source_stream_id        TEXT NOT NULL,
  posted_date             DATE NOT NULL,
  currency_code           TEXT NOT NULL DEFAULT 'USD',
  amount_cents            BIGINT NOT NULL,
  description             TEXT,
  counterparty_name       TEXT,
  memo                    TEXT,
  category                TEXT,
  mcc                     TEXT,
  merchant                TEXT,
  source_txn_id           TEXT NULL,
  source_file_fingerprint CHAR(64) NOT NULL,
  row_index_0based        INTEGER NOT NULL CHECK (row_index_0based >= 0),
  hash_norm               CHAR(64) NOT NULL,
  ingest_batch_id         BIGINT NOT NULL REFERENCES control.ingest_batches(batch_id),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_core_company_updated ON core.transactions_unified(company_id, updated_at);
CREATE INDEX IF NOT EXISTS ix_core_company_batch   ON core.transactions_unified(company_id, ingest_batch_id);


-- Company rules versioning (for snapshot activations)
CREATE TABLE IF NOT EXISTS control.company_rules_version (
  company_id      TEXT PRIMARY KEY,
  version         BIGINT NOT NULL DEFAULT 0,
  last_checksum   TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Pending rules activations (snapshot materialized in Global, applied in company DB at batch)
CREATE TABLE IF NOT EXISTS control.rules_activations (
  company_id         TEXT NOT NULL,
  activate_at_batch  BIGINT NOT NULL,
  snapshot           JSONB NOT NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, activate_at_batch)
);

-- Optional: per-company mover run metrics (best-effort writes)
CREATE TABLE IF NOT EXISTS control.mover_runs (
  run_id             UUID NOT NULL,
  company_id         TEXT NOT NULL,
  slice_size         INTEGER NOT NULL,
  inserted           INTEGER NOT NULL,
  updated            INTEGER NOT NULL,
  enqueued           INTEGER NOT NULL,
  advanced_to_batch  BIGINT,
  duration_ms        INTEGER NOT NULL,
  started_at         TIMESTAMPTZ NOT NULL,
  finished_at        TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (run_id, company_id)
);

