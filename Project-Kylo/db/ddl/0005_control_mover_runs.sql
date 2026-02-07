-- control.mover_runs: per-company slice observability (optional)
CREATE SCHEMA IF NOT EXISTS control;

CREATE TABLE IF NOT EXISTS control.mover_runs (
  id BIGSERIAL PRIMARY KEY,
  company_id TEXT NOT NULL,
  ingest_batch_id BIGINT NOT NULL,
  inserted INT NOT NULL,
  updated INT NOT NULL,
  enqueued INT NOT NULL,
  duration_ms INT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_mover_runs_company_batch
  ON control.mover_runs (company_id, ingest_batch_id);

-- Optional observability table for per-company mover runs
-- Applies to the Global database (schema: control)

CREATE TABLE IF NOT EXISTS control.mover_runs (
  run_id UUID NOT NULL,
  company_id TEXT NOT NULL,
  slice_size INT NOT NULL,
  inserted INT NOT NULL,
  updated INT NOT NULL,
  enqueued INT NOT NULL,
  advanced_to_batch BIGINT,
  duration_ms BIGINT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, company_id)
);

CREATE INDEX IF NOT EXISTS idx_mover_runs_company_started
  ON control.mover_runs (company_id, started_at DESC);


