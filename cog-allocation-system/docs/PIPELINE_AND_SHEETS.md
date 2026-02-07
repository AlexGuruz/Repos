# COG Pipeline & Sheet URLs

Single reference for what the COG watcher uses and feeds. Consolidates Project-Kylo `config.json` and layout_map.

---

## Source (CSV intake)

| URL | ID |
|-----|-----|
| https://drive.google.com/drive/folders/1b1XgCjqlcS7UeGeL7oucH92xeuIwxKrP | `1b1XgCjqlcS7UeGeL7oucH92xeuIwxKrP` |

---

## Write Target 1: COG_RAW_DAILY

| Field | Value |
|-------|-------|
| **URL** | https://docs.google.com/spreadsheets/d/1GizTKLceyoVVOVAIDrODebYbCK4hRhD5Q9jZ-s0qgIs/edit#gid=1481637753 |
| **Spreadsheet ID** | `1GizTKLceyoVVOVAIDrODebYbCK4hRhD5Q9jZ-s0qgIs` |
| **Sheet** | COG_RAW_DAILY |
| **Columns** | Date, Brand, Category, Units, COG |

---

## Write Target 2: POS_Export

| Field | Value |
|-------|-------|
| **URL** | https://docs.google.com/spreadsheets/d/1Pesnh1XQFTKPfagXgCchJQdw0te7m4L1YJAVtOPmyUs/edit#gid=0 |
| **Spreadsheet ID** | `1Pesnh1XQFTKPfagXgCchJQdw0te7m4L1YJAVtOPmyUs` |
| **Sheet** | POS_Export |
| **Columns** | Date, Product Name, ProductCategory, Brand, NetPrice, COGS |

---

## Other Workbooks (Reference)

| Workbook | URL | Purpose |
|----------|-----|---------|
| **Kylo** | https://docs.google.com/spreadsheets/d/1ZxzOvP14M7syKuZ3EoqaHJUkZoOEcMpgk5adHP9p2no | DROP DOWN HELPER, NUGZ COG, etc. |
| **Bank** | https://docs.google.com/spreadsheets/d/10RC11WsFtlgIUEdq3cpOqBs6hVpZOyPCLkjEnfho7Wk | ScriptHub sync_bank → CLEAN TRANSACTIONS |

---

## Pipeline Status

| Step | Script | Status | Writes to |
|------|--------|--------|-----------|
| 1 | `drive_watcher.py --run-once` | ✅ Implemented | Downloads CSVs to `data/csv_dump/`; uses Drive folder ID above |
| 2 | `extract_unique_brands.py` | ✅ Implemented | DROP DOWN HELPER col E (uses device creds + `spreadsheet_id`) |
| 3 | `calculate_daily_cog.py` | ⚠️ Partial | Parse done. **Writes to:** COG_RAW_DAILY, POS_Export (config set; gspread append not yet implemented). |
| 4 | `populate_categories.py` | ⚠️ Partial | DROP DOWN HELPER G/H (if still used). |

**calculate_daily_cog** must append rows to both targets using column specs above. Map CSV columns (OrderItems) → Date,Brand,Category,Units,COG and → Date,Product Name,ProductCategory,Brand,NetPrice,COGS.

---

## Docs & Config Locations

| What | Where |
|------|--------|
| COG system | E:\Repos\cog-allocation-system |
| COG config | cog-allocation-system/config/config.yaml |
| COG recreation spec | cog-allocation-system/docs/RECREATION_SPEC.md |
| Kylo/Bank IDs | Project-Kylo/tools/scripthub_legacy/config/config.json |
| NUGZ COG layout | Project-Kylo/tools/scripthub_legacy/config/layout_map.json (by_year → 2026 → NUGZ COG) |
| Systems overview | E:\Repos\docs\SYSTEMS_OVERVIEW.md |
| Commands | Project-Kylo/COMMAND_REFERENCE.md (COG section) |

---

## Quick Test

```powershell
cd E:\Repos\cog-allocation-system
python scripts/drive_watcher.py --run-once
```

If Drive has new CSVs, they download and extract_unique_brands runs. If no `service_account` or Drive API fails, fix creds (device-wide path above).
