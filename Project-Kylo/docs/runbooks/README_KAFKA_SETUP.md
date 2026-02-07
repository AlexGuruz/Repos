# Kafka Event Bus - Quick Start Guide

This guide provides a quick overview of the Kafka event-bus architecture implementation for Kylo.

## 🚀 Quick Start (Windows)

### 1. Start Infrastructure
```powershell
# Start Kafka (Redpanda)
docker compose -f docker-compose.kafka.yml up -d

# Create topics
.\scripts\active\kafka_topics.ps1
```

### 2. Setup Database
```powershell
# Apply schema updates
psql "$env:PG_DSN_RW" -f db/ddl/0014_control_sheet_posts_unique.sql

# Seed company config (update placeholders first)
# See docs/KAFKA_EVENT_BUS_RUNBOOK_WINDOWS.md for SQL
```

### 3. Install Dependencies
```powershell
pip install -r requirements-kafka.txt
```

### 4. Start Consumers (Shadow Mode)
```powershell
.\scripts\active\start_kafka_consumers.ps1 -SheetsPost "0"
```

### 5. Configure n8n
- Import workflows: `workflows/n8n/n8n_ingest_publish_kafka.json` and `workflows/n8n/n8n_promote_publish_kafka.json`
- Configure credentials: "Kylo Postgres RW" and "Redpanda Dev"
- Enable "Ingest → Publish (Kafka)" workflow

### 6. Test
```powershell
.\tools\debug\test_ingest_flow.ps1
```

## 📁 File Structure

```
├── .env                                    # Environment configuration
├── docker-compose.kafka.yml               # Redpanda infrastructure
├── db/ddl/0014_control_sheet_posts_unique.sql  # Database schema
├── services/bus/
│   ├── __init__.py
│   ├── schema.py                          # Message schemas
│   ├── kafka_consumer_txns.py             # Transaction consumer
│   └── kafka_consumer_promote.py          # Promote consumer
├── workflows/
│   └── n8n/
│       ├── n8n_ingest_publish_kafka.json          # Ingest workflow
│       └── n8n_promote_publish_kafka.json         # Promote workflow
├── scripts/
│   ├── kafka_topics.ps1                   # Topic creation (Windows)
│   └── start_kafka_consumers.ps1          # Consumer startup (Windows)
├── tools/
│   └── debug/
│       └── test_ingest_flow.ps1           # Test script (Windows)
├── requirements-kafka.txt                  # Python dependencies
└── docs/
    ├── KAFKA_EVENT_BUS_RUNBOOK.md         # Linux/Mac guide
    └── KAFKA_EVENT_BUS_RUNBOOK_WINDOWS.md # Windows guide
```

## 🔄 Event Flow

### Ingest Flow (Pending)
1. **Webhook** → `workflows/n8n/n8n_ingest_publish_kafka.json`
2. **Group by Company** → Lookup config → Build message
3. **Kafka Produce** → `txns.company.batches` topic
4. **Consumer** → Mover → Triage → Sheets (Pending tab)

### Promote Flow (Active)
1. **Manual Trigger** → `workflows/n8n/n8n_promote_publish_kafka.json`
2. **List Companies** → Build promote messages
3. **Kafka Produce** → `rules.promote.requests` topic
4. **Consumer** → Rules Promote → Replay → Sheets (Active tab)

## 🛡️ Safety Features

- **Idempotent**: All operations are idempotent
- **Deduplication**: Composite unique constraint on `sheet_posts`
- **Shadow Mode**: `KYLO_SHEETS_POST=0` for testing without Sheets writes
- **Reversible**: Direct path remains intact during transition
- **Batch-First**: All Sheets operations use batchUpdate

## 📊 Monitoring

- **Redpanda Console**: http://localhost:8080
- **Consumer Logs**: Monitor Python processes
- **Database**: Check `control.sheet_posts` for deduplication

## 🔧 Configuration

Key environment variables in `.env`:
```bash
ROUTE_VIA_KAFKA=1
KAFKA_BROKERS=localhost:9092
KAFKA_TOPIC_TXNS=txns.company.batches
KAFKA_TOPIC_PROMOTE=rules.promote.requests
KYLO_SHEETS_POST=0  # Set to 1 to enable Sheets posting
```

## 📚 Documentation

- **Windows Guide**: `docs/KAFKA_EVENT_BUS_RUNBOOK_WINDOWS.md`
- **Linux/Mac Guide**: `docs/KAFKA_EVENT_BUS_RUNBOOK.md`
- **Architecture**: See original plan in user query

## 🚨 Troubleshooting

### Common Issues
1. **Redpanda not running**: `docker ps | findstr redpanda`
2. **Consumers not starting**: Check Python dependencies
3. **n8n connection errors**: Verify credentials configuration
4. **PowerShell execution policy**: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### Rollback
```powershell
# Stop consumers
Get-Process python | Stop-Process

# Disable n8n workflows
# Direct path remains intact
```

## 🎯 Next Steps

1. **Test Shadow Mode**: Verify processing without Sheets writes
2. **Enable Sheets Posting**: Set `KYLO_SHEETS_POST=1`
3. **Test Duplicate Safety**: Re-send same payload
4. **Test Promote Flow**: Execute promote workflow
5. **Monitor & Scale**: Add monitoring, scale consumers for production
