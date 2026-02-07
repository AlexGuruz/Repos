# Portable Drive Cleanup Control Center

Rules:
- NO deleting files during the first pass
- Only scripted moves (PowerShell) after dry-run
- Clean ONE chunk folder at a time
- Anything uncertain goes to archive, not deleted

Current chunk:
- (set this before running an audit)

Status:
- Inventory: NOT STARTED
- Move plan: NOT STARTED
- Dry run: NOT STARTED
- Execute: NOT STARTED

What goes in each folder (so you understand it)

_audit\
Inventory outputs (tree, csv, hashes)

_manifests\
Move plans: move_manifest.csv

_scripts\
PowerShell scripts: scan + dry-run + execute

_logs\
Run logs from scripts

_notes\
Notes like "what is active / what is dead / keep list"
