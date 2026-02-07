-- control.company_rules_version for pending activations and snapshots
CREATE SCHEMA IF NOT EXISTS control;

CREATE TABLE IF NOT EXISTS control.company_rules_version (
  company_id TEXT PRIMARY KEY,
  version INT NOT NULL DEFAULT 0,
  pending_version INT,
  activate_at_batch_id BIGINT,
  rules_snapshot JSONB,
  updated_at TIMESTAMPTZ DEFAULT now()
);


