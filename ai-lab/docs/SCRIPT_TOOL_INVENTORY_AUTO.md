# Script / tool inventory (auto-generated)

Generated: `2026-04-28T00:02:59Z`

## How to run

```bash
cd ai-lab
python scripts/generate_integration_inventory.py
```

Optional:

```bash
python scripts/generate_integration_inventory.py --output-dir path/to/out --docs-path path/to/SCRIPT_TOOL_INVENTORY_AUTO.md
```

## Output files (machine-readable)


| File                                        | Role                                           |
| ------------------------------------------- | ---------------------------------------------- |
| `state/integration_inventory/scripts.json`  | Every scanned script + Growflow merge          |
| `state/integration_inventory/tools.json`    | Registry + brain tools + bridge/endpoint stubs |
| `state/integration_inventory/triggers.json` | Lifespan loops + PowerShell wrappers           |
| `state/integration_inventory/orphans.json`  | `orphan_candidate` scripts only                |
| `state/integration_inventory/summary.json`  | Counts + top cleanup / trigger gaps            |


## Status values (scripts)

- **wired** — clearly tied to app surface, registry, or builder role.
- **partial** — referenced or scheduled via wrapper but not fully traced.
- **manual_only** — diagnostics, probes, or Growflow host scripts.
- **orphan_candidate** — no refs, registry, or PS1 chain (review before deleting).
- **unknown_needs_review** — classifier could not bucket the path.

## Orphan candidates

Orphans are **not** failures. Treat `orphans.json` as a triage queue: confirm purpose,
add references or registry entries if promoted, else **keep_manual_only**.

## What not to auto-wire

- Do not register tools from this JSON without human approval + metadata.
- Do not treat `temp_probe` / `diagnostic` as production triggers.
- Prepared context builders are infrastructure, not user tools.

## Cadence

- Run manually after major repo moves, new scripts, or registry edits.
- Optional later: schedule weekly generation in CI or Task Scheduler (not enabled here).

## Latest summary snapshot

- Total scripts: **222**
- Total tools: **13**
- Triggers: **30**
- Orphan candidates: **25**
- Missing metadata tools: **0**

## Scan scope (important)

- Trees: `scripts/`, `brain/`, `command-center/.../backend/`, `command-center/.../frontend/src/`.
- Directory names skipped: `__pycache_`_, `node_modules`, `.venv`, `tests`, etc. (noise reduction).
- `scripts.json` merges **Growflow** rows from `growflow_runners.json` when present (`../Growflow/...`).

## `scripts.json` row fields


| Field                                            | Meaning                                                                            |
| ------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `classification`                                 | Heuristic bucket (cli, diagnostic, backend, growflow merge, …).                    |
| `writes_state_guess` / `approval_required_guess` | Regex heuristics — verify before trusting.                                         |
| `status`                                         | `wired` / `partial` / `manual_only` / `orphan_candidate` / `unknown_needs_review`. |


