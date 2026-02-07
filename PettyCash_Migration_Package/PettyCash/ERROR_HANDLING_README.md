# Enhanced Error Handling for Petty Cash Sorter

## Overview

The enhanced petty cash sorter now includes comprehensive error handling to track, log, and recover from failed cell inputs in Google Sheets. This system ensures that no transactions are lost and provides multiple recovery mechanisms.

## How Failed Cell Inputs Are Tracked

### 1. **Failed Transaction Logging**

When a cell input fails, the system automatically logs the failed transaction to `pending_transactions/Petty Cash Failed.csv` with detailed information:

- **Transaction Details**: Row, Date, Initials, Source, Company, Amount
- **Error Information**: Specific error message and timestamp
- **Target Cell Info**: Which cell was being updated when the failure occurred
- **Status Tracking**: Failed vs Processed status

### 2. **Error Types Tracked**

The system tracks various types of failures:

- **Sheet Not Found**: Target worksheet doesn't exist in Google Sheets
- **Batch Update Failures**: Google Sheets API errors during batch operations
- **Cell Reading Errors**: Issues reading current cell values
- **Rule Matching Failures**: No matching rules found for transactions
- **Coordinate Resolution Failures**: Can't find target cell coordinates

### 3. **Automatic Error Detection**

The system detects failures at multiple levels:

```python
# Individual cell failures
try:
    current_cell = worksheet.cell(row, col)
    # ... process cell
except Exception as e:
    self.log_failed_transaction(transaction, f"Cell read error: {e}")

# Batch update failures
try:
    result = spreadsheet.batch_update(body)
except Exception as e:
    # Log all transactions in the batch as failed
    for transaction in cell_transaction_map.values():
        self.log_failed_transaction(transaction, f"Batch update failed: {e}")
```

## Recovery Mechanisms

### 1. **Automatic Retry System**

The system includes an automatic retry mechanism that:

- **Retries Failed Transactions**: Up to 3 attempts with 5-second delays
- **Groups by Error Type**: Processes similar errors together
- **Individual Processing**: Tries each failed transaction individually
- **Success Tracking**: Marks successfully processed transactions

### 2. **Manual Recovery Options**

Users can manually trigger recovery processes:

#### **Option 3: Retry Failed Transactions**
```bash
# Run the retry process
run_retry_failed.bat
```

#### **Option 4: Generate Failure Report**
```bash
# Generate detailed failure report
generate_failure_report.bat
```

### 3. **Recovery Process Flow**

1. **Read Failed CSV**: Load all failed transactions
2. **Group by Error**: Organize by error type for efficient processing
3. **Retry Logic**: Attempt processing with exponential backoff
4. **Success Tracking**: Mark successful transactions as processed
5. **Report Generation**: Create detailed success/failure summary

## File Structure

### **Failed Transactions CSV**
```
pending_transactions/Petty Cash Failed.csv
├── Row: Original row number
├── Date: Transaction date
├── Initials: User initials
├── Source: Transaction source
├── Company: Company name
├── Amount: Transaction amount
├── Status: 'failed' or 'processed'
├── Error_Message: Specific error details
├── Failed_Date: When the failure occurred
└── Cell_Info: Target cell information
```

### **Failure Report**
```
pending_transactions/failure_report.txt
├── Summary statistics
├── Error type groupings
├── Transaction details
└── Recovery recommendations
```

## Usage Examples

### **Running with Error Handling**

1. **Normal Operation**: The system automatically handles errors
   ```bash
   run_enhanced_final_sorter.bat
   # Choose option 2 for live update
   ```

2. **Manual Retry**: Retry failed transactions
   ```bash
   run_enhanced_final_sorter.bat
   # Choose option 3 for retry
   ```

3. **Generate Report**: View detailed failure information
   ```bash
   run_enhanced_final_sorter.bat
   # Choose option 4 for report
   ```

### **Monitoring Failed Transactions**

```python
from petty_cash_sorter_final import FinalPettyCashSorter

sorter = FinalPettyCashSorter()

# Check for failed transactions
report = sorter.generate_failure_report()
print(report)

# Retry failed transactions
sorter.retry_failed_cells(max_retries=3, retry_delay=5)
```

## Error Resolution Strategies

### **Common Error Types and Solutions**

1. **"Target sheet not found"**
   - **Cause**: Worksheet doesn't exist in Google Sheets
   - **Solution**: Verify sheet names in JGD Truth file

2. **"Batch update failed"**
   - **Cause**: Google Sheets API quota or permission issues
   - **Solution**: Wait and retry, check API credentials

3. **"No rule found"**
   - **Cause**: Missing mapping rule in JGD Truth
   - **Solution**: Add rule to JGD Truth file

4. **"No target cell found"**
   - **Cause**: Date or header not found in target sheet
   - **Solution**: Verify date format and header names

### **Prevention Strategies**

1. **Regular Monitoring**: Check failure reports regularly
2. **Rule Maintenance**: Keep JGD Truth rules updated
3. **API Quota Management**: Monitor Google Sheets API usage
4. **Data Validation**: Verify source data quality

## Integration with Main Process

The error handling is fully integrated into the main sorting process:

1. **Step 1-4**: Normal processing with automatic error logging
2. **Step 5**: Automatic retry of failed transactions
3. **Step 6**: Final summary with failure statistics

This ensures that the system is resilient and self-healing, automatically recovering from most transient errors while providing detailed reporting for manual intervention when needed. 