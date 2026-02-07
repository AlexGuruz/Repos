-- Company DB snapshot apply function (truncate + insert)
-- Idempotent and safe to run repeatedly

CREATE SCHEMA IF NOT EXISTS app;

-- Ensure pgcrypto for digest (if not already installed)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Function: app.apply_rules_snapshot(snapshot jsonb)
CREATE OR REPLACE FUNCTION app.apply_rules_snapshot(snapshot JSONB)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  -- Truncate existing active snapshot for deterministic swaps
  TRUNCATE app.rules_active;

  -- Insert rules from JSONB array, computing per-row content hash
  INSERT INTO app.rules_active (rule_id, rule_json, applied_at, rule_hash)
  SELECT
    (elem->>'rule_id')::uuid,
    (elem->'rule_json')::jsonb,
    now(),
    encode(digest((elem->'rule_json')::text, 'sha256'), 'hex')::char(64)
  FROM jsonb_array_elements(snapshot) AS elem
  ON CONFLICT (rule_id) DO UPDATE
    SET rule_json = EXCLUDED.rule_json,
        applied_at = now(),
        rule_hash = EXCLUDED.rule_hash;
END;
$$;

-- Optional view to expose a deterministic checksum for the current active snapshot
CREATE OR REPLACE VIEW app.rules_active_checksum AS
SELECT
  'md5:' || md5(coalesce(string_agg(rule_id::text || '|' || md5(rule_json::text), E'\n' ORDER BY rule_id), '')) AS snapshot_checksum
FROM app.rules_active;


