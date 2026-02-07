-- CSV Intake Deduplication Tables
-- Adds comprehensive deduplication tracking for CSV intake processing

-- File processing log to prevent processing the same CSV file twice
CREATE TABLE IF NOT EXISTS control.file_processing_log (
    file_fingerprint CHAR(64) PRIMARY KEY,
    batch_id BIGINT REFERENCES control.ingest_batches(batch_id),
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_count INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_file_processing_batch ON control.file_processing_log(batch_id);
CREATE INDEX IF NOT EXISTS ix_file_processing_created ON control.file_processing_log(created_at);

-- Deduplication log for tracking different types of deduplication
CREATE TABLE IF NOT EXISTS control.deduplication_log (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT REFERENCES control.ingest_batches(batch_id),
    dedup_type TEXT NOT NULL, -- 'file', 'content', 'business', 'row'
    original_count INTEGER NOT NULL,
    final_count INTEGER NOT NULL,
    duplicates_skipped INTEGER NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dedup_log_batch ON control.deduplication_log(batch_id);
CREATE INDEX IF NOT EXISTS ix_dedup_log_type ON control.deduplication_log(dedup_type);
CREATE INDEX IF NOT EXISTS ix_dedup_log_processed ON control.deduplication_log(processed_at);

-- Deduplication summary for analytics and monitoring
CREATE TABLE IF NOT EXISTS control.deduplication_summary (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT REFERENCES control.ingest_batches(batch_id),
    file_fingerprint CHAR(64),
    original_parsed INTEGER NOT NULL,
    business_duplicates_found INTEGER NOT NULL DEFAULT 0,
    final_stored INTEGER NOT NULL,
    total_skipped INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dedup_summary_batch ON control.deduplication_summary(batch_id);
CREATE INDEX IF NOT EXISTS ix_dedup_summary_created ON control.deduplication_summary(created_at);

-- Business-level duplicates tracking
CREATE TABLE IF NOT EXISTS control.business_duplicates (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT REFERENCES control.ingest_batches(batch_id),
    company_id TEXT NOT NULL,
    txn_uid UUID NOT NULL,
    existing_txn_uid UUID NOT NULL,
    similarity DECIMAL(5,4) NOT NULL, -- 0.0000 to 1.0000
    posted_date DATE NOT NULL,
    amount_cents INTEGER NOT NULL,
    description TEXT NOT NULL,
    existing_description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_business_duplicates_batch ON control.business_duplicates(batch_id);
CREATE INDEX IF NOT EXISTS ix_business_duplicates_company ON control.business_duplicates(company_id);
CREATE INDEX IF NOT EXISTS ix_business_duplicates_similarity ON control.business_duplicates(similarity);

-- Enhanced intake.raw_transactions with business hash
ALTER TABLE intake.raw_transactions 
ADD COLUMN IF NOT EXISTS business_hash CHAR(64);

-- Add unique constraints for different deduplication strategies
CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_business_hash 
ON intake.raw_transactions(business_hash) WHERE business_hash IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_file_row 
ON intake.raw_transactions(source_file_fingerprint, row_index_0based);

-- Add comments for documentation
COMMENT ON TABLE control.file_processing_log IS 'Tracks processed CSV files to prevent duplicate processing';
COMMENT ON TABLE control.deduplication_log IS 'Logs deduplication metrics for different strategies';
COMMENT ON TABLE control.deduplication_summary IS 'Summary statistics for deduplication analytics';
COMMENT ON TABLE control.business_duplicates IS 'Tracks business-level duplicate transactions for review';

COMMENT ON COLUMN control.deduplication_log.dedup_type IS 'Type of deduplication: file, content, business, row';
COMMENT ON COLUMN control.business_duplicates.similarity IS 'Similarity score between 0.0000 and 1.0000';
COMMENT ON COLUMN intake.raw_transactions.business_hash IS 'Hash for business-level deduplication (same day/amount/similar description)';
