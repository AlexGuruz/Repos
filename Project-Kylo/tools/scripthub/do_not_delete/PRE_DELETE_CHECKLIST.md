# Pre-Delete Checklist for ScriptHub

**Before deleting ScriptHub, verify these items:**

## ✅ Completed
- [x] Scripts vendored into Kylo at `tools/scripthub/do_not_delete/`
- [x] All 11 scripts copied
- [x] Source files (gsheets.py, rules.py) copied
- [x] Config file copied
- [x] Hardcoded paths fixed (runner_sync_bank.pyw)
- [x] No scheduled tasks found referencing ScriptHub

## ⏳ Required Before Delete

### 1. Archive ScriptHub (REQUIRED)
**Do this FIRST before deleting:**

```powershell
# Create archive directory
mkdir D:\_archive\2026-01-27\scripthub -Force

# Create zip archive
Compress-Archive -Path D:\ScriptHub -DestinationPath D:\_archive\2026-01-27\scripthub\ScriptHub.zip -Force

# Create git bundle (if ScriptHub is a git repo)
cd D:\ScriptHub
if (Test-Path .git) {
    git bundle create D:\_archive\2026-01-27\scripthub\ScriptHub.bundle --all
}

# Move instead of delete (safer)
move D:\ScriptHub D:\_archive\2026-01-27\scripthub\ScriptHub_original
```

### 2. Verify Migration Works
**Test the vendored scripts:**

```powershell
cd D:\Project-Kylo\tools\scripthub\do_not_delete

# Run smoke test
.\smoke_test.ps1

# Test a script (dry run)
.\run.ps1 sync_bank.py --dry-run
```

### 3. Provide Credentials
**Copy service account JSON:**
- Source: `D:\ScriptHub\DO NOT DELETE\config\service_account.json`
- Destination: `D:\Project-Kylo\tools\scripthub\do_not_delete\config\service_account.json`

### 4. Check for Other Dependencies
**Verify these are NOT needed by Kylo:**
- [ ] GrowFlow automation (separate system, documented separately)
- [ ] PettyCash (Kylo has its own, but verify external usage)
- [ ] COG allocation system (referenced in Kylo docs, but separate)

### 5. Update Any Manual References
**Search for any hardcoded ScriptHub paths:**
- Check Kylo codebase for `D:\ScriptHub` references
- Check any documentation that mentions ScriptHub paths
- Check any manual scripts or shortcuts

## Safe to Delete After

Once you've:
1. ✅ Archived ScriptHub (zip + git bundle)
2. ✅ Verified vendored scripts work
3. ✅ Provided credentials
4. ✅ Confirmed no other dependencies

Then you can safely:
- Move ScriptHub to archive: `move D:\ScriptHub D:\_archive\2026-01-27\scripthub\ScriptHub_original`
- Or delete if you're confident: `Remove-Item D:\ScriptHub -Recurse -Force`

## Recommended: Archive First, Delete Later

**Best practice:** Archive now, delete later after you've verified everything works for a few days/weeks.
