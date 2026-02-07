# Growflow

Integration and automation for GrowFlow (cannabis compliance / inventory software).

Previously referenced in NUGZ EXPENSES (column 10) and Kylo ScriptHub docs. Rebuilt from scratch.

## Role (Recovered from layout_map + PRE_DELETE_CHECKLIST)

- **Expense tracking:** GROW FLOW is column 10 in NUGZ EXPENSES sheet (subscription/software cost)
- **Automation:** "GrowFlow automation (separate system, documented separately)" per ScriptHub checklist
- **Likely functions:** Export sales/OrderItems for COG allocation, inventory sync, or compliance reporting

## Data Flow (Inferred)

```
GrowFlow (POS/compliance) 
    → Sales/OrderItems export (CSV?)
    → cog-allocation-system/data/csv_dump/ 
    → COG allocation → NUGZ COG, PUFFIN COG, EMPIRE COG sheets
```

Expense amounts for Grow Flow subscription posted to NUGZ EXPENSES col 10.

## Structure

```
Growflow/
├── config/           # API keys, mappings, env config
├── scripts/          # Automation and sync scripts
├── docs/             # Documentation
├── data/             # Local data, exports, cache (gitignored)
└── tools/            # Utilities, one-off scripts
```

## Setup

1. Copy `config/config.example.yaml` to `config/config.yaml`
2. Add API credentials (GrowFlow, Sheets, etc.)
3. See `docs/SETUP.md` for detailed setup

## Related Systems

- **Kylo** – petty cash, transactions; BALANCE sheet references NUGZ COG
- **ScriptHub** – sync_bank, expense posting
- **cog-allocation-system** – sales CSV → daily COG per brand (may consume GrowFlow exports)

## License

Private / internal use.
