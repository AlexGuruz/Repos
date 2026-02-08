# CSV Intake System — Petty Cash Data Processing

## Overview

The CSV intake system provides an efficient method for processing large volumes of petty cash transaction data from Google Sheets, bypassing API quota limitations and implementing comprehensive deduplication strategies.

## Architecture

### **Data Flow**
1. **CSV Download** → Direct download from Google Sheets CSV export
2. **Multi-Layer Deduplication** → File, row, content, and business-level deduplication
3. **Database Storage** → Bulk insert to pooled database with idempotency
4. **Mover Integration** → Trigger existing mover service for company-specific processing

### **Deduplication Layers**

#### **1. File-Level Deduplication**
- **Purpose**: Prevent processing the same CSV file multiple times
- **Method**: SHA256 hash of entire CSV content
- **Storage**: `control.file_processing_log` table
- **Behavior**: Skip processing if file fingerprint already exists

#### **2. Row-Level Deduplication**
- **Purpose**: Prevent duplicate rows within the same CSV file
- **Method**: Hash of row content + position
- **Behavior**: Skip duplicate rows during parsing

#### **3. Content-Level Deduplication**
- **Purpose**: Prevent identical transactions across different files
- **Method**: Hash of normalized transaction content
- **Storage**: `intake.raw_transactions.fingerprint` unique constraint
- **Behavior**: Skip on database insert conflict

#### **4. Business-Level Deduplication**
- **Purpose**: Detect similar transactions (same day, amount, similar description)
- **Method**: Fuzzy matching on description + exact matching on date/amount
- **Storage**: `control.deduplication_log` for tracking
- **Behavior**: Log potential duplicates for review

## Database Schema

### **New Tables**

