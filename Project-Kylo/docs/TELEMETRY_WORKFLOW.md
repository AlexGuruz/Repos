# Kylo Telemetry Workflow - Complete System Integration

## Overview

The Kylo Telemetry Workflow is a comprehensive n8n-based visualization system that provides real-time monitoring of the entire Kylo data processing pipeline. It integrates all three core services (Importer, Mover, Poster) and provides detailed telemetry for every step of the data flow from Excel files to Google Sheets.

## Architecture

### Complete System Flow
```
Excel Files → Importer → Database Rules → Mover → Company DBs → Poster → Google Sheets
     ↓           ↓           ↓           ↓         ↓           ↓         ↓
  Telemetry → Telemetry → Telemetry → Telemetry → Telemetry → Telemetry → Telemetry
     ↓           ↓           ↓           ↓         ↓           ↓         ↓
  n8n Webhook → Event Logger → Service Routing → Processing → Response → Real-time Display
```

### Components
1. **Telemetry Emitter** (`telemetry/emitter.py`) - Sends events to n8n
2. **n8n Workflow** (`workflows/n8n/n8n_telemetry_workflow.json`) - Processes and routes events
3. **Service Lanes** - Separate processing paths for each service type
4. **Event Logger** - Centralized event logging and summary
5. **Workflow Summary** - System status and event tracking

## Complete Event Coverage

### 1. Importer Events (Rule Processing Pipeline)
- **Purpose**: Track rule processing from Excel files to database
- **Events**:
  - `validation_started` - Rule validation begins
  - `validation_completed` - Validation results
  - `duplicates_found` - Duplicate rules detected
  - `file_loaded` - Excel file loaded and parsed
  - `rules_promoted` - Rules promoted from pending to active
  - `active_updated` - Active rules sheet updated

### 2. Mover Events (Data Movement Pipeline)
- **Purpose**: Track data movement from global to company databases
- **Events**:
  - `batch_fetched` - Batch data fetched from global DB
  - `company_processing_started` - Company-specific processing begins
  - `upsert_started` - Database upsert operation begins
  - `transaction_processed` - Individual transactions processed
  - `rows_enqueued` - Rows processed and enqueued for sorting
  - `watermark_advanced` - Company feed watermark updated
  - `company_processing_completed` - Company processing finished

### 3. Poster Events (Sheets Update Pipeline)
- **Purpose**: Track Google Sheets updates and projections
- **Events**:
  - `sheets_connected` - Connection to Google Sheets established
  - `projection_calculated` - Data projections computed
  - `batch_update_built` - Sheets batch update prepared
  - `batch_update_sent` - Batch update sent to Google Sheets
  - `sheets_response_received` - Response from Sheets API
  - `cells_updated` - Individual cells updated

## Setup Instructions

### 1. Import the Workflow
1. Open n8n at http://localhost:5678
2. Click "Import from file"
3. Select `workflows/n8n/n8n_telemetry_workflow.json`
4. The workflow will be imported as "Kylo Telemetry Visualizer"

### 2. Activate the Workflow
1. Click on the imported workflow
2. Click the toggle switch in the top-right corner
3. The webhook will be registered at `/webhook/kylo-telemetry`

### 3. Configure Environment Variables
Set these environment variables in your Kylo services:
```bash
export TELEMETRY_SINK="http"
export N8N_WEBHOOK_URL="http://localhost:5678/webhook/kylo-telemetry"
```

## Workflow Structure

### Webhook Node
- **Path**: `/webhook/kylo-telemetry`
- **Method**: POST
- **Receives**: JSON telemetry events from all Kylo services

### Event Processing Flow
1. **Event Logger** - Centralized event logging and timestamp conversion
2. **Service Routing** - Routes events to appropriate service lanes
3. **Service Processors** - Transform and enrich events for each service
4. **Response Nodes** - Return structured JSON responses
5. **Workflow Summary** - System status and event tracking

### Service-Specific Processing
Each service lane has specialized processing:
- **Importer Lane**: Rule validation, promotion, and sheet updates
- **Mover Lane**: Database operations, batch processing, watermarks
- **Poster Lane**: Sheets operations, projections, API responses

## Event Format

### Input Event (from Kylo services)
```json
{
  "ts": 1704067200.123,
  "level": "info",
  "trace_id": "1704067200-abc12345-test-company-mover",
  "event_type": "mover",
  "step": "upsert_started",
  "payload": {
    "company_id": "test-company",
    "batch_size": 1250,
    "batch_id": 20250101,
    "temp_table": "stg_txn_created"
  }
}
```

### Output Response (from n8n)
```json
{
  "trace_id": "abc12345-test-company",
  "event_type": "mover",
  "step": "🔄 PG: Upsert Started",
  "company_id": "test-company",
  "batch_size": 1250,
  "enqueued": 0,
  "inserted": 0,
  "updated": 0,
  "batch_id": 20250101,
  "watermark_updated": false,
  "lane": "mover",
  "timestamp": "2024-01-01T12:00:00.123Z",
  "message": "Mover event processed"
}
```

