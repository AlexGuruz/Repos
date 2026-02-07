-- Company config for routing (Kafka consumers, n8n)
CREATE TABLE IF NOT EXISTS control.company_config (
  company_id TEXT NOT NULL,
  db_dsn_rw TEXT NOT NULL,
  db_schema TEXT NOT NULL DEFAULT 'app',
  spreadsheet_id TEXT NOT NULL,
  tab_pending TEXT NOT NULL DEFAULT 'Pending',
  tab_active TEXT NOT NULL DEFAULT 'Active',
  PRIMARY KEY (company_id, db_dsn_rw)
);

-- Seed routing: host.docker.internal works from containers on Docker Desktop
INSERT INTO control.company_config (company_id, db_dsn_rw, spreadsheet_id) VALUES
  ('NUGZ', 'postgresql://postgres:kylo@host.docker.internal:5433/kylo_nugz', '1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE'),
  ('710 EMPIRE', 'postgresql://postgres:kylo@host.docker.internal:5433/kylo_710', '1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE'),
  ('PUFFIN PURE', 'postgresql://postgres:kylo@host.docker.internal:5433/kylo_puffin', '1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE'),
  ('JGD', 'postgresql://postgres:kylo@host.docker.internal:5433/kylo_jgd', '1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE')
ON CONFLICT (company_id, db_dsn_rw) DO NOTHING;
