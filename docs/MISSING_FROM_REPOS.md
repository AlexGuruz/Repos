# What’s Missing From the Repos

Summary of items that are **expected by the systems but not stored in the repo** (or only documented elsewhere). Use this as a checklist when setting up a new machine or recovering data.

---

## 1. Data files (never in git)

| Item | Expected location | Notes |
|------|-------------------|--------|
| **Sales CSVs (Jan 2025 – Jan 2026)** | `cog-allocation-system/data/csv_dump/` or `D:\_data\sales_exports\` | Gitignored. Only 4 older Nugz OrderItems files documented on D:; full range may need re-export from GrowFlow/POS. See `cog-allocation-system/docs/SALES_CSV_EXPECTED.md`. |
| **COG state / Drive watcher state** | `cog-allocation-system/data/state/*.json` | `brand_state.json`, `cog_state.json`, `drive_watcher_state.json` – gitignored. |
| **Drive watcher logs** | `cog-allocation-system/data/logs/*.log` | Gitignored. |
| **2025 sales data** | `D:\Project-Kylo\archive\data\2025 sales data.csv` | Referenced in audit; on D: drive, not in repo. |

---

## 2. Credentials & secrets (gitignored or external)

| Item | Where it’s expected | Notes |
|------|---------------------|--------|
| **Google service account (COG / Sheets)** | `D:\_config\google_service_account.json` or `%LOCALAPPDATA%\_config\` or `cog-allocation-system/config/service_account.json` | Device-wide or per-repo. Required for Drive watcher, COG sheets, Growflow. |
| **Google service account (Kylo)** | `Project-Kylo/.secrets/service_account.json` | Required for watchers and Sheets posting. `.secrets/` is gitignored; README says to add the file. |
| **ScriptHub do_not_delete** | `Project-Kylo/tools/scripthub/do_not_delete/config/service_account.json` | Migration docs say copy from ScriptHub or create new. |
| **PettyCash** | `PettyCash_Migration_Package/PettyCash/config/service_account.json` | Google Sheets; you must add. |
| **Project-Kylo `.env`** | Root `.env` (gitignored) | `DATABASE_URL`, `DATABASE_URL_POOL`, `GOOGLE_APPLICATION_CREDENTIALS`, etc. Optional if using `config/dsn_map.json`. |
| **Kylo `dsn_map_local.json`** | `Project-Kylo/config/dsn_map_local.json` | Local DB overrides; may be gitignored or not committed. Check repo. |

---

## 3. Things that live on D: (not in E:\Repos)

| Item | Location on D: | Notes |
|------|----------------|--------|
| **Sales exports** | `D:\_data\sales_exports\` | Nugz OrderItems CSVs (docs say 4 files moved there 2026-01-27). |
| **Device-wide config** | `D:\_config\` | e.g. `google_service_account.json`, workspace, gcloud. |
| **ScriptHub (original)** | `D:\ScriptHub` or `D:\_archive\2026-01-27\scripthub\` | Source for scripthub_legacy / do_not_delete; may be archived. |
| **GrowFlow / Sales Analytics** | `D:\ScriptHub\DO NOT DELETE\GrowFlow\`, `...\Sales Analytics\` | ScriptHub classification: “DO NOT DELETE”; sales data and automation. |
| **Project-Kylo archive** | `D:\Project-Kylo\archive\data\` | e.g. `2025 sales data.csv`. |
| **REMODEL / Remodel-Template** | `D:\REMODEL`, `D:\Remodel-Template` | Template source; FRESH_RIG mentions `D:\REMODEL\secrets`. |

---

## 4. Incomplete or TODO in repo

| Area | Missing / TODO | Reference |
|------|-----------------|-----------|
| **Growflow** | GrowFlow API client; export sales/OrderItems to csv_dump or Drive; post Grow Flow expense to NUGZ EXPENSES col 10; document CSV format. | `Growflow/docs/RECREATION_SPEC.md` |
| **cog-allocation-system** | OrderItems CSV column parsing is TODO in `calculate_daily_cog.py`. | Script comment |
| **ScriptHub do_not_delete** | `service_account.json` and possibly other config; “Missing Dependencies” in migration summary. | `Project-Kylo/tools/scripthub/do_not_delete/MIGRATION_SUMMARY.md` |
| **_archive in workspace** | `e:\Repos\_archive` is gitignored (e.g. `_archive/ScriptHub/` had broken git state). Content not in repo. | Earlier conversation |

---

## 5. Optional / environment-specific

| Item | Purpose |
|------|--------|
| **Docker / Kafka override** | If `D:\REMODEL\secrets` is missing, use `docker-compose.kafka-consumer.override.yml` so Kylo uses `.secrets`. |
| **Python / venv** | Each repo may expect its own venv (e.g. Project-Kylo `.venv`); not in git. |
| **Instance/runtime state** | `.kylo/instances/`, watcher logs – gitignored. |

---

## Quick recovery checklist

- [ ] Sales CSVs: Copy from `D:\_data\sales_exports\` or Google Drive into `cog-allocation-system/data/csv_dump/`, or re-export from GrowFlow.
- [ ] Google service account: Add to `D:\_config\` (or per-repo paths above) for COG, Kylo, PettyCash, ScriptHub do_not_delete.
- [ ] Kylo: Add `Project-Kylo/.secrets/service_account.json`; ensure `.env` or `config/dsn_map*.json` for DB if needed.
- [ ] Growflow: Implement or restore export to csv_dump/Drive and expense posting if needed.
- [ ] D: drive: If you have it, verify `D:\_data\sales_exports\`, `D:\_config\`, and any ScriptHub/Project-Kylo archive paths.