## Testing

### Run the Complete Test Script
```bash
python tools/tests_manual/test_telemetry_workflow.py
```

This script sends a comprehensive set of test events for multiple companies, demonstrating the complete Kylo system workflow including:
- **Importer**: 6 events covering validation, promotion, and updates
- **Mover**: 7 events covering batch processing and database operations
- **Poster**: 6 events covering Sheets operations and API responses

### Manual Testing
You can also test individual events:
```python
from telemetry.emitter import emit, start_trace

trace = start_trace("mover", "test-company")
emit("mover", trace, "upsert_started", {
    "company_id": "test-company",
    "batch_size": 100,
    "batch_id": 20250101
})
```

## Real-time Monitoring

### Visual Workflow Display
- Open n8n at http://localhost:5678
- Navigate to the "Kylo Telemetry Visualizer" workflow
- Watch events flow through the different service lanes in real-time
- See emoji-enhanced step descriptions for easy identification

### Event Tracking Features
Each event includes:
- **Trace ID**: Shortened unique identifier for tracking related events
- **Company ID**: Which company the event relates to
- **Step**: Emoji-enhanced description of the operation
- **Timestamps**: ISO format timestamps
- **Service-specific Metrics**: Relevant counts and measurements
- **Lane Information**: Which service processed the event

### Service-Specific Information
- **Importer Lane**: Rule counts, validation results, version numbers
- **Mover Lane**: Batch sizes, database operations, watermark status
- **Poster Lane**: Sheets operations, API response times, update counts

## System Integration

### Mover Service Integration
The mover service automatically emits events during batch processing:
- `batch_fetched` when fetching data from global database
- `company_processing_started/completed` for company-specific operations
- `upsert_started` when beginning database operations
- `transaction_processed` for individual transaction processing
- `rows_enqueued` when transactions are processed and enqueued
- `watermark_advanced` when company feeds are updated

### Poster Service Integration
The poster service emits events during Sheets operations:
- `sheets_connected` when establishing connection
- `projection_calculated` when computing data projections
- `batch_update_built` when preparing updates
- `batch_update_sent` when sending to Google Sheets
- `sheets_response_received` when receiving API responses
- `cells_updated` when individual cells are updated

### Importer Service Integration
The importer service can be enhanced to emit events during rule processing:
- `validation_started/completed` for rule validation
- `duplicates_found` for duplicate detection
- `file_loaded` when Excel files are processed
- `rules_promoted` when rules are promoted to active
- `active_updated` when active sheets are updated

## Advanced Features

### Event Correlation
- **Trace IDs**: Link related events across services
- **Company Context**: Track all events for a specific company
- **Batch Tracking**: Follow batch processing through the entire pipeline

### Performance Monitoring
- **Response Times**: Track API response times
- **Processing Durations**: Monitor operation durations
- **Throughput Metrics**: Track batch sizes and processing rates

### Error Tracking
- **Validation Errors**: Track rule validation issues
- **API Failures**: Monitor Sheets API responses
- **Database Issues**: Track database operation status

## Troubleshooting

### Webhook Not Receiving Events
1. Check that the workflow is activated in n8n
2. Verify the webhook URL is correct
3. Check n8n logs for errors

### Events Not Appearing
1. Verify `TELEMETRY_SINK="http"` is set
2. Check `N8N_WEBHOOK_URL` is correct
3. Look for network connectivity issues

### Workflow Errors
1. Check n8n logs for detailed error messages
2. Verify the workflow JSON is valid
3. Restart the n8n container if needed

### Service-Specific Issues
- **Importer**: Check rule validation and promotion logic
- **Mover**: Verify database connections and batch processing
- **Poster**: Monitor Sheets API authentication and responses

## Future Enhancements

### Potential Additions
1. **Dashboard Integration**: Connect to external dashboards (Grafana, etc.)
2. **Alerting**: Set up alerts for failed operations or performance issues
3. **Metrics Aggregation**: Collect performance metrics over time
4. **Historical Analysis**: Store events for trend analysis
5. **Company-specific Views**: Filter by company ID for focused monitoring

### Advanced Features
1. **Event Correlation**: Enhanced linking of related events across services
2. **Performance Monitoring**: Advanced performance tracking and alerting
3. **Error Tracking**: Comprehensive error monitoring and alerting
4. **Capacity Planning**: Analyze throughput patterns for capacity planning
5. **Real-time Analytics**: Live analytics and reporting

## File Structure

```
├── workflows/
│   └── n8n/
│       └── n8n_telemetry_workflow.json    # Complete n8n workflow
├── tools/
│   └── tests_manual/
│       └── test_telemetry_workflow.py     # Comprehensive test script
├── telemetry/
│   └── emitter.py                 # Telemetry emission library
└── docs/
    └── TELEMETRY_WORKFLOW.md      # This documentation
```

## Support

For issues or questions about the telemetry workflow:
1. Check the n8n logs for error messages
2. Verify environment variables are set correctly
3. Test with the provided test script
4. Review this documentation for setup instructions
5. Check service-specific logs for detailed error information
