# Enhanced Petty Cash System

## Overview

The **Enhanced Petty Cash System** builds on your existing sorter with advanced features for handling missing rules and transaction backlog processing. It maintains your control over rule creation while ensuring zero transaction data loss.

## Key Features

✅ **CSV Transaction Logging** - All missing transactions logged to CSV  
✅ **JGD Truth Source Addition** - New sources added to JGD Truth for visibility  
✅ **Daily Backlog Processing** - Automatically processes transactions once rules exist  
✅ **Alert System** - Notifications for new sources and processing results  
✅ **Zero Data Loss** - Every transaction captured and preserved  
✅ **Complete Control** - You manually create target mappings in JGD Truth  

## System Components

### 1. Enhanced Petty Cash Sorter (`petty_cash_sorter_enhanced.py`)
- **Purpose**: Main sorting script with enhanced logging
- **Features**: 
  - Logs missing transactions to CSV
  - Adds new sources to JGD Truth (Column A only)
  - Generates alerts for new sources
  - Continues processing other transactions

### 2. Daily Backlog Processor (`backlog_processor.py`)
- **Purpose**: Processes pending transactions once rules exist
- **Features**:
  - Checks for completed rules in JGD Truth
  - Processes eligible transactions
  - Updates CSV status files
  - Generates processing alerts

### 3. CSV Management System
- **Pending Transactions**: `pending_transactions/pending_transactions.csv`
- **Processed Transactions**: `pending_transactions/processed_transactions.csv`
- **Failed Transactions**: `pending_transactions/failed_transactions.csv`
- **Alerts**: `pending_transactions/alerts.txt`

## File Structure

```
PettyCash/
├── petty_cash_sorter_enhanced.py      # Enhanced main sorter
├── backlog_processor.py               # Daily backlog processor
├── run_enhanced_sorter.bat            # Run enhanced sorter
├── run_backlog_processor.bat          # Run backlog processor
├── pending_transactions/
│   ├── pending_transactions.csv       # Transactions waiting for rules
│   ├── processed_transactions.csv     # Successfully processed
│   ├── failed_transactions.csv        # Failed attempts
│   └── alerts.txt                     # System alerts
└── logs/
    ├── enhanced_sorter.log            # Enhanced sorter logs
    └── backlog_processor.log          # Backlog processor logs
```

## Workflow

### Phase 1: Transaction Processing
```
Main Sorter → Find New Source → Add to JGD Truth → Log to CSV → Skip Processing
```

**What happens:**
1. Enhanced sorter finds transaction with missing rule
2. Adds source name to JGD Truth (Column A only)
3. Logs complete transaction details to CSV
4. Skips processing, continues with other transactions
5. Generates alert for new source

### Phase 2: Manual Rule Creation
```
Review JGD Truth → Create Target Mapping → Complete Rule
```

**What you do:**
1. See new source in JGD Truth (Column A)
2. Add target sheet (Column B)
3. Add target header (Column C)
4. Rule is now complete

### Phase 3: Backlog Processing
```
Daily Processor → Check Rules → Process Eligible → Update Status
```

**What happens:**
1. Daily processor reads pending CSV
2. Checks for completed rules in JGD Truth
3. Processes transactions with complete rules
4. Updates CSV status files
5. Generates processing alerts

## CSV Format

### Pending Transactions
```csv
transaction_id,timestamp,source,company,date,amount,initials,row,jgd_truth_row,status,created_date
TXN_A1B2C3D4,2025-01-15T10:30:00,NEW GAS STATION,NUGZ,1/15/25,45.00,JD,1234,NUGZ_45,pending_rule,2025-01-15
```

### Processed Transactions
```csv
transaction_id,timestamp,source,company,date,amount,initials,row,jgd_truth_row,status,processed_date,target_sheet,target_header
TXN_A1B2C3D4,2025-01-15T10:30:00,NEW GAS STATION,NUGZ,1/15/25,45.00,JD,1234,NUGZ_45,processed,2025-01-16,NUGZ EXPENSES,FUEL
```

## Usage

