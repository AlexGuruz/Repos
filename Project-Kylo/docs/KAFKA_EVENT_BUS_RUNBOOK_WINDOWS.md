# Kafka Event Bus Runbook (Windows)

This runbook guides you through setting up and testing the Kafka event-bus architecture for Kylo on Windows.

## Prerequisites

- Docker Desktop for Windows installed and running
- Python 3.8+ with pip
- PostgreSQL running (via docker-compose.yml)
- n8n instance running
- Google Sheets API credentials configured
- PowerShell 5.0+

## Step 1: Start Infrastructure & Topics

```powershell
# Start Kafka (Redpanda) infrastructure
docker compose -f docker-compose.kafka.yml up -d

# Wait for Redpanda to be healthy, then create topics
.\scripts\active\kafka_topics.ps1
```

## Step 2: Apply Database Schema Updates

```powershell
# Apply the sheet_posts composite uniqueness constraint
psql "$env:PG_DSN_RW" -f db/ddl/0014_control_sheet_posts_unique.sql
```

## Step 3: Seed Company Configuration

Ensure `control.company_config` table exists and is populated:

```sql
-- Create table if it doesn't exist
CREATE TABLE IF NOT EXISTS control.company_config (
    company_id VARCHAR(50) PRIMARY KEY,
    db_dsn_rw TEXT NOT NULL,
    db_schema VARCHAR(50) NOT NULL,
    spreadsheet_id VARCHAR(100) NOT NULL,
    tab_pending VARCHAR(100) NOT NULL,
    tab_active VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert/update company configurations
INSERT INTO control.company_config(company_id, db_dsn_rw, db_schema, spreadsheet_id, tab_pending, tab_active)
VALUES
('710', '<PG_DSN_RW>', 'app_710', '<SHEET_ID_710>', '710 Pending', '710 Active'),
('711', '<PG_DSN_RW>', 'app_711', '<SHEET_ID_711>', '711 Pending', '711 Active')
ON CONFLICT (company_id) DO UPDATE
  SET db_dsn_rw=excluded.db_dsn_rw, 
      db_schema=excluded.db_schema,
      spreadsheet_id=excluded.spreadsheet_id, 
      tab_pending=excluded.tab_pending, 
      tab_active=excluded.tab_active,
      updated_at=NOW();
```

**Replace the placeholders:**
- `<PG_DSN_RW>`: Your PostgreSQL connection string
- `<SHEET_ID_710>`: Google Sheets ID for company 710
- `<SHEET_ID_711>`: Google Sheets ID for company 711

## Step 4: Install Dependencies

```powershell
pip install -r requirements-kafka.txt
```

## Step 5: Start Consumers (Shadow Mode)

Start the Kafka consumers in shadow mode (no Sheets posting):

```powershell
# Start consumers in shadow mode (no Sheets posting)
.\scripts\active\start_kafka_consumers.ps1 -SheetsPost "0"
```

## Step 6: Configure n8n Credentials

In your n8n instance, configure these credentials:

### Postgres Credential: "Kylo Postgres RW"
- Host: localhost
- Port: 5432
- Database: kylo
- User: postgres
- Password: kylo

### Kafka Credential: "Redpanda Dev"
- Bootstrap Servers: localhost:9092
- Security Protocol: PLAINTEXT

## Step 7: Import n8n Workflows

Import the two workflow files from `workflows/n8n/`:
1. `workflows/n8n/n8n_ingest_publish_kafka.json` - Ingest → Publish (Kafka)
2. `workflows/n8n/n8n_promote_publish_kafka.json` - Promote Rules → Publish (Kafka)

## Step 8: Test Ingest Flow (Pending Path)

### 8.1 Enable Ingest Workflow
In n8n, enable the "Ingest → Publish (Kafka)" workflow.

### 8.2 Test Transaction Ingestion
```powershell
# Use the PowerShell test script
.\tools\debug\test_ingest_flow.ps1
```

