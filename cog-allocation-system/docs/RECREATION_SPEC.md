# COG Allocation System - Recreation Spec

Recovered from Project-Kylo COMMAND_REFERENCE.md, layout_map.json, PRE_DELETE_CHECKLIST.

## Scripts (from COMMAND_REFERENCE)

| Script | Purpose |
|--------|---------|
| `drive_watcher.py` | Monitors Google Drive watch folder every 5 min. Processes new CSV files to csv_dump, then runs COG pipeline. |
| `drive_watcher.py --run-once` | Single run, then exit. |
| `extract_unique_brands.py` | Extracts unique brand names from CSV files → Google Sheet "DROP DOWN HELPER" column E. |
| `extract_unique_brands.py --dry-run` | Preview only. |
| `extract_unique_brands.py --remove-excluded-brands` | Removes brands if ALL categories excluded (column H flags). |
| `calculate_daily_cog.py --csv-files "data/csv_dump/file.csv"` | Processes CSV sales data, calculates daily COG per brand → "COG" sheet (or NUGZ COG, etc.). |
| `calculate_daily_cog.py --dry-run` | Preview. |
| `populate_categories.py` | Extracts categories from CSVs → DROP DOWN HELPER column G (categories), column H (inclusion flags). |

## Data Paths

| Path | Purpose |
|------|---------|
| `data/csv_dump/` | Input sales CSV files |
| `data/state/brand_state.json` | Brand state |
| `data/state/cog_state.json` | COG calculation state |
| `data/state/drive_watcher_state.json` | Drive watcher progress |
| `data/logs/drive_watcher.log` | Watcher log |

## Google Sheet Layout - DROP DOWN HELPER

- **Column E:** Unique brands (from CSV)
- **Column G:** Categories
- **Column H:** Category inclusion flags (exclude brands if all excluded)

## Google Sheet Layout - NUGZ COG (from layout_map)

Headers (row 19): DATE, then category columns:
- (MJ) PRODUCTS, (NON-MJ) PROD., NUGZ PAYROLL, FIRE SAFETY, AMAZON, WALMART, HARDWARE, SAMS, OMMA, OBNDD, FUEL, FACEBOOK (MP), PARKING METER, MISC., HEALTH DEPARTMENT, METRC TAGS, TESTING, SALES TAX, ESTIMATED TAX, MJ TAX, Total

Dates map to row numbers (e.g. 01/01/25 → row 22).

## CSV Format (Assumed)

OrderItems format from Nugz sales exports:
- Files like `Nugz (7-31)-(5-1) OrderItems.csv` in `D:\_data\sales_exports\`
- Contains: product/brand, quantity, revenue, date, etc.
- Used to allocate COG by brand based on sales mix

## Google Drive Watch Folder

- **Folder ID:** `1b1XgCjqlcS7UeGeL7oucH92xeuIwxKrP`
- **URL:** https://drive.google.com/drive/folders/1b1XgCjqlcS7UeGeL7oucH92xeuIwxKrP

## Integration Points

- **BALANCE sheet:** NUGZ COG column 6 (from layout)
- **Kylo:** Reads BALANCE for daily totals
- **GrowFlow / POS:** Likely source of OrderItems/sales CSV exports
- **Google Drive:** Watch folder for automated CSV intake
