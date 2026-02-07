-- Helpers for deterministic UUIDv5 and SHA-256 hex (Postgres 16)
-- Install required extensions once per DB
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Deterministic UUIDv5 using a fixed namespace derived from 'kylo://txn'
CREATE SCHEMA IF NOT EXISTS core;

CREATE OR REPLACE FUNCTION core.kylo_txn_uuid(name_text TEXT)
RETURNS UUID
LANGUAGE sql IMMUTABLE AS $$
  SELECT uuid_generate_v5(uuid_generate_v5(uuid_ns_url(), 'kylo://txn'), name_text);
$$;

-- Hex SHA-256 helper
CREATE OR REPLACE FUNCTION core.sha256_hex(input TEXT)
RETURNS CHAR(64)
LANGUAGE sql IMMUTABLE AS $$
  SELECT encode(digest(input, 'sha256'), 'hex')::char(64);
$$;

-- Canonical hash builder matching the remodel spec
CREATE OR REPLACE FUNCTION core.hash_norm_txn(
  p_posted_date DATE,
  p_company_id TEXT,
  p_source_stream_id TEXT,
  p_amount_cents BIGINT,
  p_file_fingerprint CHAR(64),
  p_row_index_0based INTEGER
) RETURNS CHAR(64)
LANGUAGE sql IMMUTABLE AS $$
  SELECT core.sha256_hex(
    to_char(p_posted_date, 'YYYY-MM-DD') || '|' ||
    p_company_id || '|' ||
    p_source_stream_id || '|' ||
    p_amount_cents::TEXT || '|' ||
    p_file_fingerprint || '|' ||
    p_row_index_0based::TEXT
  );
$$;


