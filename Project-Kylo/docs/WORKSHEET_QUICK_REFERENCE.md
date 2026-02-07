# Worksheet Quick Reference

## Workbook Types

| Workbook Type | Spreadsheet ID | Purpose | Contains |
|---------------|----------------|---------|----------|
| **Rules Management** | `1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec` | Rule management & promotion | Pending/Active rule tabs for all companies |
| **Company Transaction** | From `config/companies.json` | Transaction processing | Company-specific transaction sheets |

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
# ... other transaction sheets
```

## Service Responsibilities

| Service | Target Workbook | Operations |
|---------|----------------|------------|
| `services/rules_promoter/service.py` | **Rules Management** only | Rule promotion, banner rows |
| `services/bus/kafka_consumer_promote.py` | **Rules Management** only | Rule promotion via Kafka |
| `services/sheets/poster.py` | **Company Transaction** only | Transaction posting |

## Critical Rules

⚠️ **NEVER:**
- Target company transaction workbooks for rule management
- Target rules management workbook for transaction processing
- Use old tab naming convention (`"Pending Rules – {CID}"`)
- Create rule tabs in transaction workbooks

✅ **ALWAYS:**
- Use new tab naming convention (`"{CID} Pending"`, `"{CID} Active"`)
- Target correct workbook type for each operation
- Respect strict separation between workbook types
- Use batchUpdate operations only

## Tab Headers

### Pending Tab (Rules Management)
```
Row_Hash | Date | Source | Company_ID | Amount | Target_Sheet | Target_Header | Match_Notes | Approved | Rule_ID | Processed_At
```

### Active Tab (Rules Management)
```
Ruleset_Version | Effective_At | Company_ID | Source | Target_Sheet | Target_Header | Match_Notes | Created_At
```

## Configuration Files

- **Rules Management Workbook ID:** Hardcoded in services
- **Company Transaction Workbook IDs:** `config/companies.json` → `workbook` field
- **Tab Naming:** Enforced in all services

## Troubleshooting

### Issue: Rule tabs in transaction workbooks
**Solution:** Delete these tabs - they were incorrectly created

### Issue: Services targeting wrong workbook
**Solution:** Check service configuration and update to latest code

### Issue: Old tab naming convention
**Solution:** Update to use `"{CID} Pending"` and `"{CID} Active"`

## Validation Checklist

- [ ] Rules management operations target Rules Management Workbook only
- [ ] Transaction processing operations target Company Transaction Workbooks only
- [ ] All tabs use new naming convention
- [ ] No rule tabs exist in transaction workbooks
- [ ] Services use correct spreadsheet IDs
- [ ] Tab headers match specifications
- [ ] Protected columns are properly configured
