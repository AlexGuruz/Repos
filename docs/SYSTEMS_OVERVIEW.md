# Systems Overview – GrowFlow, COG, Kylo

Recovered from Project-Kylo, layout_map, COMMAND_REFERENCE. Recreations in E:\Repos.

## COG watcher – source & write targets

- **Source (CSV intake):** https://drive.google.com/drive/folders/1b1XgCjqlcS7UeGeL7oucH92xeuIwxKrP
- **Write 1 (COG_RAW_DAILY):** https://docs.google.com/spreadsheets/d/1GizTKLceyoVVOVAIDrODebYbCK4hRhD5Q9jZ-s0qgIs — tab COG_RAW_DAILY | Date, Brand, Category, Units, COG
- **Write 2 (POS_Export):** https://docs.google.com/spreadsheets/d/1Pesnh1XQFTKPfagXgCchJQdw0te7m4L1YJAVtOPmyUs — tab POS_Export | Date, Product Name, ProductCategory, Brand, NetPrice, COGS

Pipeline: **cog-allocation-system/docs/PIPELINE_AND_SHEETS.md**. Bank/Kylo: Project-Kylo config.

## Architecture

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│ GrowFlow / POS  │     │ cog-allocation-system    │     │ Kylo / ScriptHub    │
│ (BLEUM, etc.)   │────▶│ Sales CSV → COG by brand  │────▶│ BALANCE, NUGZ COG   │
│                 │     │ DROP DOWN HELPER         │     │ JGD EXPENSES        │
└────────┬────────┘     └──────────────────────────┘     └─────────────────────┘
         │
         │ NUGZ EXPENSES col 10 (Grow Flow subscription)
         └──────────────────────────────────────────────▶ NUGZ EXPENSES sheet
```

## Repos

| Repo | Location | Purpose |
|------|----------|---------|
| **cog-allocation-system** | E:\Repos\cog-allocation-system | Sales CSV → daily COG per brand → NUGZ/PUFFIN/EMPIRE COG sheets |
| **Growflow** | E:\Repos\Growflow | GrowFlow integration: expense tracking (NUGZ EXPENSES col 10), sales export |
| **Project-Kylo** | E:\Repos\Project-Kylo | Petty cash, watchers, BANK, transactions, BALANCE |

## Data Paths

| Path | Purpose |
|------|---------|
| D:\_data\sales_exports\ | Nugz OrderItems.csv (historical sales) |
| cog-allocation-system/data/csv_dump/ | Input sales CSVs for COG |
| cog-allocation-system/data/state/ | brand_state, cog_state, drive_watcher_state |
| D:\_config\ or %LOCALAPPDATA%\_config\ (google_service_account.json) | Device-wide Google creds |

## Google Sheets

- **BALANCE:** NUGZ COG col 6, NUGZ EXPENSES col 7, etc.
- **NUGZ EXPENSES:** Col 10 = GROW FLOW
- **NUGZ COG, PUFFIN COG, EMPIRE COG:** Daily COG by category
- **DROP DOWN HELPER:** Brands (E), categories (G), flags (H)

## Original Locations (D:\)

- ScriptHub: D:\ScriptHub (or archived)
- cog-allocation-system: D:\ScriptHub\cog-allocation-system
- Project-Kylo: D:\Project-Kylo (or E:\Repos\Project-Kylo)
