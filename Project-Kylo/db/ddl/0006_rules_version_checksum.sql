-- Optional: persist the last snapshot checksum alongside version

ALTER TABLE IF EXISTS control.company_rules_version
  ADD COLUMN IF NOT EXISTS last_checksum TEXT;


