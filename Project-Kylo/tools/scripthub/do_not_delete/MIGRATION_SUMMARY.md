# ScriptHub DO NOT DELETE Migration Summary

**Migration Date:** 2026-01-27  
**Source:** `D:\ScriptHub\DO NOT DELETE\`  
**Destination:** `D:\Project-Kylo\tools\scripthub\do_not_delete\`

## Files Copied

### Scripts (11 files)
- `scripts/sync_bank.py` - Applies Kylo_Config rules to CLEAN TRANSACTIONS
- `scripts/sync_company_ids.py` - Syncs Company IDs from BANK to CLEAN TRANSACTIONS
- `scripts/dynamic_columns_jgdtruth.py` - Maps headers/dates for JGDTRUTH sheets
- `scripts/run_both_syncs.py` - Bundled script that runs all sync scripts
- `scripts/server.py` - FastAPI webhook server
- `scripts/rule_loader_jgdtruth.py` - Loads JGD Truth rules from Excel
- `scripts/clear_provenance.py` - Clears provenance column
- `scripts/diag_cols.py` - Diagnoses column structure
- `scripts/set_validation.py` - Sets data validation rules
- `scripts/gui_scheduler.py` - GUI for managing Windows Task Scheduler
- `scripts/runner_sync_bank.pyw` - Windowed runner for sync_bank (FIXED)

### Source Files (2 files)
- `src/gsheets.py` - Google Sheets API utilities
- `src/rules.py` - Rule loading utilities

### Config Files (1 file)
- `config/config.json` - Configuration file (requires service_account.json separately)

### Documentation & Wrappers (3 files)
- `README.md` - Documentation
- `run.ps1` - PowerShell wrapper script
- `smoke_test.ps1` - Smoke test script

## Path Rewrites Performed

### 1. `scripts/runner_sync_bank.pyw`
**Original:**
```python
base = r"D:\\ScriptHub\\utils"
```

**Fixed:**
```python
script_dir = Path(__file__).parent
base = script_dir.parent.resolve()
```

**Rationale:** Removed hardcoded absolute path, now uses relative path resolution.

### 2. All Scripts
**Original:** Scripts referenced `config/` and `src/` relative to ScriptHub root

**Fixed:** All scripts now resolve paths relative to their location:
- `config/config.json` resolved from `scripts/` parent directory
- `src/` imports resolved via PYTHONPATH set to parent directory

**Rationale:** Makes scripts portable and independent of external ScriptHub location.

## Missing Dependencies

### Required but Not Copied (Must Be Provided Separately)
1. **`config/service_account.json`** - Google Service Account credentials
   - **Action Required:** Copy from ScriptHub or provide new credentials
   - **Location:** Should be placed in `tools/scripthub/do_not_delete/config/service_account.json`

2. **`JGD Truth Current.xlsx`** or **`JGDTruth.xlsx`** - Excel file for rule_loader
   - **Action Required:** Copy from ScriptHub if needed, or provide separately
   - **Location:** Can be placed in `tools/scripthub/do_not_delete/` or specified via `--file` argument

### Python Dependencies
All scripts require standard Python packages. Check if Kylo's venv has:
- `google-auth`
- `google-api-python-client`
- `gspread`
- `pandas`
- `openpyxl`
- `fastapi`
- `uvicorn`

**Action Required:** Verify Kylo's `requirements.txt` or `pyproject.toml` includes these.

## Scheduled Tasks

### Current State
No scheduled tasks were found matching ScriptHub patterns. This could mean:
1. Tasks are named differently
2. Tasks were already removed
3. Tasks are configured on a different system

### Recommended Task Configuration

**Task Name:** `KyloSyncPeriodic`

**Command (Option A - Recommended):**
```powershell
powershell.exe -ExecutionPolicy Bypass -File "D:\Project-Kylo\tools\scripthub\do_not_delete\run.ps1"
```

**Command (Option B - Direct):**
```powershell
python.exe "D:\Project-Kylo\tools\scripthub\do_not_delete\scripts\run_both_syncs.py"
```

**Working Directory:** `D:\Project-Kylo\tools\scripthub\do_not_delete`

**Trigger:** Periodic (every 5 minutes or as configured)

## Verification Steps

1. **Run Smoke Test:**
   ```powershell
   cd D:\Project-Kylo\tools\scripthub\do_not_delete
   .\smoke_test.ps1
   ```

2. **Test Individual Scripts:**
   ```powershell
   .\run.ps1 sync_bank.py --dry-run
   .\run.ps1 dynamic_columns_jgdtruth.py --summary
   ```

3. **Verify Config:**
   - Ensure `config/service_account.json` exists
   - Verify `config/config.json` has correct spreadsheet IDs

4. **Test Scheduled Task:**
   - Create or update task to use new paths
   - Run task manually to verify it works
   - Monitor logs in `logs/` directory

## Next Steps

1. ✅ **Migration Complete** - Scripts vendored into Kylo
2. ⏳ **Provide Credentials** - Copy `service_account.json` to config directory
3. ⏳ **Update Scheduled Tasks** - Repoint any existing tasks to new paths
4. ⏳ **Test Execution** - Run smoke test and verify scripts work
5. ⏳ **Archive ScriptHub** - After verification, archive original ScriptHub

## Notes

- ScriptHub original remains untouched (read-only)
- All scripts use relative path resolution (no hardcoded ScriptHub paths)
- Wrapper script (`run.ps1`) handles Python resolution (venv or system)
- Smoke test verifies file structure and imports
