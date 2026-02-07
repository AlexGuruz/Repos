-- Create company_config table for n8n workflows
CREATE TABLE IF NOT EXISTS control.company_config (
  company_id TEXT PRIMARY KEY,
  db_dsn_rw TEXT NOT NULL,
  db_schema TEXT NOT NULL DEFAULT 'app',
  spreadsheet_id TEXT NOT NULL,
  tab_pending TEXT NOT NULL DEFAULT 'Pending',
  tab_active TEXT NOT NULL DEFAULT 'Active'
);

-- Insert sample data for testing
-- Using the spreadsheet IDs from companies.json
INSERT INTO control.company_config (company_id, db_dsn_rw, spreadsheet_id) VALUES
('710', 'postgresql://postgres:password@localhost:5432/kylo', '1A1J_u4PDExvi_TujgHNBvBSW9xuGFSKJYQr0xoO73b4'),
('711', 'postgresql://postgres:password@localhost:5432/kylo', '1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE'),
('NUGZ', 'postgresql://postgres:password@localhost:5432/kylo', '1hXG_doc4R2ODSDpjElsNgSel54kP1q2qb2RmNBOMeco'),
('PUFFIN', 'postgresql://postgres:password@localhost:5432/kylo', '1SeMGqClTe_osvDM2sH5d-M55drsqzRIgxWgKjDUA0rU'),
('JGD', 'postgresql://postgres:password@localhost:5432/kylo', '1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE')
ON CONFLICT (company_id) DO NOTHING;
