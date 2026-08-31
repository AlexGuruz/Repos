# Senior layout migration toolkit

Safe, logged hard-cut of `E:\Repos` into zone folders (`products/`, `internal/`, …).

## Quick start (engineer order)

```powershell
cd E:\Repos\tools\migration

# 0) Close Cursor tabs on heavy folders (Growflow, Project-Kylo, ai-lab, Ai, WinPython).
#    Prefer a window rooted at tools\migration only during the cut.

# 1) Path helpers self-check
python -m pytest python\test_repos_paths.py -q

# 2) Clear locks + preflight + inventory
.\clear_locks.ps1 -Apply
.\preflight.ps1
.\inventory.ps1

# 3) Rewrite dry-run (no writes)
.\rewrite.ps1

# 4) E: drive hygiene dry-run
.\edrive_hygiene.ps1 -DryRun

# 5) Monorepo migrate dry-run
.\migrate.ps1 -DryRun

# --- maintenance window ---
# 6) Apply
.\clear_locks.ps1 -Apply
.\edrive_hygiene.ps1 -Apply
.\migrate.ps1 -Apply
.\rewrite.ps1 -Apply
.\obsidian_remap.ps1 -Apply
.\generate_workspace.ps1 -Apply
.\tasks_export.ps1
.\tasks_reinstall.ps1 -Apply
.\verify.ps1
```

**Lock rule:** never leave a full-tree `robocopy /MOVE` running overnight on Growflow/WinPython — migrate now moves **children** on failure and skips `.claude` lock magnets.
## SSOT

- [`layout.json`](layout.json) — every old→new path, power-1 junctions, E: moves
- Python: [`python/repos_paths.py`](python/repos_paths.py)
- PowerShell: [`lib/Paths.psm1`](lib/Paths.psm1)

## Scripts

| Script | Purpose |
|--------|---------|
| `preflight.ps1` | Gate before apply |
| `inventory.ps1` | Find legacy path strings |
| `rewrite.ps1` | Dry-run/apply path rewrites |
| `migrate.ps1` | Zone create + folder moves |
| `rollback.ps1` | Reverse last migrate log |
| `edrive_hygiene.ps1` | Personal / `_archive_E` moves |
| `power1_junction.ps1` / `power1_smoke.ps1` | Runtime junction + health |
| `tasks_export.ps1` / `tasks_reinstall.ps1` | Scheduled task safety |
| `obsidian_remap.ps1` | Remap `repo_obsidian_map.json` |
| `obsidian_frontmatter_remap.ps1` | Remap vault note frontmatter `repo_path` fields |
| `generate_workspace.ps1` | Clean Cursor workspace |
| `verify.ps1` | Pass/fail after cut |

Reports land in `reports/` (gitignored).

## Env vars

`REPOS_ROOT`, `AI_LAB_ROOT`, `AI_LAB_GOVERNANCE_ROOT`, `OPERATOR_BRAIN_VAULT_ROOT`

## Do not

- Push GitHub until `verify.ps1` is green and you approve
- Delete `E:\secrets` or personal media
- Merge Kylo / Growflow / ai-lab / COG