#### **control.file_processing_log**
```sql
CREATE TABLE control.file_processing_log (
    file_fingerprint CHAR(64) PRIMARY KEY,
    batch_id BIGINT REFERENCES control.ingest_batches(batch_id),
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_count INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### **control.deduplication_log**
```sql
CREATE TABLE control.deduplication_log (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT REFERENCES control.ingest_batches(batch_id),
    dedup_type TEXT NOT NULL, -- 'file', 'content', 'business', 'row'
    original_count INTEGER NOT NULL,
    final_count INTEGER NOT NULL,
    duplicates_skipped INTEGER NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### **control.deduplication_summary**
```sql
CREATE TABLE control.deduplication_summary (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT REFERENCES control.ingest_batches(batch_id),
    file_fingerprint CHAR(64),
    original_parsed INTEGER NOT NULL,
    business_duplicates_found INTEGER NOT NULL DEFAULT 0,
    final_stored INTEGER NOT NULL,
    total_skipped INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### **Enhanced Existing Tables**

#### **intake.raw_transactions**
```sql
-- Add business hash column
ALTER TABLE intake.raw_transactions 
ADD COLUMN IF NOT EXISTS business_hash CHAR(64);

-- Add unique constraints
CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_business_hash 
ON intake.raw_transactions(business_hash);

CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_file_row 
ON intake.raw_transactions(source_file_fingerprint, row_index_0based);
```

## Configuration

### **Copy CSV to paths outside C:**
In `config/global.yaml` (or layered YAML), you can set `intake.csv_copy_paths` so that certain intakes immediately write the downloaded CSV to specific files (e.g. on D: or E:). Keys are company keys (`NUGZ`, `JGD`, `EMPIRE`, `PUFFIN`); `_default` applies when running without `--company`. Parent directories are created if needed.

```yaml
intake:
  csv_copy_paths:
    NUGZ: ["D:/intake/nugz.csv", "E:/backup/nugz.csv"]
    JGD: ["E:/data/jgd_intake.csv"]
    _default: ["D:/intake/petty_cash.csv"]
```

Copy happens right after download and validation, before parsing and DB storage.

### **CSV Intake Configuration**
```json
{
  "csv_intake": {
    "spreadsheet_id": "1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU",
    "sheet_name": "PETTY CASH",
    "header_rows": 19,
    "column_mapping": {
      "date": 0,
      "amount": 1,
      "company": 2,
      "description": 3
    },
    "batch_size": 1000,
    "date_format": "%m/%d/%Y",
    "amount_format": "currency",
    "deduplication": {
      "business_similarity_threshold": 0.8,
      "enable_business_dedup": true,
      "enable_content_dedup": true
    }
  }
}
```

## Implementation

### **Core Components**

#### **1. CSV Download Service**
- **File**: `services/intake/csv_downloader.py`
- **Purpose**: Download CSV from Google Sheets with authentication
- **Features**: Service account authentication, error handling, retry logic

#### **2. CSV Processor**
- **File**: `services/intake/csv_processor.py`
- **Purpose**: Parse CSV content and extract transactions
- **Features**: Row-level deduplication, data normalization, error handling

#### **3. Deduplication Workflow**
- **File**: `services/intake/deduplication.py`
- **Purpose**: Multi-layer deduplication logic
- **Features**: File, content, and business-level deduplication

#### **4. Database Storage**
- **File**: `services/intake/storage.py`
- **Purpose**: Efficient database storage with bulk operations
- **Features**: COPY operations, conflict resolution, batch processing

### **CLI Tools**

#### **csv_intake.py**
```bash
python bin/csv_intake.py \
  --spreadsheet-id "1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU" \
  --db-url "postgresql://..." \
  --service-account "secrets/service_account.json"
```

#### **csv_dedup_analyzer.py**
```bash
python bin/csv_dedup_analyzer.py \
  --batch-id 123 \
  --output-format json
```

## Monitoring and Analytics

### **Deduplication Metrics**
```sql
-- Daily deduplication summary
SELECT 
    DATE(created_at) as date,
    COUNT(*) as batches_processed,
    SUM(original_parsed) as total_parsed,
    SUM(final_stored) as total_stored,
    SUM(total_skipped) as total_skipped,
    ROUND(100.0 * SUM(total_skipped) / SUM(original_parsed), 2) as dedup_percentage
FROM control.deduplication_summary
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

### **File Processing History**
```sql
-- File processing status
SELECT 
    file_fingerprint,
    processed_at,
    row_count,
    status,
    batch_id
FROM control.file_processing_log
ORDER BY processed_at DESC
LIMIT 10;
```

### **Business Duplicate Analysis**
```sql
-- Business-level duplicates by company
SELECT 
    company_id,
    COUNT(*) as duplicate_count,
    AVG(similarity) as avg_similarity
FROM control.business_duplicates
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY company_id
ORDER BY duplicate_count DESC;
```

## Error Handling

### **Common Error Scenarios**

#### **1. File Already Processed**
- **Error**: File fingerprint exists in `control.file_processing_log`
- **Action**: Skip processing, log warning
- **Recovery**: Manual override available via CLI flag

#### **2. CSV Format Errors**
- **Error**: Malformed CSV, missing columns, invalid data
- **Action**: Log error, skip problematic rows, continue processing
- **Recovery**: Review error logs, fix CSV format

#### **3. Database Constraints**
- **Error**: Unique constraint violations
- **Action**: Skip duplicates, log deduplication metrics
- **Recovery**: Normal behavior, no action required

#### **4. Authentication Errors**
- **Error**: Invalid service account credentials
- **Action**: Retry with exponential backoff
- **Recovery**: Check service account configuration

## Performance Considerations

### **Large File Processing**
- **Chunked Processing**: Process large files in memory-efficient chunks
- **Bulk Database Operations**: Use PostgreSQL COPY for large inserts
- **Parallel Processing**: Process multiple companies in parallel where possible

### **Memory Management**
- **Streaming Parsing**: Parse CSV line-by-line to minimize memory usage
- **Batch Processing**: Process transactions in configurable batch sizes
- **Garbage Collection**: Explicit cleanup of large data structures

### **Database Optimization**
- **Indexing**: Proper indexes on deduplication columns
- **Partitioning**: Consider partitioning for very large datasets
- **Connection Pooling**: Efficient database connection management

## Testing

### **Unit Tests**
- CSV parsing with various formats
- Deduplication logic validation
- Database storage operations
- Error handling scenarios

### **Integration Tests**
- End-to-end CSV processing workflow
- Database constraint validation
- Mover service integration
- Telemetry and monitoring

### **Performance Tests**
- Large file processing (10k+ rows)
- Memory usage validation
- Database performance under load
- Deduplication efficiency metrics

## Future Enhancements

### **Planned Features**
1. **Incremental Processing**: Process only new rows since last run
2. **Real-time Monitoring**: Live dashboard for processing status
3. **Advanced Deduplication**: Machine learning-based similarity detection
4. **Multi-format Support**: Support for Excel, JSON, and other formats
5. **Distributed Processing**: Scale across multiple workers

### **Configuration Enhancements**
1. **Dynamic Column Mapping**: Auto-detect CSV structure
2. **Custom Deduplication Rules**: User-defined business logic
3. **Processing Schedules**: Automated periodic processing
4. **Alert Integration**: Notifications for processing issues
