# Sheets Contract

## Worksheet Architecture

The system uses **two separate Google Sheets workbooks** with distinct purposes:

### 1. Rules Management Workbook
- **Spreadsheet ID:** `1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec`
- **Purpose:** Rule management, approval, and promotion workflow
- **Contains:** Pending and Active rule tabs for all companies

### 2. Company Transaction Workbooks
- **Purpose:** Transaction processing and financial data output
- **Contains:** Company-specific transaction sheets (PETTY CASH, BALANCE, PAYROLL, etc.)
- **Configuration:** Defined in `config/companies.json` under `workbook` field

## Tab Naming Convention

### Rules Management Tabs (Rules Management Workbook)
Per company tabs in the rules management workbook:
- **Pending tab name:** `"{CID} Pending"` (e.g., "NUGZ Pending")
- **Active tab name:** `"{CID} Active"` (e.g., "NUGZ Active")

### Transaction Processing Tabs (Company Transaction Workbooks)
Transaction data is posted to company-specific workbooks with tabs like:
- `PETTY CASH`
- `BALANCE`
- `PAYROLL`
- `EXPENSES`
- etc.

## Rules Management Tab Specifications

### Pending Tab Headers (row 1; frozen):
`Row_Hash | Date | Source | Company_ID | Amount | Target_Sheet | Target_Header | Match_Notes | Approved | Rule_ID | Processed_At`

- **Approved:** Data validation (TRUE/FALSE), strict
- **Company_ID:** Fixed to company ID, data validation enforced
- **Row_Hash:** System-managed column (protected)
- **Processed_At:** System-managed column (protected)

### Active Tab Headers (row 1; frozen):
`Ruleset_Version | Effective_At | Company_ID | Source | Target_Sheet | Target_Header | Match_Notes | Created_At`

- **Entire tab:** System-protected (read-only)
- **Content:** Automatically populated from promoted rules

## Posting Protocol

### Rules Management
- **Workbook:** Rules Management Workbook only
- **Method:** batchUpdate only, in blocks; no single-cell writes
- **Deduplication:** Via `control.sheet_posts.batch_signature`
- **Tab Creation:** Automatic via `ensure_company_tabs()`

### Transaction Processing
- **Workbook:** Company Transaction Workbooks only
- **Method:** batchUpdate only, in blocks; no single-cell writes
- **Deduplication:** Via `control.sheet_posts.batch_signature`
- **Target:** Specific `target_header` columns within transaction tabs

## Strict Separation

⚠️ **CRITICAL:** The system enforces strict separation:
- **Rules management** operations ONLY target the Rules Management Workbook
- **Transaction processing** operations ONLY target Company Transaction Workbooks
- **No cross-contamination** between the two workbook types
- **All services and scripts** must respect this separation

## Migration Notes

- Old tab naming convention (`"Pending Rules – {CID}"`, `"Active Rules – {CID}"`) is deprecated
- All new operations use the new convention (`"{CID} Pending"`, `"{CID} Active"`)
- Legacy tabs in company transaction workbooks should be deleted
- Rules management operations now exclusively use the Rules Management Workbook
