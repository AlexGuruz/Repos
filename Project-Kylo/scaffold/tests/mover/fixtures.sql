-- Seed data for mover smoke test
-- Databases expected: kylo_global, kylo_company_a, kylo_company_b

-- In kylo_global: create one batch and two core transactions for Company A
\connect kylo_global

-- Ensure schemas exist (idempotent in case DDL not yet applied here)
CREATE SCHEMA IF NOT EXISTS intake;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS control;

-- Global batch 1001
INSERT INTO control.ingest_batches(batch_id, source, started_at)
VALUES (1001, 'cashpool', now())
ON CONFLICT (batch_id) DO NOTHING;

-- Ensure company feed rows exist for A and B with last_batch_id = 0
INSERT INTO control.company_feeds(company_id, last_batch_id)
VALUES ('company_a', 0)
ON CONFLICT (company_id) DO NOTHING;

INSERT INTO control.company_feeds(company_id, last_batch_id)
VALUES ('company_b', 0)
ON CONFLICT (company_id) DO NOTHING;

-- Two unified transactions for Company A (none for B)
-- Deterministic IDs using helpers: txn_uid and hash_norm
WITH t AS (
  SELECT
    'company_a'::text               AS company_id,
    'cashpool'::text                AS source_stream_id,
    '2025-02-21'::date              AS posted_date,
    12345::bigint                   AS amount_cents,
    'Test Coffee 1'::text           AS description,
    NULL::text                      AS counterparty_name,
    NULL::text                      AS memo,
    NULL::text                      AS category,
    NULL::text                      AS mcc,
    NULL::text                      AS merchant,
    NULL::text                      AS source_txn_id,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'::char(64) AS file_fp,
    0::int                          AS row_idx
  UNION ALL
  SELECT
    'company_a',
    'cashpool',
    '2025-02-22'::date,
    -2500::bigint,
    'Test Debit 2',
    NULL, NULL, NULL, NULL, NULL,
    NULL,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'::char(64),
    1
)
INSERT INTO core.transactions_unified (
  txn_uid, company_id, source_stream_id, posted_date, currency_code,
  amount_cents, description, counterparty_name, memo, category, mcc, merchant,
  source_txn_id, source_file_fingerprint, row_index_0based, hash_norm, ingest_batch_id
)
SELECT
  core.kylo_txn_uuid(t.source_stream_id || '|' || t.file_fp || '|' || t.row_idx) AS txn_uid,
  t.company_id,
  t.source_stream_id,
  t.posted_date,
  'USD'::text,
  t.amount_cents,
  t.description,
  t.counterparty_name,
  t.memo,
  t.category,
  t.mcc,
  t.merchant,
  t.source_txn_id,
  t.file_fp,
  t.row_idx,
  core.hash_norm_txn(t.posted_date, t.company_id, t.source_stream_id, t.amount_cents, t.file_fp, t.row_idx) AS hash_norm,
  1001 AS ingest_batch_id
FROM t
ON CONFLICT (txn_uid) DO NOTHING;

-- Per-company DBs should already be created and DDL applied separately
\connect kylo_company_a
CREATE SCHEMA IF NOT EXISTS app;
\connect kylo_company_b
CREATE SCHEMA IF NOT EXISTS app;


