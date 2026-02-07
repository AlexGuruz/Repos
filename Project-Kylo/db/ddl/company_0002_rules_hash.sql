-- Add content fingerprint to app.rules_active to detect duplicates/changes
-- Requires pgcrypto (installed by 0003_helpers.sql in Global; install here too if needed)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='app' AND table_name='rules_active' AND column_name='rule_hash'
  ) THEN
    ALTER TABLE app.rules_active
      ADD COLUMN rule_hash CHAR(64);

    -- Backfill existing rows
    UPDATE app.rules_active
    SET rule_hash = encode(digest(rule_json::text, 'sha256'), 'hex')::char(64)
    WHERE rule_hash IS NULL;

    -- Enforce uniqueness on content if desired
    CREATE UNIQUE INDEX IF NOT EXISTS ux_rules_active_rule_hash
      ON app.rules_active(rule_hash);
  END IF;
END $$;