Or manually:
```powershell
$testData = @{
    transactions = @(
        @{id="t1"; company_id="710"; date="2025-08-26"; amount=-12.34; description="STARBUCKS"},
        @{id="t2"; company_id="711"; date="2025-08-26"; amount=45.67; description="WALMART"},
        @{id="t3"; company_id="710"; date="2025-08-26"; amount=10.00; description="UNKNOWN"}
    )
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "http://localhost:5678/webhook/txns.ingest" -Method POST -Body $testData -ContentType "application/json"
```

### 8.3 Verify Shadow Mode
- Check consumer logs for processing
- Verify DB: pending rows exist for batch
- No new rows in `control.sheet_posts` (shadow mode)

## Step 9: Enable Sheets Posting (Pending)

```powershell
# Stop existing consumers
Get-Process python | Where-Object {$_.ProcessName -eq "python"} | Stop-Process

# Restart with posting enabled
.\scripts\active\start_kafka_consumers.ps1 -SheetsPost "1"
```

### 9.1 Re-test Ingest
Re-fire the same ingest payload and verify:
- "710 Pending" tab updated
- "711 Pending" tab updated  
- `sheet_posts` rows inserted with `(company_id, batch_signature)`

## Step 10: Test Duplicate Safety

Re-POST the exact same payload → no new `sheet_posts` rows (composite unique constraint prevents duplicates).

## Step 11: Test Promote/Active Flow

### 11.1 Enable Promote Workflow
In n8n, enable the "Promote Rules → Publish (Kafka)" workflow.

### 11.2 Execute Promote
Click "Execute" on the Manual Trigger node in the promote workflow.

### 11.3 Verify Active Flow
Consumer should:
1. Run `rules_promote` → move approved pending to `app.rules_active`
2. Run `replay_after_promotion`
3. BatchUpdate Active tab: delete rows 2..end, append rows
4. Record `sheet_posts` (signature over rules' content)

Verify:
- Active tabs updated
- `sheet_posts` entries for Active tabs

## Step 12: Rollback Procedure

If issues occur:

```powershell
# Stop consumers
Get-Process python | Where-Object {$_.ProcessName -eq "python"} | Stop-Process

# Disable n8n workflows
# (Manually disable in n8n UI)

# Direct path remains intact
# Kafka messages persist for later reprocessing
```

## Monitoring

### Kafka Console
Access Redpanda Console at: http://localhost:8080

### Consumer Logs
Monitor consumer output for:
- Message processing
- Error handling
- Deduplication events

### Database Verification
```sql
-- Check sheet_posts for deduplication
SELECT company_id, tab_name, batch_signature, row_count, created_at 
FROM control.sheet_posts 
ORDER BY created_at DESC;

-- Check pending transactions
SELECT company_id, COUNT(*) as pending_count 
FROM app.pending_txns 
WHERE status = 'open' 
GROUP BY company_id;
```

## Troubleshooting

### Common Issues

1. **Consumer Connection Errors**
   - Verify Redpanda is running: `docker ps | findstr redpanda`
   - Check broker address: `$env:KAFKA_BROKERS=localhost:9092`

2. **Database Connection Errors**
   - Verify PostgreSQL is running
   - Check `$env:PG_DSN_RW` environment variable

3. **Sheets API Errors**
   - Verify `$env:GOOGLE_APPLICATION_CREDENTIALS` path
   - Check service account permissions

4. **Duplicate Key Errors**
   - Verify DDL was applied: `0014_control_sheet_posts_unique.sql`
   - Check composite unique index exists

5. **PowerShell Execution Policy**
   - If scripts won't run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### Log Analysis
```powershell
# Check running Python processes
Get-Process python

# Check Docker containers
docker ps | findstr redpanda
docker logs kylo-redpanda
```

## Production Deployment

For production deployment:

1. **Scale Consumers**: Run multiple consumer instances
2. **Monitoring**: Add metrics collection
3. **Security**: Enable TLS/SASL for Kafka
4. **Backup**: Configure Kafka topic retention policies
5. **Alerting**: Set up alerts for consumer failures
