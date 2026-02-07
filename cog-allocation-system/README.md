# COG Allocation System

Recreated from COMMAND_REFERENCE.md and Project-Kylo layout_map. Allocates daily Cost of Goods (COG) per brand from sales CSV data → Google Sheets.

## Source & Write Targets

| Role | URL | Sheet | Columns |
|------|-----|-------|---------|
| **Source** | https://drive.google.com/drive/folders/1b1XgCjqlcS7UeGeL7oucH92xeuIwxKrP | — | CSV intake |
| **Write 1** | https://docs.google.com/spreadsheets/d/1GizTKLceyoVVOVAIDrODebYbCK4hRhD5Q9jZ-s0qgIs | COG_RAW_DAILY | Date, Brand, Category, Units, COG |
| **Write 2** | https://docs.google.com/spreadsheets/d/1Pesnh1XQFTKPfagXgCchJQdw0te7m4L1YJAVtOPmyUs | POS_Export | Date, Product Name, ProductCategory, Brand, NetPrice, COGS |

Pipeline details: **docs/PIPELINE_AND_SHEETS.md**.

## Data Flow

```
Sales CSV (OrderItems from POS/GrowFlow) 
    → Google Drive folder (above)
    → drive_watcher.py downloads to data/csv_dump/
    → extract_unique_brands.py → DROP DOWN HELPER (col E brands, G/H categories)
    → calculate_daily_cog.py → NUGZ COG / PUFFIN COG / EMPIRE COG sheets
```

## Structure

```
cog-allocation-system/
├── scripts/
│   ├── drive_watcher.py       # Watch Drive folder, download new CSVs, run pipeline
│   ├── extract_unique_brands.py
│   ├── calculate_daily_cog.py
│   └── populate_categories.py
├── lib/
│   ├── config_loader.py       # Load config.yaml
│   └── sheets_helper.py       # Google Sheets writes
├── config/
│   ├── config.yaml            # Drive folder ID, spreadsheet IDs
│   └── service_account.json   # (you provide)
├── data/
│   ├── csv_dump/              # Downloaded sales CSVs
│   ├── state/                 # drive_watcher_state.json, etc.
│   └── logs/
└── run_drive_watcher.ps1      # PowerShell runner
```

## Google Sheets

| Sheet | Purpose |
|-------|---------|
| **DROP DOWN HELPER** | Col E = brands, Col G = categories, Col H = category inclusion flags |
| **NUGZ COG** | Daily COG by category (DATE + brand/category columns) |
| **PUFFIN COG** | Same for PUFFIN |
| **EMPIRE COG** | Same for EMPIRE |

## Commands

```powershell
cd E:\Repos\cog-allocation-system

# Run once
python scripts/drive_watcher.py --run-once

# Continuous (5 min)
python scripts/drive_watcher.py

# Extract brands
python scripts/extract_unique_brands.py
python scripts/extract_unique_brands.py --dry-run
python scripts/extract_unique_brands.py --remove-excluded-brands

# Calculate COG
python scripts/calculate_daily_cog.py --csv-files "data/csv_dump/file.csv"
python scripts/calculate_daily_cog.py --csv-files "data/csv_dump/file.csv" --dry-run

# Populate categories
python scripts/populate_categories.py
```

## Service Account (Device-Wide)

No need to copy credentials into each repo. Put your service account JSON in:

**`D:\_config\google_service_account.json`**

Or set the env var:
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "D:\_config\google_service_account.json"
```

The COG system will use it automatically. Override per-repo with `config.yaml` → `google_sheets.service_account_path` if needed.

## Related

- **Sales CSVs:** `D:\_data\sales_exports\` (Nugz OrderItems) or Google Drive watch folder
- **Kylo:** BALANCE sheet pulls NUGZ COG column
- **Growflow:** May be source of sales exports (POS/compliance)
