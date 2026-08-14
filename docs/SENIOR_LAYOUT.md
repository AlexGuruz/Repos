# Senior Repos Layout

**SSOT for moves:** [`tools/migration/layout.json`](../tools/migration/layout.json)  
**Runbook:** [`tools/migration/README.md`](../tools/migration/README.md)  
**Ownership:** [REPO_FUNCTION_OWNERSHIP.md](REPO_FUNCTION_OWNERSHIP.md) · [E_DRIVE_LAYOUT.md](E_DRIVE_LAYOUT.md)

## Target tree

```text
E:\Repos\
  docs\
  products\     project-kylo, greg-kylo, growflow, cog-allocation,
                ai-lab, ai-lab-governance, kylo-site, gigatt-geomapper,
                gigatt-platform
  internal\     gigatt-transport, obsidian-brain, …
  concepts\     command-center-ui
  archive\      pettycash-migration, pilot-car-map, …
  vendor\       activepieces, bmad-method, …
  tools\        migration\, scripts\, winpython\, …
```

## Path helpers

| Language | Module |
|----------|--------|
| Python | `tools/migration/python/repos_paths.py` — also dual-read in `ai-lab/operator_desk/paths.py` |
| PowerShell | `tools/migration/lib/Paths.psm1` |

Env: `REPOS_ROOT`, `AI_LAB_ROOT`, `AI_LAB_GOVERNANCE_ROOT`, `OPERATOR_BRAIN_VAULT_ROOT`

## Power-1 after cut

| Alias | Target |
|-------|--------|
| `C:\Project-Kylo` (junction) | `C:\worker\repos\products\project-kylo` |
| Greg | `C:\worker\repos\products\greg-kylo` |

## Migration order

1. Toolkit tests + `preflight` + `inventory` + `rewrite -DryRun`  
2. `edrive_hygiene` then `migrate`  
3. power-1 sync + `power1_junction` + `power1_smoke` + task reinstall  
4. Obsidian remap + workspace + `verify`  
5. Commit when asked — no GitHub push without approval  
