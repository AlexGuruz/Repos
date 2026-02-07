-- Reconcile control.mover_runs schema with service expectations
CREATE SCHEMA IF NOT EXISTS control;

-- Add new columns if missing
ALTER TABLE control.mover_runs
  ADD COLUMN IF NOT EXISTS run_id UUID,
  ADD COLUMN IF NOT EXISTS slice_size INT,
  ADD COLUMN IF NOT EXISTS advanced_to_batch BIGINT,
  ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ DEFAULT now(),
  ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ DEFAULT now();

-- Widen duration_ms for large runs
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='control' AND table_name='mover_runs'
      AND column_name='duration_ms' AND data_type IN ('integer')
  ) THEN
    ALTER TABLE control.mover_runs ALTER COLUMN duration_ms TYPE BIGINT;
  END IF;
END $$;

-- Backfill defaults for NOT NULL guarantees (idempotent for existing rows)
UPDATE control.mover_runs
SET run_id = COALESCE(run_id, '00000000-0000-0000-0000-000000000000'::uuid),
    slice_size = COALESCE(slice_size, 0),
    started_at = COALESCE(started_at, now()),
    finished_at = COALESCE(finished_at, now());

-- Enforce NOT NULL where appropriate
ALTER TABLE control.mover_runs
  ALTER COLUMN run_id SET NOT NULL,
  ALTER COLUMN slice_size SET NOT NULL,
  ALTER COLUMN started_at SET NOT NULL,
  ALTER COLUMN finished_at SET NOT NULL;

-- Provide a unique index to support ON CONFLICT (run_id, company_id)
CREATE UNIQUE INDEX IF NOT EXISTS ux_mover_runs_run_company
  ON control.mover_runs (run_id, company_id);


