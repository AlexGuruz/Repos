# Worksheet Architecture and Protocols

## Overview

The Kylo Remodel system uses a **strict two-workbook architecture** to separate rule management from transaction processing. This document outlines the protocols, naming conventions, and operational guidelines.

## Workbook Architecture

### 1. Rules Management Workbook
- **Spreadsheet ID:** `1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec`
- **Purpose:** Centralized rule management for all companies
- **Access:** All rule management operations target this workbook exclusively
- **Content:** Pending and Active rule tabs for all configured companies

### 2. Company Transaction Workbooks
- **Purpose:** Company-specific transaction processing and financial data
- **Configuration:** Defined in `config/companies.json` under `workbook` field
- **Content:** Transaction sheets (PETTY CASH, BALANCE, PAYROLL, etc.)
- **Access:** Transaction processing operations only

## Tab Naming Conventions

### Rules Management Tabs (Rules Management Workbook)
```
"{CID} Pending"    # e.g., "NUGZ Pending"
"{CID} Active"     # e.g., "NUGZ Active"
```

### Transaction Processing Tabs (Company Transaction Workbooks)
```
PETTY CASH
BALANCE
PAYROLL
EXPENSES
# ... other company-specific transaction sheets
```

## Tab Specifications

### Pending Tab Structure
**Headers (Row 1, frozen):**
```
Row_Hash | Date | Source | Company_ID | Amount | Target_Sheet | Target_Header | Match_Notes | Approved | Rule_ID | Processed_At
```

**Column Details:**
- **Row_Hash (A):** System-managed, protected column
- **Date (B):** Transaction date
- **Source (C):** Transaction description/source
- **Company_ID (D):** Fixed to company ID, data validation enforced
- **Amount (E):** Transaction amount
- **Target_Sheet (F):** Target transaction sheet name
- **Target_Header (G):** Target column header
- **Match_Notes (H):** Matching notes/comments
- **Approved (I):** Data validation (TRUE/FALSE), strict
- **Rule_ID (J):** System-assigned rule ID
- **Processed_At (K):** System-managed, protected column

### Active Tab Structure
**Headers (Row 1, frozen):**
```
Ruleset_Version | Effective_At | Company_ID | Source | Target_Sheet | Target_Header | Match_Notes | Created_At
```

**Column Details:**
- **Ruleset_Version (A):** Version identifier
- **Effective_At (B):** When rule becomes effective
- **Company_ID (C):** Company identifier
- **Source (D):** Rule source pattern
- **Target_Sheet (E):** Target transaction sheet
- **Target_Header (F):** Target column header
- **Match_Notes (G):** Matching notes
- **Created_At (H):** Rule creation timestamp

**Protection:** Entire tab is system-protected (read-only)

## Operational Protocols

### Rules Management Operations
- **Target Workbook:** Rules Management Workbook only
- **Method:** batchUpdate only, no single-cell writes
- **Deduplication:** Via `control.sheet_posts.batch_signature`
- **Tab Creation:** Automatic via `ensure_company_tabs()`
- **Services:** `services/rules_promoter/service.py`, `services/bus/kafka_consumer_promote.py`

### Transaction Processing Operations
- **Target Workbook:** Company Transaction Workbooks only
- **Method:** batchUpdate only, no single-cell writes
- **Deduplication:** Via `control.sheet_posts.batch_signature`
- **Target:** Specific `target_header` columns within transaction tabs
- **Services:** `services/sheets/poster.py`

## Strict Separation Rules

⚠️ **CRITICAL PROTOCOLS:**

1. **No Cross-Contamination**
   - Rules management operations NEVER target company transaction workbooks
   - Transaction processing operations NEVER target the rules management workbook
   - Each workbook type serves exactly one purpose

2. **Service Responsibilities**
   - **Rules Promoter:** Only operates on Rules Management Workbook
   - **Sheets Poster:** Only operates on Company Transaction Workbooks
   - **Kafka Consumer:** Only operates on Rules Management Workbook for rule operations

3. **Configuration Management**
   - Rules Management Workbook ID is hardcoded in services
   - Company Transaction Workbook IDs come from `config/companies.json`
   - No dynamic switching between workbook types

## Migration and Cleanup

### Legacy Tab Cleanup
- **Delete:** Any rule management tabs in company transaction workbooks
- **Reason:** These were incorrectly created due to configuration errors
- **Safe to delete:** These tabs contain no essential data

### Naming Convention Migration
- **Old Convention:** `"Pending Rules – {CID}"`, `"Active Rules – {CID}"` (DEPRECATED)
- **New Convention:** `"{CID} Pending"`, `"{CID} Active"` (CURRENT)
- **Status:** All services updated to use new convention

## Validation and Monitoring

### Automated Checks
- **Tab Naming:** All services validate tab names match expected conventions
- **Workbook Targeting:** Services verify they're operating on correct workbook type
- **Data Validation:** Enforced data validation on critical columns

### Manual Verification
- **Rules Management:** Check Rules Management Workbook for proper tab structure
- **Transaction Processing:** Verify company transaction workbooks contain only transaction tabs
- **No Cross-Contamination:** Confirm no rule tabs exist in transaction workbooks

## Troubleshooting

### Common Issues
1. **Wrong Workbook Targeting:** Services operating on incorrect workbook type
2. **Legacy Tab Names:** Old naming convention still in use
3. **Cross-Contamination:** Rule tabs appearing in transaction workbooks

### Resolution Steps
1. **Verify Configuration:** Check `config/companies.json` and service configurations
2. **Update Services:** Ensure all services use latest code with proper workbook targeting
3. **Clean Legacy Tabs:** Delete incorrectly placed rule tabs from transaction workbooks
4. **Validate Naming:** Confirm all tabs use current naming convention

## Security and Access Control

### Protected Columns
- **Row_Hash:** System-managed, protected from user modification
- **Processed_At:** System-managed, protected from user modification
- **Active Tab:** Entire tab protected (read-only)

### Data Validation
- **Approved Column:** Strict TRUE/FALSE validation
- **Company_ID:** Fixed to company ID, validation enforced
- **Target_Sheet/Target_Header:** Must match existing transaction sheet structure

## Future Considerations

### Scalability
- **Multi-Company Support:** Rules Management Workbook supports all companies
- **Tab Management:** Automatic tab creation and cleanup
- **Performance:** Batch operations for efficiency

### Extensibility
- **New Tab Types:** Can be added following established naming conventions
- **Additional Workbooks:** New workbook types can be added with clear separation
- **Enhanced Validation:** Additional data validation rules can be implemented
