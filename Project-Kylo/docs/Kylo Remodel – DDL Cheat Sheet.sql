Kylo Remodel – DDL Cheat Sheet
🔹 Global Database
Schemas

public

legacy rules* tables (unchanged from 0001_rules.sql)

intake

ingest batch metadata & raw rows

core

unified transactions (canonical form)

control

watermarks, outbox events, company rule versions

intake
CREATE TABLE intake.batches (
  ingest_batch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_stream_id TEXT NOT NULL,
  file_fingerprint CHAR(64) NOT NULL,
  original_filename TEXT,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_count INTEGER NOT NULL CHECK (row_count >= 0),
  status TEXT NOT NULL DEFAULT 'received'
    CHECK (status IN ('received','parsed','loaded','failed')),
  UNIQUE (source_stream_id, file_fingerprint)
);

CREATE TABLE intake.rows (
  ingest_batch_id BIGINT NOT NULL REFERENCES intake.batches ON DELETE CASCADE,
  row_index_0based INTEGER NOT NULL CHECK (row_index_0based >= 0),
  raw_payload JSONB NOT NULL,
  parsed_payload JSONB,
  PRIMARY KEY (ingest_batch_id, row_index_0based)
);

core
CREATE TABLE core.transactions_unified (
  txn_uid UUID PRIMARY KEY,
  company_id UUID NOT NULL,
  source_txn_id TEXT,
  source_stream_id TEXT NOT NULL,
  posted_date DATE NOT NULL,
  amount_cents INTEGER NOT NULL,
  currency_code TEXT NOT NULL DEFAULT 'USD',
  description TEXT,
  counterparty_name TEXT,
  memo TEXT,
  category TEXT,
  hash_norm CHAR(64) NOT NULL,
  file_fingerprint CHAR(64) NOT NULL,
  row_index_0based INTEGER NOT NULL CHECK (row_index_0based >= 0),
  ingest_batch_id BIGINT NOT NULL REFERENCES intake.batches,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_stream_id, file_fingerprint, row_index_0based)
);


Indexes:

(company_id, ingest_batch_id)

(company_id, hash_norm)

(company_id, posted_date)

Trigger: BEFORE UPDATE → core.touch_updated_at() sets updated_at.

control
CREATE TABLE control.company_feeds (
  company_id UUID PRIMARY KEY,
  last_batch_id BIGINT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE control.outbox_events (
  event_id BIGSERIAL PRIMARY KEY,
  topic TEXT NOT NULL,
  payload JSONB NOT NULL,
  event_key TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','published','failed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at TIMESTAMPTZ
);

-- Unique index for idempotent outbox inserts
CREATE UNIQUE INDEX ux_outbox_event_key
  ON control.outbox_events(event_key) WHERE event_key IS NOT NULL;

CREATE TABLE control.company_rules_version (
  company_id UUID PRIMARY KEY,
  version BIGINT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

🔹 Company Database (per company, schema = app)
CREATE TABLE app.transactions (
  txn_uid UUID PRIMARY KEY,
  posted_date DATE NOT NULL,
  amount_cents INTEGER NOT NULL,
  currency_code TEXT NOT NULL DEFAULT 'USD',
  description TEXT,
  counterparty_name TEXT,
  memo TEXT,
  category TEXT,
  source_stream_id TEXT NOT NULL,
  source_file_fingerprint CHAR(64) NOT NULL,
  row_index_0based INTEGER NOT NULL CHECK (row_index_0based >= 0),
  hash_norm CHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_stream_id, source_file_fingerprint, row_index_0based)
);

CREATE TABLE app.rules_active (
  rule_id UUID PRIMARY KEY,
  rule_json JSONB NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.sort_queue (
  queue_id BIGSERIAL PRIMARY KEY,
  txn_uid UUID NOT NULL REFERENCES app.transactions(txn_uid) ON DELETE CASCADE,
  reason TEXT NOT NULL CHECK (reason IN ('feed.updated','rules.updated')),
  enqueued_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Unique constraint enforces idempotent enqueue
CREATE UNIQUE INDEX ux_sort_queue_txn_reason
  ON app.sort_queue (txn_uid, reason);


Trigger: BEFORE UPDATE → app.touch_updated_at() sets updated_at.

🔹 Helpers (optional)
-- Deterministic UUIDv5
SELECT uuid_generate_v5(uuid_ns_url(), 'kylo://txn' || '|' || 'payload');

-- SHA256 hash
SELECT encode(digest('string', 'sha256'), 'hex');

🧾 Key DDL takeaways

Global DB = ingest + canonical transactions + outbox/events + per-company watermarks + global rules versioning.

Company DB = minimal: active snapshot, transactions, and sort queue.

Idempotency baked into:

unique (stream+fingerprint+row) in core.transactions_unified

event_key unique index in control.outbox_events

(txn_uid, reason) unique in app.sort_queue