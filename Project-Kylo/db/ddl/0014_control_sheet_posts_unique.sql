-- Ensure composite uniqueness so duplicate batches per company are skipped safely
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname='control_sheet_posts_batch_signature_key') THEN
    ALTER TABLE control.sheet_posts DROP CONSTRAINT IF EXISTS control_sheet_posts_batch_signature_key;
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_sheet_posts_company_batchsig
  ON control.sheet_posts(company_id, batch_signature);
