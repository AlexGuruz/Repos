# Post-Deployment Validation Checklist: Kafka Fan-Out Architecture

## Overview
This checklist validates the full Kafka fan-out architecture deployment with phased testing from shadow mode to full production readiness.

**Testing Strategy:**
- Shadow-mode ingest (no Sheets writes) → verify DB effects only
- Canary one company with real posting → verify idempotency + metrics  
- Promote/replay path → verify Active rebuild + replay behavior
- Ordering, retry/DLQ, and duplicate-safety drills
- Load sanity + rollback switch

---

## 0) Pre-Checks

### 0.1 Services Up
```bash
# Redpanda/Console
docker compose -f docker-compose.kafka.yml ps

# Expected: Both redpanda and console containers running
# Pass: All containers show "Up" status
```

### 0.2 n8n Workflows Imported & Enabled
Verify these workflows are imported and enabled in n8n UI:
- "Ingest & Publish (Kafka)" 
- "Promote Rules → Publish (Kafka)"

**Pass:** Both workflows show as "Active" in n8n dashboard

### 0.3 Environment Setup (dev)
```bash
export KAFKA_BROKERS=localhost:9092
export KAFKA_TOPIC_TXNS=txns.company.batches
export KAFKA_TOPIC_PROMOTE=rules.promote.requests
export KAFKA_GROUP_TXNS=kylo-workers-txns
export KAFKA_GROUP_PROMOTE=kylo-workers-promote
export KYLO_SHEETS_POST=0   # shadow start
```

### 0.4 Consumers Running
Start in two separate terminals:
```bash
# Terminal 1
python -m services.bus.kafka_consumer_txns

# Terminal 2  
python -m services.bus.kafka_consumer_promote
```

**Pass:** Both consumers start without errors and show "Starting consumer..." messages

---

## 1) Shadow-Mode Ingest (Pending Path)

### 1.1 Send Mixed-Company Batch
```bash
curl -X POST http://localhost:5678/webhook/txns.ingest \
  -H "content-type: application/json" \
  -d '{
    "transactions": [
      {"id":"t1","company_id":"710","date":"2025-08-26","amount":-12.34,"description":"STARBUCKS #123"},
      {"id":"t2","company_id":"711","date":"2025-08-26","amount":45.67,"description":"WALMART 0001"},
      {"id":"t3","company_id":"710","date":"2025-08-26","amount":10.00,"description":"SHELL OIL"}
    ]
  }'
```

**Expected:**
- n8n responds: `{"ok":true,"items_published":2}`
- Txns consumer logs show for each company:
  - "Move slice → Triage → Build pending batch → (skip post; shadow)"

### 1.2 Verify DB Effects Only
```sql
-- Pending rows exist (status=open) for both companies:
SELECT company_id, count(*) 
FROM app.pending_txns
WHERE status='open' AND occurred_at >= current_date - interval '1 day'
GROUP BY company_id;

-- No sheet posts in shadow:
SELECT count(*) FROM control.sheet_posts;
```

**Pass Criteria:**
- ✅ Counts appear in `pending_txns` for companies 710 and 711
- ✅ `sheet_posts` count unchanged (shadow mode)

---

## 2) Canary One Company with Real Posting

### 2.1 Enable Sheets Posting
```bash
# Stop txns consumer (Ctrl+C), then restart with:
export KYLO_SHEETS_POST=1
python -m services.bus.kafka_consumer_txns
```

### 2.2 Re-Ingest Same Payload
```bash
# Run the same curl as §1.1
curl -X POST http://localhost:5678/webhook/txns.ingest \
  -H "content-type: application/json" \
  -d '{
    "transactions": [
      {"id":"t1","company_id":"710","date":"2025-08-26","amount":-12.34,"description":"STARBUCKS #123"},
      {"id":"t2","company_id":"711","date":"2025-08-26","amount":45.67,"description":"WALMART 0001"},
      {"id":"t3","company_id":"710","date":"2025-08-26","amount":10.00,"description":"SHELL OIL"}
    ]
  }'
```

**Expected:**
- Only canary company (e.g., 710) posts to Sheets
- `{CID} Pending` tab updated with new rows