### Running the Enhanced Sorter
```bash
run_enhanced_sorter.bat
```

**What it does:**
- Processes all transactions
- Adds new sources to JGD Truth
- Logs missing transactions to CSV
- Generates alerts for new sources

### Running the Backlog Processor
```bash
run_backlog_processor.bat
```

**What it does:**
- Reads pending transactions from CSV
- Checks for completed rules in JGD Truth
- Processes eligible transactions
- Updates status files
- Generates processing alerts

### Manual Processing
```bash
# Run enhanced sorter once
python petty_cash_sorter_enhanced.py

# Run backlog processor once
python backlog_processor.py
```

## Alert System

### Alert Types
- **NEW_SOURCES**: When new sources are found
- **PROCESSING_COMPLETE**: When main sorter completes
- **BACKLOG_EMPTY**: When no pending transactions
- **BACKLOG_PROCESSING_COMPLETE**: Daily processing summary
- **BACKLOG_PROCESSING_ERROR**: Processing errors

### Alert Format
```
[2025-01-15 10:30:00] NEW_SOURCES: Found 3 new sources needing rules: NEW GAS STATION, UNKNOWN SUPPLIER, and 1 more
[2025-01-15 10:35:00] PROCESSING_COMPLETE: Processed 150 transactions, 3 pending rules
```

## Benefits

### 1. Zero Data Loss
- Every transaction captured in CSV
- Complete transaction details preserved
- No transactions overlooked

### 2. Complete Control
- You decide when to create rules
- You control target mappings
- No automatic rule creation

### 3. Clear Visibility
- See new sources in JGD Truth immediately
- Know exactly what needs rules
- Track processing status

### 4. Automated Processing
- Daily backlog processing
- Automatic status updates
- Batch processing efficiency

### 5. Comprehensive Tracking
- Transaction IDs for tracking
- Processing timestamps
- Error handling and reporting

## Configuration

### Modify Alert Thresholds
Edit the alert creation in the scripts:
```python
# Create alert for high backlog
if len(pending_transactions) > 50:
    self.create_alert("high_backlog", f"{len(pending_transactions)} pending transactions")
```

### Change Processing Frequency
The backlog processor can be scheduled:
- **Daily**: Run `run_backlog_processor.bat` daily
- **Weekly**: Run manually when needed
- **On-demand**: Run after creating rules

### Custom CSV Fields
Add additional fields to CSV format:
```python
# Add custom fields
pending_data['custom_field'] = 'custom_value'
```

## Troubleshooting

### Common Issues

1. **No Pending Transactions Found**
   - Check if `pending_transactions.csv` exists
   - Verify CSV format and headers
   - Check file permissions

2. **Rules Not Found**
   - Ensure JGD Truth Excel file is up to date
   - Check company tab names match exactly
   - Verify source names match exactly

3. **Processing Errors**
   - Check Google Sheets API permissions
   - Verify target sheet names exist
   - Check date formats in target sheets

### Manual Recovery

1. **Clear Pending Transactions**
   ```bash
   # Backup and clear pending CSV
   copy pending_transactions\pending_transactions.csv pending_transactions\backup.csv
   echo transaction_id,timestamp,source,company,date,amount,initials,row,jgd_truth_row,status,created_date > pending_transactions\pending_transactions.csv
   ```

2. **Reprocess Failed Transactions**
   ```bash
   # Move failed transactions back to pending
   copy pending_transactions\failed_transactions.csv pending_transactions\pending_transactions.csv
   ```

3. **Check Alert Log**
   ```bash
   # View recent alerts
   type pending_transactions\alerts.txt
   ```

## Next Steps

1. **Test the System**: Run enhanced sorter to see CSV logging in action
2. **Create Rules**: Add target mappings to JGD Truth for new sources
3. **Process Backlog**: Run backlog processor to handle pending transactions
4. **Schedule Processing**: Set up daily backlog processing
5. **Monitor Alerts**: Check alert file for system status

This enhanced system gives you complete control while ensuring no transaction data is lost and providing automated processing once rules exist! 