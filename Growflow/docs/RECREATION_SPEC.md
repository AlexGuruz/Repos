# Growflow - Recreation Spec

Recovered from Project-Kylo layout_map.json, PRE_DELETE_CHECKLIST, COMMAND_REFERENCE.

## What We Know

### From layout_map.json (NUGZ EXPENSES)

- **GROW FLOW** = column 10 in NUGZ EXPENSES sheet
- Same row as: FARMERS INS., UTILITIES, ADT, OEC, SQUARE, METRC FEE, POS SYSTEM(BLEUM), etc.
- Grow Flow is an expense line item (software/subscription cost)
- POS SYSTEM (BLEUM) is column 9 – BLEUM is the POS; GrowFlow is separate (likely compliance/inventory)

### From PRE_DELETE_CHECKLIST

- "GrowFlow automation (separate system, documented separately)"
- Listed as dependency to verify before deleting ScriptHub
- No recovered docs or code

### Inferred Role

1. **Expense:** Grow Flow subscription fees posted to NUGZ EXPENSES col 10
2. **Data source:** May export sales/OrderItems that feed cog-allocation-system (CSV → COG)
3. **Compliance:** Cannabis compliance software – inventory, reporting, METRC

## Integration Points

| System | Connection |
|--------|------------|
| NUGZ EXPENSES | Column 10 = Grow Flow expense amounts |
| COG allocation | Sales CSV (OrderItems) – may come from GrowFlow export |
| Kylo BALANCE | NUGZ EXPENSES feeds into balance calc |
| D:\_data\sales_exports | Nugz OrderItems.csv – historical sales; format may match GrowFlow export |

## TODO (Recreation)

- [ ] GrowFlow API client (if API exists)
- [ ] Export sales/OrderItems to csv_dump or Google Drive
- [ ] Post Grow Flow subscription expense to NUGZ EXPENSES col 10
- [ ] Document CSV format for COG compatibility