### 2.3 Verify DB Signature Recorded
```sql
SELECT company_id, tab_name, row_count, created_at
FROM control.sheet_posts
ORDER BY created_at DESC
LIMIT 5;
```

### 2.4 Duplicate Safety Test
Re-send exact same payload:
```bash
# Same curl command as above
```

**Expected:**
- No additional `sheet_posts` row for same `(company_id, signature)`
- Spreadsheet row count unchanged

**Pass Criteria:**
- ✅ One new row in `sheet_posts` for canary company's Pending tab
- ✅ Second send produces no new `sheet_posts` rows

---

## 3) Promote / Replay → Active Flow

### 3.1 Shadow Promote
```bash
# Keep KYLO_SHEETS_POST=0 for promote consumer
# Ensure promote consumer is running:
python -m services.bus.kafka_consumer_promote
```

In n8n, run "Promote Rules → Publish (Kafka)" (Manual Trigger).

**Expected:**
- Promote consumer logs: "Promote rules → Replay → Build Active batch → (skip post; shadow)"
- DB: Pending items matched by new rules should reduce

### 3.2 Verify DB Changes
```sql
-- Active rules present:
SELECT count(*) FROM app.rules_active;

-- Pending decreased for the promoted company:
SELECT company_id, count(*) 
FROM app.pending_txns
WHERE status='open' 
GROUP BY company_id;
```

### 3.3 Enable Active Posting
```bash
# Restart promote consumer with:
export KYLO_SHEETS_POST=1
python -m services.bus.kafka_consumer_promote
```

Re-run "Promote Rules → Publish" in n8n.

**Expected:**
- `{CID} Active` tab rebuilt (rows 2..end cleared, then appended)
- `sheet_posts` gets new row for Active tab

### 3.4 Verify Active Tab
```sql
SELECT company_id, tab_name, row_count, created_at
FROM control.sheet_posts
WHERE tab_name LIKE '%Active%'
ORDER BY created_at DESC
LIMIT 5;
```

**Pass Criteria:**
- ✅ Active tab shows current rules snapshot
- ✅ `sheet_posts` contains entry for Active with reasonable `row_count`

---

## 4) Ordering & Retry Drills

### 4.1 Per-Company Ordering
```bash
# Send 3 rapid ingests for same company:
for i in {1..3}; do
  curl -X POST http://localhost:5678/webhook/txns.ingest \
    -H "content-type: application/json" \
    -d "{
      \"transactions\": [
        {\"id\":\"t${i}_1\",\"company_id\":\"710\",\"date\":\"2025-08-26\",\"amount\":$i.00,\"description\":\"TEST $i\"}
      ]
    }"
  sleep 1
done
```

**Expected:**
- Consumer logs show three batches for company 710 process in order
- Kafka keying by `company_id` ensures ordering

### 4.2 Retry on Transient Failure
```bash
# Temporarily break Sheets creds (set invalid token)
export GOOGLE_APPLICATION_CREDENTIALS=/invalid/path
# Restart txns consumer
python -m services.bus.kafka_consumer_txns

# Ingest payload (should fail)
curl -X POST http://localhost:5678/webhook/txns.ingest \
  -H "content-type: application/json" \
  -d '{
    "transactions": [
      {"id":"retry_test","company_id":"710","date":"2025-08-26","amount":99.99,"description":"RETRY TEST"}
    ]
  }'

# Restore creds and restart consumer
export GOOGLE_APPLICATION_CREDENTIALS=/correct/path
python -m services.bus.kafka_consumer_txns
```

**Expected:**
- No duplicate posts (signature ensures idempotency)
- After creds fix, batch succeeds; `sheet_posts` shows one record only

**Pass Criteria:**
- ✅ Three sequential batches for one company processed in order
- ✅ Transient failure retried successfully without duplicate posts

---

## 5) Load Sanity (Quick)

