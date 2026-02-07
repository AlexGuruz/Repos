#!/usr/bin/env bash
set -euo pipefail

# Test the ingest flow with sample transaction data

N8N_URL=${N8N_URL:-http://localhost:5678}

echo "Testing ingest flow..."
echo "n8n URL: $N8N_URL"
echo ""

# Sample transaction data
cat > /tmp/test_transactions.json << 'EOF'
{
  "transactions": [
    {"id":"t1","company_id":"710","date":"2025-08-26","amount":-12.34,"description":"STARBUCKS"},
    {"id":"t2","company_id":"711","date":"2025-08-26","amount":45.67,"description":"WALMART"},
    {"id":"t3","company_id":"710","date":"2025-08-26","amount":10.00,"description":"UNKNOWN"},
    {"id":"t4","company_id":"711","date":"2025-08-26","amount":-25.50,"description":"AMAZON"},
    {"id":"t5","company_id":"710","date":"2025-08-27","amount":100.00,"description":"DEPOSIT"}
  ],
  "batch_id": "test-batch-$(date +%s)",
  "ingest_batch_id": $(date +%s)
}
EOF

echo "Sending test transactions..."
curl -X POST "$N8N_URL/webhook/txns.ingest" \
  -H "content-type: application/json" \
  -d @/tmp/test_transactions.json

echo ""
echo "Test completed. Check consumer logs for processing."
echo ""

# Cleanup
rm -f /tmp/test_transactions.json
