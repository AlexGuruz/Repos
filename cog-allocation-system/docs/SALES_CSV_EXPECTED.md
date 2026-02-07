# Sales CSVs – Expected Range (Jan 2025 – Jan 2026)

**Expected:** Sales/OrderItems CSVs covering **January 2025 through January 2026** (13 months).

## Where they should live

| Location | Purpose |
|--------|---------|
| **D:\_data\sales_exports\** | Primary historical location (Nugz OrderItems). Check here first. |
| **Google Drive** [watch folder](https://drive.google.com/drive/folders/1b1XgCjqlcS7UeGeL7oucH92xeuIwxKrP) | New exports; `drive_watcher.py` downloads from here → `data/csv_dump/`. |
| **e:\Repos\cog-allocation-system\data\csv_dump\** | After Drive download or manual copy; used by COG scripts. |

## What’s documented today

- **D:\_data\sales_exports\** – Only **4** Nugz OrderItems files are documented (date ranges like (7-31)-(5-1), (1-31)-(11-1), etc.; likely 2024–2025).  
- A full **Jan 2025 – Jan 2026** set would be more files (e.g. monthly or quarterly exports).

## If the Jan 2025 – Jan 2026 CSVs are missing

1. **Check D:\_data\sales_exports\** – List files; see if any cover the missing months.
2. **Check the Google Drive watch folder** – Same folder ID as in `config/config.yaml`; see if exports are there.
3. **Re-export from GrowFlow / POS** – OrderItems/sales export for Jan 2025 – Jan 2026; save to `D:\_data\sales_exports\` and/or upload to the Drive folder so `drive_watcher` can pull them into `data/csv_dump/`.
4. **Check D:\Project-Kylo\archive\data\** – One file `2025 sales data.csv` was referenced in an audit; may be a single consolidated export.

## After you have the CSVs

- Put them in **data/csv_dump/** (or ensure Drive watcher has downloaded them there).
- Run:  
  `python scripts/calculate_daily_cog.py --csv-files "data/csv_dump/yourfile.csv"`  
  (or multiple files) to run COG and update sheets.