### 5.1 Many Small Companies
```bash
# Construct payload with ~10 companies × 3 txns each
curl -X POST http://localhost:5678/webhook/txns.ingest \
  -H "content-type: application/json" \
  -d '{
    "transactions": [
      {"id":"load_1_1","company_id":"710","date":"2025-08-26","amount":1.00,"description":"LOAD TEST 1"},
      {"id":"load_1_2","company_id":"710","date":"2025-08-26","amount":2.00,"description":"LOAD TEST 2"},
      {"id":"load_1_3","company_id":"710","date":"2025-08-26","amount":3.00,"description":"LOAD TEST 3"},
      {"id":"load_2_1","company_id":"711","date":"2025-08-26","amount":4.00,"description":"LOAD TEST 4"},
      {"id":"load_2_2","company_id":"711","date":"2025-08-26","amount":5.00,"description":"LOAD TEST 5"},
      {"id":"load_2_3","company_id":"711","date":"2025-08-26","amount":6.00,"description":"LOAD TEST 6"}
      # ... add more companies as needed
    ]
  }'
```

**Expected:**
- 10 messages produced; consumers process in parallel partitions
- Consumer lag clears quickly

### 5.2 Big Batch Test
```bash
# For one company, post ~2-5k txns
# Generate large payload (example with 1000 txns):
python -c "
import json
txns = []
for i in range(1000):
    txns.append({
        'id': f'big_{i}',
        'company_id': '710',
        'date': '2025-08-26',
        'amount': float(i % 100),
        'description': f'BIG BATCH TXN {i}'
    })
print(json.dumps({'transactions': txns}))
" > big_batch.json

curl -X POST http://localhost:5678/webhook/txns.ingest \
  -H "content-type: application/json" \
  -d @big_batch.json
```

**Expected:**
- One pending `appendCells` in single `batchUpdate` (or small number if chunked)
- Google API response time < 60s typical

**Pass Criteria:**
- ✅ Load sanity (10 small companies) completed; consumer lag cleared
- ✅ Big batch processed within acceptable time limits

---

## 6) Observability Spot Checks

### 6.1 Redpanda Console
Visit http://localhost:8080 → Topics:
- `txns.company.batches`: partitions show low consumer lag
- `rules.promote.requests`: near zero lag after promote

### 6.2 DB Metrics
```sql
-- Latest sheet_posts activity
SELECT company_id, tab_name, row_count, created_at
FROM control.sheet_posts
ORDER BY created_at DESC
LIMIT 10;
```

---

## 7) Rollback Procedure (Fast)

```bash
# 1. Disable n8n workflows (both publish flows)
# 2. Stop consumers (Ctrl+C)
# 3. Set env ROUTE_VIA_KAFKA=0 (if gating upstream publishing)
# 4. Or remove companies from canary list

# Your previous direct path continues; Kafka messages remain retained
```

**Pass:** Rollback drill executed successfully (workflows off, consumers stopped)

---

## 8) Sign-Off Checklist

Copy/paste this section and check off each item:

- [ ] **Shadow ingest** wrote `pending_txns` for multiple companies; no `sheet_posts`
- [ ] **Canary posting** created exactly one `sheet_posts` row; repeated ingest did not create a second row
- [ ] **Promote shadow** updated `rules_active` and reduced open `pending_txns`
- [ ] **Promote posting** rebuilt `{CID} Active` and recorded `sheet_posts`
- [ ] **Three sequential batches** for one company processed in order
- [ ] **Transient failure** retried successfully without duplicate posts
- [ ] **Load sanity** (10 small companies) completed; consumer lag cleared
- [ ] **Rollback drill** executed successfully (workflows off, consumers stopped)

---

## Troubleshooting Notes

### Common Issues
1. **Consumer not starting**: Check `KAFKA_BROKERS` env var and Redpanda health
2. **n8n webhook 404**: Verify workflow is imported and active
3. **Duplicate posts**: Check signature computation and `sheet_posts` dedupe logic
4. **Ordering issues**: Verify Kafka keying by `company_id` in producer

### Log Locations
- Consumer logs: Terminal output
- n8n logs: n8n UI → Executions tab
- Redpanda logs: `docker compose -f docker-compose.kafka.yml logs redpanda`

### Emergency Contacts
- Database: Check `control.sheet_posts` for audit trail
- Kafka: Redpanda Console at http://localhost:8080
- n8n: UI at http://localhost:5678
