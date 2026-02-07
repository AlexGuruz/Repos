-- Rules snapshot activation fixtures for tests
\connect kylo_global

BEGIN;

-- Optional: activation coordination table for tests
CREATE SCHEMA IF NOT EXISTS control;

CREATE TABLE IF NOT EXISTS control.rules_activations (
  company_id TEXT NOT NULL,
  activate_at_batch BIGINT NOT NULL,
  snapshot JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, activate_at_batch)
);

-- Optional: rules version tracker if not present
CREATE TABLE IF NOT EXISTS control.company_rules_version (
  company_id UUID PRIMARY KEY,
  version INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed a version row
INSERT INTO control.company_rules_version (company_id, version, updated_at)
VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 1, now())
ON CONFLICT (company_id) DO UPDATE SET version = EXCLUDED.version, updated_at = now();

-- Seed pending activation at batch 1002
INSERT INTO control.rules_activations (company_id, activate_at_batch, snapshot)
VALUES (
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  1002,
  jsonb_build_array(
    jsonb_build_object(
      'rule_id', '11111111-1111-1111-1111-111111111111',
      'rule_json', jsonb_build_object('name','Office Supplies','pattern','(?i)office|staples','category','710')
    ),
    jsonb_build_object(
      'rule_id', '22222222-2222-2222-2222-222222222222',
      'rule_json', jsonb_build_object('name','Fuel','pattern','(?i)gas|fuel','category','720')
    )
  )
)
ON CONFLICT (company_id, activate_at_batch) DO UPDATE
SET snapshot = EXCLUDED.snapshot;

COMMIT;


-- Ensure at least one transaction exists in company DB so rules.enqueue can produce rows
\connect kylo_company_a
-- Ensure app schema and minimal tables exist (in case company DDL not applied yet)
CREATE SCHEMA IF NOT EXISTS app;
CREATE TABLE IF NOT EXISTS app.transactions (
  txn_uid UUID PRIMARY KEY,
  posted_date DATE,
  amount_cents INTEGER,
  currency_code TEXT,
  description TEXT,
  counterparty_name TEXT,
  memo TEXT,
  category TEXT,
  source_stream_id TEXT,
  source_file_fingerprint CHAR(64),
  row_index_0based INTEGER,
  hash_norm CHAR(64)
);
CREATE TABLE IF NOT EXISTS app.sort_queue (
  queue_id BIGSERIAL PRIMARY KEY,
  txn_uid UUID NOT NULL REFERENCES app.transactions(txn_uid) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  enqueued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (txn_uid, reason)
);
INSERT INTO app.transactions (
  txn_uid, posted_date, amount_cents, currency_code, description,
  counterparty_name, memo, category, source_stream_id, source_file_fingerprint,
  row_index_0based, hash_norm
) VALUES (
  '00000000-0000-0000-0000-000000000001', '2025-01-01', 1000, 'USD', 'seed txn',
  NULL, NULL, NULL, 'seed', repeat('a',64), 0, repeat('b',64)
) ON CONFLICT (txn_uid) DO NOTHING;

