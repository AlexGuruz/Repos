# Migration Complete - ScriptHub DO NOT DELETE → Kylo

**Date:** 2026-01-27  
**Status:** ✅ COMPLETE

## Summary

All required scripts from `D:\ScriptHub\DO NOT DELETE\scripts\` have been successfully vendored into Kylo at:
`D:\Project-Kylo\tools\scripthub\do_not_delete\`

## Files Migrated

### ✅ Scripts (11 files) - ALL PRESENT
- `scripts/sync_bank.py`
- `scripts/sync_company_ids.py`
- `scripts/dynamic_columns_jgdtruth.py`
- `scripts/run_both_syncs.py`
- `scripts/server.py`
- `scripts/rule_loader_jgdtruth.py`
- `scripts/clear_provenance.py`
- `scripts/diag_cols.py`
- `scripts/set_validation.py`
- `scripts/gui_scheduler.py`
- `scripts/runner_sync_bank.pyw` (PATH FIXED)

### ✅ Source Files (2 files) - ALL PRESENT
- `src/gsheets.py`
- `src/rules.py`

### ✅ Config Files (1 file) - PRESENT
- `config/config.json`

### ✅ Documentation & Tools (4 files) - CREATED
- `README.md`
- `run.ps1` (wrapper script)
- `smoke_test.ps1` (verification script)
- `MIGRATION_SUMMARY.md`

## Path Fixes Applied

1. **`scripts/runner_sync_bank.pyw`**
   - ❌ **Before:** `base = r"D:\\ScriptHub\\utils"`
   - ✅ **After:** Uses relative path resolution from script location

## Scheduled Tasks

**Result:** No scheduled tasks found referencing ScriptHub paths.

This means either:
- Tasks were already removed/renamed
- Tasks are configured on a different system
- Tasks use different naming conventions

**Action:** If you know of any scheduled tasks that should be updated, you can:
1. Find them manually in Task Scheduler
2. Update them to point to: `D:\Project-Kylo\tools\scripthub\do_not_delete\run.ps1`

## Next Steps

### 1. Provide Credentials ⏳
Copy `service_account.json` to:
```
D:\Project-Kylo\tools\scripthub\do_not_delete\config\service_account.json
```

### 2. Test the Migration ✅
Run the smoke test:
```powershell
cd D:\Project-Kylo\tools\scripthub\do_not_delete
.\smoke_test.ps1
```

### 3. Test Individual Scripts ✅
```powershell
# Test sync_bank (dry run)
.\run.ps1 sync_bank.py --dry-run

# Test dynamic columns
.\run.ps1 dynamic_columns_jgdtruth.py --summary

# Test full sync
.\run.ps1 run_both_syncs.py
```

### 4. Update Scheduled Tasks (if any exist) ⏳
If you find scheduled tasks, update them to use:
```powershell
powershell.exe -ExecutionPolicy Bypass -File "D:\Project-Kylo\tools\scripthub\do_not_delete\run.ps1"
```

### 5. Archive ScriptHub ⏳
After verification, archive ScriptHub:
```powershell
mkdir D:\_archive\2026-01-27\scripthub -Force
Compress-Archive -Path D:\ScriptHub -DestinationPath D:\_archive\2026-01-27\scripthub\ScriptHub.zip -Force
cd D:\ScriptHub
git bundle create D:\_archive\2026-01-27\scripthub\ScriptHub.bundle --all
move D:\ScriptHub D:\_archive\2026-01-27\scripthub\ScriptHub_original
```

## Verification

All files are present and ready. The migration is **COMPLETE**.

To verify yourself:
```powershell
cd D:\Project-Kylo\tools\scripthub\do_not_delete
Get-ChildItem -Recurse -File | Measure-Object | Select-Object Count
# Should show 18 files total
```
