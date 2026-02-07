# FINAL PETTY CASH SORTER

## Overview

The **Final Petty Cash Sorter** is a bulletproof system that processes transactions from the "PETTY CASH" sheet and automatically sorts them into target sheets based on rules from the "JGD Truth" spreadsheet. It uses the actual Excel files as the source of truth, eliminating all API calls and assumptions.

## Key Features

✅ **Uses Real Excel Files** - No API calls, no assumptions, works directly with your actual data  
✅ **Auto-Fixes Missing Rules** - Creates rules for sources not found in JGD Truth  
✅ **Auto-Creates Missing Dates** - Adds missing date rows to target sheets  
✅ **Comprehensive Logging** - Detailed logs of all operations  
✅ **Dry Run Mode** - Test before making actual changes  
✅ **Error Handling** - Graceful handling of missing data  

## Files Required

- `JGDTruth.xlsx` - Contains the mapping rules (NUGZ, JGD, PUFFIN sheets)
- `2025 JGD FINANCIALS (3).xlsx` - Contains PETTY CASH and target sheets

## How It Works

### 1. Rule Loading
- Reads rules from JGD Truth Excel file
- Maps sources to target sheets and headers
- Handles NUGZ, JGD, and PUFFIN rule sets

### 2. Header Mapping
- Loads headers from all target sheets (row 19)
- Loads PETTY CASH headers (row 4)
- Maps transaction sources to target columns

### 3. Transaction Processing
- Reads PETTY CASH transactions (starting row 5)
- Finds matching rules for each source
- Creates missing rules automatically if needed
- Finds or creates target date rows
- Updates target cells with transaction amounts

### 4. Auto-Fix Logic

**Missing Rules:**
- SALE transactions → INCOME / (N) WHOLESALE
- REG transactions → INCOME / REGISTERS  
- SQUARE transactions → INCOME / SQUARE
- RETURN transactions → INCOME / STONED PROJECT
- Company-specific → Respective C.O.G. / MISC.

**Missing Dates:**
- Automatically creates date rows in target sheets
- Adds proper Excel formulas for date progression

## Usage

### Quick Start
```bash
# Run the batch file
run_final_sorter.bat

# Or run directly
python petty_cash_sorter_final.py
```

### Process Flow
1. **Dry Run** - System processes all transactions and shows what would be updated
2. **Review** - Check the logs and results
3. **Live Run** - Confirm to perform actual updates

## File Structure

```
PettyCash/
├── petty_cash_sorter_final.py    # Main sorter script
├── run_final_sorter.bat          # Easy run script
├── JGDTruth.xlsx                 # Rule definitions
├── 2025 JGD FINANCIALS (3).xlsx  # Data files
├── logs/
│   └── final_sorter.log         # Detailed logs
└── FINAL_SORTER_README.md       # This file
```

## Logging

The system creates detailed logs in `logs/final_sorter.log` including:
- Rules loaded from JGD Truth
- Headers found in target sheets
- Transactions processed
- Missing rules created
- Missing dates created
- All errors and warnings

## Error Handling

The system handles common issues:
- **Missing rules** - Creates them automatically
- **Incomplete rules** - Fills in missing target sheet/header
- **Missing dates** - Creates date rows in target sheets
- **Invalid data** - Logs warnings and continues processing

## Example Output

```
FINAL PETTY CASH SORTER
============================================================

RUNNING DRY RUN FIRST...
Loaded 1,234 rules from JGD Truth
Loaded headers for 25 target sheets
Loaded 18 PETTY CASH headers
Creating missing rule for source 'SALE TO LAUGHING HYENA'
Creating missing date 2025-01-01 in sheet 'INCOME'
Would update INCOME row 25 col 8 for 'SALE TO LAUGHING HYENA' -> '(N) WHOLESALE'
Processed 1,567 transactions, 0 errors
Missing rules created: 23
Missing dates created: 45

No errors found! Ready for live run.
```

## Safety Features

- **Dry run by default** - Always test first
- **Backup recommendation** - Back up your Excel files before running
- **Detailed logging** - Full audit trail of all changes
- **Error recovery** - Continues processing even with individual transaction errors

## What Gets Updated

The system updates target cells by:
1. Finding the correct target sheet and column
2. Finding or creating the correct date row
3. Adding the transaction amount to the existing cell value
4. Saving the updated Excel file

## Troubleshooting

**Common Issues:**
- Missing Excel files → Check file names and locations
- Permission errors → Close Excel files before running
- Memory issues → Process in smaller batches if needed

**Check Logs:**
- Review `logs/final_sorter.log` for detailed information
- Look for warnings and errors
- Verify rule mappings and target cells

## Success Criteria

The system is working correctly when:
- ✅ All transactions are processed
- ✅ No critical errors in logs
- ✅ Target cells are updated with correct amounts
- ✅ Missing rules and dates are created automatically

---

**Built with ❤️ to handle your petty cash sorting needs automatically!** 