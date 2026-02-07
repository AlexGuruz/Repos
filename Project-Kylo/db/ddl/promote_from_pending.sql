-- Promote approved rows from a rules_pending_<slug> table into app.rules_active
-- Usage (example for NUGZ):
--   psql -U postgres -d kylo_nugz -v table_name=rules_pending_nugz -f db/ddl/promote_from_pending.sql

\set ON_ERROR_STOP on
SET client_min_messages = WARNING;

-- Capture psql var into a custom GUC for plpgsql access. Expect psql to provide :table_name
SET kylo.table_name TO :'table_name';

-- Ensure extension for deterministic UUID v5 exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$
DECLARE
  tbl text := current_setting('kylo.table_name', true);
  ns  uuid := '6ba7b811-9dad-11d1-80b4-00c04fd430c8'::uuid; -- URL namespace
  approved_count bigint;
BEGIN
  -- Validate table exists
  IF to_regclass(tbl) IS NULL THEN
    RAISE NOTICE 'Pending table % not found; skipping', tbl;
    RETURN;
  END IF;

  EXECUTE format('SELECT count(*) FROM %I WHERE approved = true', tbl) INTO approved_count;
  IF coalesce(approved_count, 0) = 0 THEN
    RAISE NOTICE 'No approved pending in %; skipping', tbl;
    RETURN;
  END IF;

  -- Rebuild active snapshot atomically
  PERFORM pg_advisory_xact_lock(911042); -- coarse lock to serialize promotions
  EXECUTE 'TRUNCATE app.rules_active';
  EXECUTE format($fmt$
    INSERT INTO app.rules_active (rule_id, rule_json, applied_at, rule_hash)
    SELECT
      uuid_generate_v5(%L::uuid, p.content_hash) AS rule_id,
      jsonb_build_object(
        'source', p.source,
        'target_sheet', p.target_sheet,
        'target_header', p.target_header,
        'approved', true
      ) AS rule_json,
      now() AS applied_at,
      p.content_hash AS rule_hash
    FROM %I AS p
    WHERE p.approved = true
    ORDER BY p.content_hash
  $fmt$, ns::text, tbl);
END $$;

RESET kylo.table_name;


