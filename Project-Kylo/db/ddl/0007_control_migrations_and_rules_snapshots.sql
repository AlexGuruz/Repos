-- Global control DDL additions (Postgres 16)
-- Idempotent: safe to run multiple times

CREATE SCHEMA IF NOT EXISTS control;

-- Track applied migrations to lock schema and enable auditing
CREATE TABLE IF NOT EXISTS control.migrations (
  id         BIGSERIAL PRIMARY KEY,
  name       TEXT NOT NULL UNIQUE,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  checksum   TEXT
);

-- Store materialized rules snapshots by company/version for audit & replay
CREATE TABLE IF NOT EXISTS control.rules_snapshots (
  snapshot_id        BIGSERIAL PRIMARY KEY,
  company_id         TEXT NOT NULL,
  version            BIGINT NOT NULL,
  snapshot           JSONB NOT NULL,
  snapshot_checksum  TEXT NOT NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (company_id, version)
);

CREATE INDEX IF NOT EXISTS ix_rules_snapshots_company_created
  ON control.rules_snapshots (company_id, created_at DESC);


