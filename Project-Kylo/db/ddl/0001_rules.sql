-- Kylo Remodel — Minimal Rules DDL (Postgres)

-- 1) ENUMS
DO $$ BEGIN
  CREATE TYPE ruleset_state AS ENUM ('active','retired');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 2) TABLES
CREATE TABLE IF NOT EXISTS rulesets (
  id            UUID PRIMARY KEY,
  company_id    TEXT NOT NULL,
  version       INT  NOT NULL,
  state         ruleset_state NOT NULL DEFAULT 'active',
  effective_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
  created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
  UNIQUE (company_id, version)
);

CREATE TABLE IF NOT EXISTS rules (
  id            UUID PRIMARY KEY,
  ruleset_id    UUID NOT NULL REFERENCES rulesets(id) ON DELETE CASCADE,
  date          DATE NULL,
  source        TEXT NOT NULL,
  company_id    TEXT NOT NULL,
  amount_expr   TEXT NULL,  -- exact or range, e.g. "=120.50" or "100..200"
  target_sheet  TEXT NOT NULL,
  target_header TEXT NOT NULL,
  match_notes   TEXT NULL,
  row_hash      TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (company_id, source, row_hash)
);

CREATE TABLE IF NOT EXISTS rule_audit (
  id          UUID PRIMARY KEY,
  company_id  TEXT NOT NULL,
  action      TEXT NOT NULL,  -- PROMOTE | RETIRE | etc.
  ruleset_id  UUID NULL REFERENCES rulesets(id) ON DELETE SET NULL,
  summary     JSONB NULL,
  actor       TEXT NULL,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3) INDEXES
CREATE INDEX IF NOT EXISTS idx_rules_company_source ON rules(company_id, source);
CREATE INDEX IF NOT EXISTS idx_rulesets_company_state ON rulesets(company_id, state);
CREATE INDEX IF NOT EXISTS idx_rules_row_hash ON rules(row_hash);

-- 4) VIEW: current active ruleset per company (optional)
CREATE OR REPLACE VIEW active_rulesets AS
SELECT DISTINCT ON (company_id)
  id, company_id, version, state, effective_at, created_at
FROM rulesets
WHERE state = 'active'
ORDER BY company_id, version DESC;


