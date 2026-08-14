# Repository path contract for agents

The workspace was reorganized in July 2026. All agents, scripts, and commands must use the current zoned paths below.

## Canonical paths

| System | Canonical source path |
|---|---|
| Project Kylo | `E:\Repos\products\project-kylo` |
| Greg Kylo | `E:\Repos\products\greg-kylo` |
| Growflow | `E:\Repos\products\growflow` |
| COG allocation | `E:\Repos\products\cog-allocation` |
| AI Lab | `E:\Repos\products\ai-lab` |
| AI Lab governance | `E:\Repos\products\ai-lab-governance` |
| Kylo marketing site | `E:\Repos\products\kylo-site` |
| GIGATT Geomapper | `E:\Repos\products\gigatt-geomapper` |
| GIGATT Platform | `E:\Repos\products\gigatt-platform` |
| Obsidian Brain vault | `E:\Repos\internal\obsidian-brain\Obsidian\Brain` |
| GIGATT transport internals | `E:\Repos\internal\gigatt-transport` |
| Migration tooling | `E:\Repos\tools\migration` |

## Removed flat paths

Do not use or recreate these retired paths:

- `E:\Repos\Project-Kylo`
- `E:\Repos\Greg-Kylo`
- `E:\Repos\Growflow`
- `E:\Repos\cog-allocation-system`
- `E:\Repos\ai-lab`
- `E:\Repos\ai-lab-governance`
- `E:\Repos\kylo-site`
- `E:\Repos\geomapper app`
- `E:\Repos\Ai`

When an old path appears in a historical log, evidence artifact, or archived note, treat it as historical context—not a valid command.

## Runtime exception

`C:\Project-Kylo` is an intentional power-1 runtime alias/junction. It is not the Acheron source path. The intended power-1 target is:

`C:\worker\repos\products\project-kylo`

Greg Kylo on power-1 is expected at:

`C:\worker\repos\products\greg-kylo`

## Agent behavior

1. Start from `E:\Repos\Repos.code-workspace` or `E:\Repos`.
2. Read `docs/SENIOR_LAYOUT.md` and `docs/SYSTEMS_AND_REPOS.md` before cross-repo work.
3. Resolve paths through `tools/migration/python/repos_paths.py` or `tools/migration/lib/Paths.psm1` instead of assuming sibling folders.
4. Search for stale flat paths before adding or changing scripts, task installers, workspace files, registries, or Cursor rules.
5. Keep secrets in `E:\secrets` or approved runtime secret mounts; never place credentials in tracked paths.
6. Do not sync or modify power-1 production merely because an Acheron path changed. Verify the worker path and run the power-1 smoke checks first.

## Verification

```powershell
cd E:\Repos\tools\migration
python -m pytest python\test_repos_paths.py -q
.\verify.ps1
```

Migration details: `docs/REPO_PATH_MIGRATION.md`.
